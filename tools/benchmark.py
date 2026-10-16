"""Measure actual v2 generation with isolated workers and reproducible JSON evidence."""

import argparse
import ast
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIZES = (100, 1_000, 10_000, 100_000, 1_000_000)
DEPENDENCIES = ("pandas", "numpy", "python-dateutil")


def CanonicalJson(value):
    """Encode deterministic JSON while rejecting non-finite numeric evidence."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def DeclaredVersion():
    """Read the modern canonical version literal without executing package code."""

    path = ROOT / "pricegenerator" / "_version.py"

    if not path.is_file():
        return None

    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in statement.targets
        ) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            return statement.value.value

    return None


def SourceIdentity():
    """Identify checkout sources and metadata without executing packaging code."""

    sources = {}
    paths = sorted((ROOT / "pricegenerator").rglob("*.py"))
    paths.extend(ROOT / relative_path for relative_path in ("pyproject.toml", "tools/benchmark.py"))

    for path in paths:
        if path.is_file():
            sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()

    except (OSError, subprocess.SubprocessError):
        revision = None

    return {"declared_source_version": DeclaredVersion(), "git_commit": revision, "source_sha256": sources}


def Environment():
    """Record runtime and actual installed dependency versions for comparison."""

    dependencies = {}

    for name in DEPENDENCIES:
        try:
            dependencies[name] = metadata.version(name)

        except metadata.PackageNotFoundError:
            dependencies[name] = None

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "dependencies": dependencies,
    }


def PeakRss():
    """Return process lifetime peak RSS where the standard library supports it."""

    try:
        import resource

    except ImportError:
        return None

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return int(peak_rss if sys.platform == "darwin" else peak_rss * 1024)


def LoadRuntime():
    """Load actual checkout implementations and reject another installed package."""

    sys.path.insert(0, str(ROOT))

    try:
        config_module = importlib.import_module("pricegenerator.config")
        generation = importlib.import_module("pricegenerator.generation")
        streaming = importlib.import_module("pricegenerator.streaming")

    finally:
        sys.path.remove(str(ROOT))

    if Path(generation.__file__).resolve() != ROOT / "pricegenerator" / "generation.py":
        raise RuntimeError("Imported generator does not belong to the benchmark checkout")

    return config_module.GenerationConfig, generation.Generate, streaming.GenerateChunks


def EmptyCase(row_count, seed, mode="full", chunk_size=10_000):
    """Create a stable measurement record including explicit requested inputs."""

    return {
        "status": "error", "model": "regime_v2",
        "rng": "python.random.Random/MT19937", "seed": seed,
        "mode": mode, "chunk_size": chunk_size if mode == "chunked" else None,
        "configuration": None, "requested_rows": row_count,
        "generated_rows": None, "row_sha256": None, "elapsed_seconds": None,
        "tracemalloc_peak_bytes": None, "process_peak_rss_bytes": None,
        "error": None,
    }


def UpdateFingerprint(digest, frame):
    """Hash validated rows with the package's versioned exact binary64 recipe."""

    for row in frame.itertuples(index=False, name=None):
        serialized = [int(row[0].value), *(float(value).hex() for value in row[1:])]
        digest.update(json.dumps(serialized, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        digest.update(b"\n")


def RunCase(row_count, seed, mode="full", chunk_size=10_000):
    """Measure generation, canonical validation and exact output hashing together."""

    result = EmptyCase(row_count, seed, mode, chunk_size)

    try:
        config_class, generate, generate_chunks = LoadRuntime()
        config = config_class(horizon=row_count, seed=seed)
        result["configuration"] = config.ToDict()

        if mode not in {"full", "chunked"}:
            raise ValueError("mode must be full or chunked")

        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")

        if tracemalloc.is_tracing():
            raise RuntimeError("Benchmark must own tracemalloc; run it in an isolated process")

        digest = hashlib.sha256(b"pricegenerator-ohlcv-fingerprint-v1\n")
        tracemalloc.start()
        started = time.perf_counter_ns()

        try:
            chunks = [generate(config)] if mode == "full" else generate_chunks(config, chunk_size=chunk_size)
            count = 0

            for chunk in chunks:
                count += len(chunk)
                UpdateFingerprint(digest, chunk)

            result["generated_rows"] = count

        finally:
            result["elapsed_seconds"] = (time.perf_counter_ns() - started) / 1_000_000_000
            result["tracemalloc_peak_bytes"] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            result["process_peak_rss_bytes"] = PeakRss()

        if count != row_count:
            raise ValueError("Generated row count differs from the requested horizon")

        result["row_sha256"] = digest.hexdigest()
        result["status"] = "ok"

    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}

    return result


def ValidateWorker(result, expected, returncode):
    """Reject incomplete, mismatched, contradictory or nonfinite worker evidence."""

    if not isinstance(result, dict) or set(result) != set(expected):
        raise ValueError("Worker result does not match the evidence schema")

    for key in ("requested_rows", "seed", "model", "rng", "mode", "chunk_size"):
        if result[key] != expected[key]:
            raise ValueError("Worker result does not identify the requested case")

    if result["status"] not in ("ok", "error") or (returncode == 0) != (result["status"] == "ok"):
        raise ValueError("Worker exit code contradicts its result status")

    CanonicalJson(result)

    if result["status"] == "error":
        if not isinstance(result["error"], dict) or not all(isinstance(result["error"].get(key), str) for key in ("type", "message")):
            raise ValueError("Failed worker result has no actionable error")

        return

    configuration = result["configuration"]

    if not isinstance(configuration, dict) or configuration.get("seed") != expected["seed"] or configuration.get("horizon") != expected["requested_rows"]:
        raise ValueError("Worker configuration does not match the requested inputs")

    fingerprint = result["row_sha256"]

    if result["generated_rows"] != expected["requested_rows"] or result["error"] is not None:
        raise ValueError("Successful worker result has inconsistent counts or error")

    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise ValueError("Successful worker result has no valid row fingerprint")

    for key in ("elapsed_seconds", "tracemalloc_peak_bytes", "process_peak_rss_bytes"):
        value = result[key]

        if key == "process_peak_rss_bytes" and value is None:
            continue

        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Successful worker result has invalid measurement values")


def RunChild(row_count, seed, timeout, mode="full", chunk_size=10_000):
    """Run one case with bounded lifetime and retain serializable worker failures."""

    failure = EmptyCase(row_count, seed, mode, chunk_size)
    command = [
        sys.executable, str(Path(__file__).resolve()), "--worker", str(row_count),
        "--seed", str(seed), "--mode", mode, "--chunk-size", str(chunk_size),
    ]

    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)

    except (OSError, subprocess.TimeoutExpired) as error:
        failure["error"] = {"type": type(error).__name__, "message": str(error)}

        return failure

    try:
        result = json.loads(completed.stdout)
        ValidateWorker(result, failure, completed.returncode)

    except (ValueError, TypeError) as error:
        failure["error"] = {
            "type": "WorkerProtocolError", "message": str(error),
            "returncode": completed.returncode, "stderr_tail": completed.stderr[-4_000:],
        }

        return failure

    return result


