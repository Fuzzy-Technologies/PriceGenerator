"""Measure the real legacy generator and emit reproducible diagnostic JSON."""

import argparse
import ast
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
from importlib import metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIZES = (100, 1_000, 10_000, 100_000, 1_000_000)
COLUMNS = ("datetime", "open", "high", "low", "close", "volume")
DEPENDENCIES = ("pandas", "numpy", "python-dateutil", "bokeh", "Jinja2", "pandas-ta", "pandas-ta-classic")


def CanonicalJson(value):
    """Encode deterministic JSON while rejecting non-finite numeric evidence."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def Configuration(row_count):
    """Specify every input used by the legacy generation algorithm."""

    return {
        "horizon": row_count,
        "ticker": "BENCHMARK",
        "time_start": "2020-01-01T00:00:00+00:00",
        "timezone": "UTC",
        "timeframe_seconds": 60,
        "precision": 2,
        "min_close": 60.0,
        "max_close": 90.0,
        "init_close": 75.0,
        "max_outlier": 3.0,
        "max_candle_body": 2.7,
        "max_volume": 100_000,
        "up_candles_prob": 0.5,
        "outliers_prob": 0.03,
        "trend_deviation": 0.005,
        "trend_split": "",
        "split_count": [],
        "columns": list(COLUMNS),
    }


def DeclaredVersion():
    """Read the canonical version literal, falling back to the legacy layout."""

    for relative_path in ("pricegenerator/_version.py", "setup.py"):
        path = ROOT / relative_path

        if not path.is_file():
            continue

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
    paths.extend(ROOT / relative_path for relative_path in ("setup.py", "pyproject.toml", "tools/benchmark.py"))

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


@contextmanager
def LegacyEnvironment(seed):
    """Contain legacy global RNG, local timezone, stderr and logging effects."""

    random_state = random.getstate()
    original_timezone = os.environ.get("TZ")
    original_stderr = sys.stderr
    logger = logging.getLogger("PriceGenerator-UniLogger")
    original_disabled = logger.disabled
    os.environ["TZ"] = "UTC"

    try:
        if hasattr(time, "tzset"):
            time.tzset()

        if time.timezone != 0 or time.daylight != 0:
            raise RuntimeError("Legacy benchmark requires UTC; set the host timezone to UTC on platforms without tzset")

        # A script invocation otherwise finds tools/ before the checkout package.
        sys.path.insert(0, str(ROOT))

        try:
            module = importlib.import_module("pricegenerator.PriceGenerator")

        finally:
            sys.path.remove(str(ROOT))
            sys.stderr = original_stderr

        if Path(module.__file__).resolve() != ROOT / "pricegenerator" / "PriceGenerator.py":
            raise RuntimeError("The imported generator does not belong to this checkout")

        logger.disabled = True
        # Constructor RNG consumption is deliberately included in this recipe.
        random.seed(seed)
        yield module

    finally:
        random.setstate(random_state)
        logger.disabled = original_disabled
        sys.stderr = original_stderr

        if original_timezone is None:
            os.environ.pop("TZ", None)

        else:
            os.environ["TZ"] = original_timezone

        if hasattr(time, "tzset"):
            time.tzset()


def Generate(module, configuration):
    """Construct and configure the actual package before generating OHLCV rows."""

    generator = module.PriceGenerator()
    generator.horizon = configuration["horizon"]
    generator.ticker = configuration["ticker"]
    generator.timeStart = datetime.fromisoformat(configuration["time_start"]).astimezone(module.tzlocal())
    generator.timeframe = timedelta(seconds=configuration["timeframe_seconds"])
    generator.precision = configuration["precision"]
    generator.minClose = configuration["min_close"]
    generator.maxClose = configuration["max_close"]
    generator.initClose = configuration["init_close"]
    generator.maxOutlier = configuration["max_outlier"]
    generator.maxCandleBody = configuration["max_candle_body"]
    generator.maxVolume = configuration["max_volume"]
    generator.upCandlesProb = configuration["up_candles_prob"]
    generator.outliersProb = configuration["outliers_prob"]
    generator.trendDeviation = configuration["trend_deviation"]
    generator.trendSplit = configuration["trend_split"]
    generator.splitCount = list(configuration["split_count"])
    generator.dfHeaders = list(configuration["columns"])

    return generator.Generate()


def Fingerprint(frame):
    """Hash ordered canonical JSON rows with explicit UTC timestamps and types."""

    digest = hashlib.sha256()

    if list(frame.columns) != list(COLUMNS):
        raise ValueError("Generated columns differ from the configured OHLCV schema")

    for row in frame.itertuples(index=False, name=None):
        timestamp = row[0]

        if timestamp.utcoffset() != timedelta(0):
            raise ValueError("Generated timestamps must carry the explicit UTC timezone")

        values = [timestamp.isoformat(), *(float(value) for value in row[1:5]), int(row[5])]
        digest.update((CanonicalJson(values) + "\n").encode("utf-8"))

    return digest.hexdigest()


def PeakRss():
    """Return process lifetime peak RSS where the standard library supports it."""

    try:
        import resource

    except ImportError:
        return None

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return int(peak_rss if sys.platform == "darwin" else peak_rss * 1024)


def EmptyCase(row_count, seed):
    """Create a stable result shape shared by success and failure records."""

    return {
        "status": "error",
        "model": "legacy_v1",
        "rng": "python.random.MT19937; seed before constructor",
        "seed": seed,
        "configuration": Configuration(row_count),
        "requested_rows": row_count,
        "generated_rows": None,
        "row_sha256": None,
        "elapsed_seconds": None,
        "tracemalloc_peak_bytes": None,
        "process_peak_rss_bytes": None,
        "error": None,
    }


def RunCase(row_count, seed):
    """Measure generation only, then validate and fingerprint its actual output."""

    result = EmptyCase(row_count, seed)

    try:
        with LegacyEnvironment(seed) as module:
            if tracemalloc.is_tracing():
                raise RuntimeError("Benchmark must own tracemalloc; run it in an isolated process")

            tracemalloc.start()
            started = time.perf_counter_ns()

            try:
                frame = Generate(module, result["configuration"])

            finally:
                result["elapsed_seconds"] = (time.perf_counter_ns() - started) / 1_000_000_000
                result["tracemalloc_peak_bytes"] = tracemalloc.get_traced_memory()[1]
                tracemalloc.stop()
                result["process_peak_rss_bytes"] = PeakRss()

            result["generated_rows"] = len(frame)

            if len(frame) != row_count:
                raise ValueError("Generated row count differs from the requested horizon")

            result["row_sha256"] = Fingerprint(frame)
            result["status"] = "ok"

    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}

    return result


def ValidateWorker(result, expected, returncode):
    """Reject incomplete, mismatched or non-finite worker evidence."""

    if not isinstance(result, dict) or set(result) != set(expected):
        raise ValueError("Worker result does not match the evidence schema")

    for key in ("requested_rows", "seed", "configuration", "model", "rng"):
        if result[key] != expected[key]:
            raise ValueError("Worker result does not identify the requested case")

    if result["status"] not in ("ok", "error"):
        raise ValueError("Worker result has no valid status")

    if (returncode == 0) != (result["status"] == "ok"):
        raise ValueError("Worker exit code contradicts its result status")

    CanonicalJson(result)

    if result["status"] == "error":
        if not isinstance(result["error"], dict) or not all(
            isinstance(result["error"].get(key), str) for key in ("type", "message")
        ):
            raise ValueError("Failed worker result has no actionable error")

        return

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


def RunChild(row_count, seed, timeout):
    """Run one size with bounded lifetime and preserve serializable failures."""

    failure = EmptyCase(row_count, seed)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(row_count), "--seed", str(seed)]

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
            "type": "WorkerProtocolError",
            "message": str(error),
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-4_000:],
        }

        return failure

    return result


def BuildReport(sizes, seed, timeout, repeat):
    """Collect isolated observations without imposing performance thresholds."""

    report = {
        "schema_version": 1,
        "benchmark": "legacy-generation-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": SourceIdentity(),
        "environment": Environment(),
        "measurement": {
            "elapsed_scope": "constructor, explicit configuration and Generate; imports and fingerprint excluded",
            "allocation_scope": "tracemalloc peak during elapsed_scope; tracer overhead is included in runtime",
            "rss_scope": "isolated process lifetime peak through generation; includes imports; null if unavailable",
            "fingerprint": "SHA-256 of UTF-8 compact JSON row arrays followed by LF; timestamp ISO-8601, float OHLC, int volume",
            "timeout_seconds_per_case": timeout,
            "performance_gate": False,
        },
        "cases": [],
    }

    for row_count in sizes:
        for repetition in range(1, repeat + 1):
            result = RunChild(row_count, seed, timeout)
            result["repetition"] = repetition
            report["cases"].append(result)

    report["status"] = "ok" if all(case["status"] == "ok" for case in report["cases"]) else "error"

    return report


def Main(argv=None):
    """Expose a reproducible benchmark CLI with optional JSON file output."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES), help="Row counts, each at least 5")
    parser.add_argument("--seed", type=int, default=0, help="Explicit random seed; zero is valid (default: 0)")
    parser.add_argument("--repeat", type=int, default=1, help="Independent observations per size (default: 1)")
    parser.add_argument("--timeout", type=float, default=120, help="Seconds allowed per isolated case (default: 120)")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout; parent directory must exist")
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if any(size < 5 for size in args.sizes) or (args.worker is not None and args.worker < 5):
        parser.error("Each size must be at least 5; the legacy generator silently expands smaller requests")

    if args.repeat < 1 or not 0 < args.timeout < float("inf"):
        parser.error("Repeat must be positive and timeout must be finite and positive")

    if args.worker is not None:
        # Optional legacy imports must not contaminate the JSON transport.
        with redirect_stdout(sys.stderr):
            result = RunCase(args.worker, args.seed)

        print(CanonicalJson(result))

        return int(result["status"] != "ok")

    report = BuildReport(args.sizes, args.seed, args.timeout, args.repeat)
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
