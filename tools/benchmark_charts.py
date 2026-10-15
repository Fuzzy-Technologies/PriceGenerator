"""Record matched chart exports and actual headless Canvas timings as JSON."""

import argparse
from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timezone
import gzip
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SIZES = (1_000, 10_000, 100_000)


def ErrorRecord(error):
    """Keep diagnostic failures serializable without fabricating measurements."""

    return {"type": type(error).__name__, "message": str(error)}


def Environment():
    """Record the Python renderer dependency environment for each report."""

    dependencies = {}

    for name in ("pandas", "numpy", "bokeh", "Jinja2", "pandas-ta", "pandas-ta-classic"):
        try:
            dependencies[name] = metadata.version(name)

        except metadata.PackageNotFoundError:
            dependencies[name] = None

    return {"python": platform.python_version(), "python_executable": sys.executable, "platform": platform.platform(),
        "machine": platform.machine(), "cpu_count": os.cpu_count(), "dependencies": dependencies}


def SourceIdentity(source_root):
    """Fingerprint the measured checkout and the independent benchmark recipes."""

    paths = sorted((source_root / "pricegenerator").rglob("*"))
    paths.extend(source_root / name for name in ("setup.py", "pyproject.toml"))
    paths.extend(source_root / "tools" / "chart_runtime" / name
        for name in ("canvas_environment.cjs", "package.json", "package-lock.json"))
    hashes = {}

    for path in paths:
        if path.is_file() and "__pycache__" not in path.parts:
            hashes[path.relative_to(source_root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source_root,
            capture_output=True, text=True, check=True, timeout=5).stdout.strip()

    except (OSError, subprocess.SubprocessError):
        revision = None

    recipes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), Path(__file__).with_suffix(".cjs"))}

    return {"git_commit": revision, "source_sha256": hashes, "recipe_sha256": recipes}


def RunJSON(command, timeout, cwd, isolate=True):
    """Require a successful worker to return finite, explicitly successful JSON."""

    try:
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=isolate and os.name == "posix")

        try:
            stdout, stderr = process.communicate(timeout=timeout)

        except subprocess.TimeoutExpired as error:
            # The outer worker owns its POSIX process group, including its Node child.
            try:
                if isolate and os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)

                else:
                    process.kill()

            except ProcessLookupError:
                pass

            process.communicate()

            return {"status": "error", "error": ErrorRecord(error)}

        result = json.loads(stdout)

        if not isinstance(result, dict) or result.get("status") not in ("ok", "error"):
            raise ValueError("Worker did not return a status-bearing JSON object")

        json.dumps(result, allow_nan=False)

        if (process.returncode == 0) != (result["status"] == "ok"):
            raise ValueError("Worker exit code contradicts its reported status")

        return result

    except OSError as error:
        return {"status": "error", "error": ErrorRecord(error)}

    except (ValueError, TypeError) as error:
        return {"status": "error", "error": {"type": "WorkerProtocolError", "message": str(error),
            "returncode": process.returncode, "stderr_tail": stderr[-4000:]}}


def Timed(operation):
    """Measure one synchronous stage with a monotonic clock."""

    started = time.perf_counter_ns()
    value = operation()

    return value, (time.perf_counter_ns() - started) / 1_000_000_000


def WriteMeasured(text, path):
    """Measure UTF-8 file writing separately from rendering and compression."""

    encoded = text.encode("utf-8")
    _, seconds = Timed(lambda: path.write_bytes(encoded))

    return {"write_seconds": seconds, "bytes": len(encoded),
        "gzip_bytes": len(gzip.compress(encoded, compresslevel=9, mtime=0)),
        "sha256": hashlib.sha256(encoded).hexdigest()}