def BuildReport(sizes, seed, timeout, repeat, mode="full", chunk_size=10_000):
    """Collect isolated diagnostics without imposing a noisy performance gate."""

    report = {
        "schema_version": 2, "benchmark": "regime-v2-generation-and-fingerprint-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": SourceIdentity(), "environment": Environment(),
        "measurement": {
            "elapsed_scope": "Generate or traversal of GenerateChunks, canonical validation, and exact row fingerprinting; imports and configuration excluded",
            "allocation_scope": "tracemalloc peak during elapsed_scope; tracer overhead included in runtime",
            "rss_scope": "isolated process lifetime peak through measurement, including imports; null if unavailable",
            "fingerprint": "package OHLCV fingerprint v1: UTC nanoseconds and float.hex JSON rows",
            "timeout_seconds_per_case": timeout, "performance_gate": False,
        },
        "cases": [],
    }

    for row_count in sizes:
        for repetition in range(1, repeat + 1):
            result = RunChild(row_count, seed, timeout, mode, chunk_size)
            result["repetition"] = repetition
            report["cases"].append(result)

    report["status"] = "ok" if all(case["status"] == "ok" for case in report["cases"]) else "error"

    return report


def Main(argv=None):
    """Expose a bounded benchmark command with machine-readable failure evidence."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--mode", choices=("full", "chunked"), default="full")
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sizes = args.sizes + ([] if args.worker is None else [args.worker])

    if any(not 1 <= size <= 1_000_000 for size in sizes):
        parser.error("Each size must be between 1 and 1000000")

    if args.repeat < 1 or args.chunk_size < 1 or not 0 < args.timeout < float("inf"):
        parser.error("Repeat, chunk size, and finite timeout must be positive")

    if args.worker is not None:
        with redirect_stdout(sys.stderr):
            result = RunCase(args.worker, args.seed, args.mode, args.chunk_size)

        print(CanonicalJson(result))

        return int(result["status"] != "ok")

    report = BuildReport(args.sizes, args.seed, args.timeout, args.repeat, args.mode, args.chunk_size)
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"

    if args.output is not None:
        try:
            args.output.write_text(rendered, encoding="utf-8")

        except OSError as error:
            report["status"] = "error"
            report["output_error"] = {"type": type(error).__name__, "message": str(error)}
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))

    else:
        print(rendered, end="")

    return int(report["status"] != "ok")


if __name__ == "__main__":
    sys.exit(Main())