def Fixture(row_count):
    """Build deterministic shared OHLCV, one gapped overlay and one annotation."""

    import pandas as pd
    from pricegenerator.PriceGenerator import PriceGenerator

    indices = range(row_count)
    opens = [100 + (index % 97) / 100 for index in indices]
    closes = [value + (0.15 if index % 2 else -0.15) for index, value in enumerate(opens)]
    frame = pd.DataFrame({
        "datetime": pd.date_range("2020-01-01T00:00:00Z", periods=row_count, freq="min"),
        "open": opens, "high": [max(first, second) + 0.3 for first, second in zip(opens, closes)],
        "low": [min(first, second) - 0.3 for first, second in zip(opens, closes)],
        "close": closes, "volume": [1000 + index % 997 for index in indices],
    })
    model = PriceGenerator()
    model.prices = frame
    model.horizon = row_count
    model.precision = 2
    model.ticker = "BENCHMARK"
    overlay = pd.DataFrame({"datetime": frame.datetime,
        "Reference": [None if index < 19 else (first + second) / 2 for index, (first, second) in enumerate(zip(opens, closes))]})
    markers = pd.DataFrame({"datetime": frame.datetime,
        "markersUpper": ["Signal" if index == row_count // 2 else "" for index in indices]})

    return model, overlay, markers


def PythonCase(args):
    """Measure both real renderers with matched source data and explicit scopes."""

    result = {"status": "error", "requested_rows": args.worker, "stages": {}}
    sys.path.insert(0, str(args.source_root))

    try:
        from pricegenerator.rendering.adapters import BuildLegacyChart
        from pricegenerator.rendering.interactive import RenderInteractive
        from pricegenerator.rendering.static import RenderSVG
        import pricegenerator.PriceGenerator as legacy
        from bokeh.embed import file_html
        from bokeh.resources import INLINE

        if Path(legacy.__file__).resolve() != args.source_root / "pricegenerator" / "PriceGenerator.py":
            raise RuntimeError("Imported PriceGenerator does not match --source-root")

        legacy.uLogger.disabled = True
        model, overlay, markers = Fixture(args.worker)
        title = "Matched chart benchmark"
        spec, adapter_seconds = Timed(lambda: BuildLegacyChart(model,
            include_statistics=False, lines=(overlay,), markers=markers,
            title=title, theme="dark", width=1280, height=760))
        spec_json, json_seconds = Timed(spec.ToJSON)
        result["fixture"] = {"recipe": "arithmetic-ohlcv-v1", "seed": None,
            "timezone": "UTC", "start": "2020-01-01T00:00:00Z", "timeframe_seconds": 60,
            "rows": len(spec.candles), "overlays": len(spec.series), "markers": len(spec.markers),
            "width": 1280, "height": 760, "automatic_statistics": False,
            "chart_spec_sha256": hashlib.sha256(spec_json.encode("utf-8")).hexdigest()}
        result["stages"]["adapter_seconds"] = adapter_seconds
        result["stages"]["spec_serialization_seconds"] = json_seconds
        result["stages"]["spec_json_bytes"] = len(spec_json.encode("utf-8"))

        if len(spec.candles) != args.worker or len(spec.series) != 1 or len(spec.markers) != 1:
            raise ValueError("The matched fixture lost rows, its overlay or its annotation")

        working_directory = nullcontext(str(args.work_directory)) if args.work_directory else tempfile.TemporaryDirectory(prefix="pricegenerator-charts-")

        with working_directory as temporary:
            directory = Path(temporary)
            svg, seconds = Timed(lambda: RenderSVG(spec))
            result["stages"]["static_svg"] = dict(WriteMeasured(svg, directory / "chart.svg"), render_seconds=seconds)
            del svg
            html, seconds = Timed(lambda: RenderInteractive(spec))
            html_path = directory / "chart.html"
            result["stages"]["interactive_html"] = dict(WriteMeasured(html, html_path), render_seconds=seconds)
            del html

            try:
                layout, model_seconds = Timed(lambda: model.RenderBokeh(fileName=None,
                    darkTheme=True, showStatOnChart=False, showControlsOnChart=True,
                    lines=[overlay], markers=markers, title=title, width=1280, height=760))
                legacy_html, serialization_seconds = Timed(lambda: file_html(layout, INLINE, title))
                result["stages"]["legacy_bokeh_html"] = dict(
                    WriteMeasured(legacy_html, directory / "legacy.html"),
                    model_seconds=model_seconds, serialization_seconds=serialization_seconds,
                    resources="INLINE", automatic_statistics=False, status="ok")
                del legacy_html
                layout = None

            except Exception as error:
                result["stages"]["legacy_bokeh_html"] = {"status": "error", "error": ErrorRecord(error)}

            command = [args.node, str(Path(__file__).with_suffix(".cjs")),
                str(args.source_root), args.canvas_module, str(html_path)]
            result["canvas"] = RunJSON(command, args.timeout, args.source_root, isolate=False)

        if result["canvas"]["status"] == "ok" and result["stages"]["legacy_bokeh_html"]["status"] == "ok":
            if result["canvas"].get("total_rows") != args.worker:
                raise ValueError("Canvas evidence does not identify the requested row count")

            result["status"] = "ok"

    except Exception as error:
        result["error"] = ErrorRecord(error)

    return result


def Main(argv=None):
    """Run bounded isolated chart cases without browser performance claims."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--canvas-module", default="@napi-rs/canvas", help="Pinned module name or explicit installed module directory")
    parser.add_argument("--node", default="node")
    parser.add_argument("--timeout", type=float, default=60, help="Seconds allowed per Python or Canvas worker")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--work-directory", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.source_root = args.source_root.resolve()

    if any(size < 20 for size in args.sizes) or (args.worker is not None and args.worker < 20):
        parser.error("Sizes must be at least 20 for the shared gapped overlay fixture")

    if not 0 < args.timeout < float("inf"):
        parser.error("Timeout must be finite and positive")

    if args.worker is not None:
        with redirect_stdout(sys.stderr):
            result = PythonCase(args)

        print(json.dumps(result, allow_nan=False))

        return int(result["status"] != "ok")

    report = {"schema_version": 1, "benchmark": "chart-performance-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": SourceIdentity(args.source_root), "environment": Environment(),
        "invocation": {"source_root": str(args.source_root), "sizes": args.sizes,
            "canvas_module": args.canvas_module, "node": args.node, "timeout_seconds": args.timeout},
        "scope": {
            "fixture": "Shared arithmetic OHLCV, one custom overlay with 19 leading gaps, one above-candle marker; automatic indicators disabled in both paths",
            "python": "Fixture and imports excluded; adapter, serialization, renderer construction and file writes measured separately; gzip and hashes excluded",
            "legacy": "Real RenderBokeh model construction plus offline INLINE file_html serialization and explicit UTF-8 file write; no legacy browser timing",
            "canvas": "Real vendored ECharts and native raster Canvas with DOM/lifecycle shim; no browser, DOM layout, input delivery or display FPS measurement",
            "comparison": "New chart initial viewport may display fewer candles; full-range timings and visible counts recorded separately; no speed ratio implied",
            "repetitions": "One observation per size in a fresh Python and Node process; no warmup or statistical aggregation",
            "timeout_seconds_per_worker": args.timeout,
            "performance_gate": False,
        }, "cases": []}

    for row_count in args.sizes:
        # Parent ownership permits cleanup even after a killed worker cannot run finally.
        with tempfile.TemporaryDirectory(prefix="pricegenerator-chart-case-") as temporary:
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(row_count),
                "--source-root", str(args.source_root), "--canvas-module", args.canvas_module,
                "--node", args.node, "--timeout", str(args.timeout), "--work-directory", temporary]
            result = RunJSON(command, args.timeout, args.source_root)

        if result["status"] == "ok" and result.get("requested_rows") != row_count:
            result = {"status": "error", "error": {"type": "WorkerProtocolError", "message": "Worker row count differs from the requested case"}}

        result["requested_rows"] = row_count
        report["cases"].append(result)

    report["source_tree_stable"] = SourceIdentity(args.source_root) == report["source"]
    report["status"] = "ok" if report["source_tree_stable"] and all(case["status"] == "ok" for case in report["cases"]) else "error"

    if not report["source_tree_stable"]:
        report["source_error"] = {"type": "SourceChangedError", "message": "Measured sources or benchmark recipes changed during the run"}

    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"

    if args.output is None:
        print(rendered, end="")

    else:
        try:
            args.output.write_text(rendered, encoding="utf-8")

        except OSError as error:
            report["status"] = "error"
            report["output_error"] = ErrorRecord(error)
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))

    return int(report["status"] != "ok")


if __name__ == "__main__":
    sys.exit(Main())
