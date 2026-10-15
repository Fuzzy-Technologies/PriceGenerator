"""Verify real benchmark replay, isolation, evidence and deterministic failures."""

import json
import logging
import os
import random
import subprocess
import sys
import tracemalloc
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from tools import benchmark


def test_RealPackageReplaysAndRestoresProcessState():
    """Actual generation replays seed zero without consuming host RNG state."""

    original_state = random.getstate()
    original_stderr = sys.stderr
    original_timezone = os.environ.get("TZ")
    first = benchmark.RunCase(100, 0)
    second = benchmark.RunCase(100, 0)
    different = benchmark.RunCase(100, 1)

    assert first["status"] == second["status"] == different["status"] == "ok", "Actual package generation must succeed"
    assert first["generated_rows"] == 100, "The benchmark must measure the requested horizon"
    assert first["row_sha256"] == second["row_sha256"], "Identical seed and configuration must replay exactly"
    assert first["row_sha256"] != different["row_sha256"], "The supplied seed must reach the real generator"
    assert first["elapsed_seconds"] > 0, "Generation runtime must be measured"
    assert first["tracemalloc_peak_bytes"] > 0, "Allocation evidence must measure actual generation"
    assert random.getstate() == original_state, "Benchmarking must restore the caller's global RNG"
    assert sys.stderr is original_stderr, "Legacy import must not retain its stderr replacement"
    assert os.environ.get("TZ") == original_timezone, "Benchmarking must restore the caller's timezone setting"
    assert not tracemalloc.is_tracing(), "Benchmark-owned tracing must stop after measurement"


def test_RealCommandProducesReplayableEvidence(tmp_path):
    """The public command runs isolated real workers and creates usable JSON."""

    output = tmp_path / "evidence.json"
    completed = subprocess.run(
        [sys.executable, str(benchmark.ROOT / "tools" / "benchmark.py"), "--sizes", "5", "--repeat", "2", "--output", str(output)],
        check=False, capture_output=True, text=True, timeout=30,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert completed.returncode == 0, f"Real benchmark CLI failed: {completed.stderr}"
    assert not completed.stdout, "File output must not leak worker logs into stdout"
    assert report["status"] == "ok", "Successful workers must yield successful evidence"
    assert isinstance(report["source"]["declared_source_version"], str), "Evidence must identify the benchmarked source version"
    assert report["environment"]["dependencies"]["pandas"], "Actual dependencies must be recorded"
    assert report["measurement"]["performance_gate"] is False, "Diagnostic timings must not create a performance gate"
    assert report["cases"][0]["row_sha256"] == report["cases"][1]["row_sha256"], "Separate workers must replay identically"
    assert len(report["source"]["source_sha256"]["tools/benchmark.py"]) == 64, "Evidence must identify its benchmark recipe"


def test_GenerationFailureRestoresResources(monkeypatch):
    """A failing generator still produces timings and restores process resources."""

    original_state = random.getstate()
    logger = logging.getLogger("PriceGenerator-UniLogger")
    original_disabled = logger.disabled
    monkeypatch.setattr(benchmark, "Generate", Mock(side_effect=RuntimeError("controlled generation failure")))
    result = benchmark.RunCase(5, 0)

    assert result["error"] == {"type": "RuntimeError", "message": "controlled generation failure"}, "Failures must remain machine-readable"
    assert result["elapsed_seconds"] is not None, "Failed generation must retain elapsed evidence"
    assert result["tracemalloc_peak_bytes"] is not None, "Failed generation must retain allocation evidence"
    assert random.getstate() == original_state, "Failure must restore constructor seed changes"
    assert logger.disabled == original_disabled, "Failure must restore logging suppression"
    assert not tracemalloc.is_tracing(), "Failure must not leak the allocation tracer"
    json.dumps(result, allow_nan=False)


def test_ImportFailureRestoresState(monkeypatch):
    """A missing legacy dependency fails explicitly without leaking import setup."""

    original_path = list(sys.path)
    original_state = random.getstate()
    original_timezone = os.environ.get("TZ")
    monkeypatch.setattr(benchmark.importlib, "import_module", Mock(side_effect=ImportError("missing real dependency")))
    result = benchmark.RunCase(5, 0)

    assert result["error"]["type"] == "ImportError", "Missing dependencies must not become synthetic benchmark successes"
    assert result["elapsed_seconds"] is None, "Import failure occurs outside measured generation"
    assert sys.path == original_path, "Temporary checkout import priority must be restored"
    assert random.getstate() == original_state, "Import failure must restore process RNG"
    assert os.environ.get("TZ") == original_timezone, "Import failure must restore timezone settings"


def test_RejectsAnotherCheckout(monkeypatch):
    """A previously imported unrelated package must not be mislabeled as this code."""

    module = SimpleNamespace(__file__="/another/checkout/pricegenerator/PriceGenerator.py")
    monkeypatch.setattr(benchmark.importlib, "import_module", Mock(return_value=module))
    result = benchmark.RunCase(5, 0)

    assert "does not belong" in result["error"]["message"], "Source identity must match the imported module"


def test_NonUtcHostWithoutTzsetFailsClearly(monkeypatch):
    """Unsupported timezone isolation must fail rather than mislabel local time."""

    monkeypatch.delattr(benchmark.time, "tzset", raising=False)
    monkeypatch.setattr(benchmark.time, "timezone", 3600)
    result = benchmark.RunCase(5, 0)

    assert "requires UTC" in result["error"]["message"], "Uncontrolled local timezone must not claim UTC replay"


def test_ExistingTracerRemainsOwnedByCaller():
    """Refusing nested tracing must preserve the host's allocation measurement."""

    tracemalloc.start()

    try:
        result = benchmark.RunCase(5, 0)
        assert "must own tracemalloc" in result["error"]["message"], "Nested tracing must be rejected explicitly"
        assert tracemalloc.is_tracing(), "Rejecting the benchmark must not stop the caller's tracer"

    finally:
        tracemalloc.stop()


def test_RowCountMismatchIsFailure(monkeypatch):
    """Silently altered generation sizes cannot pass as comparable evidence."""

    monkeypatch.setattr(benchmark, "Generate", Mock(return_value=[]))
    result = benchmark.RunCase(5, 0)

    assert result["status"] == "error", "A row count mismatch must fail the observation"
    assert result["generated_rows"] == 0, "Failure evidence must retain the actual output count"
    assert result["row_sha256"] is None, "Invalid output must not receive a success fingerprint"


@pytest.mark.parametrize("defect", ["schema", "timezone", "nonfinite"])
def test_FingerprintRejectsInvalidRows(defect):
    """Fingerprinting must reject mismatched schema, naive times and NaN values."""

    row = [pd.Timestamp("2020-01-01", tz="UTC"), 1.0, 2.0, 0.5, 1.5, 10]
    columns = list(benchmark.COLUMNS)

    if defect == "schema":
        columns[0] = "wrong_datetime"

    elif defect == "timezone":
        row[0] = pd.Timestamp("2020-01-01")

    else:
        row[1] = float("nan")

    with pytest.raises(ValueError):
        benchmark.Fingerprint(pd.DataFrame([row], columns=columns))


@pytest.mark.parametrize("error", [FileNotFoundError("worker executable missing"), subprocess.TimeoutExpired("worker", 1)])
def test_WorkerLaunchFailureIsSerializable(monkeypatch, error):
    """Spawn failure and timeout produce case records instead of aborting the run."""

    monkeypatch.setattr(benchmark.subprocess, "run", Mock(side_effect=error))
    result = benchmark.RunChild(100, 0, 1)

    assert result["status"] == "error", "Worker infrastructure failure must fail its observation"
    assert result["error"]["type"] == type(error).__name__, "Failure type must remain actionable"
    assert result["requested_rows"] == 100 and result["seed"] == 0, "Failed workers must retain scenario identity"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        ("not JSON", 1),
        ("null", 0),
        ('{"requested_rows":6,"seed":0,"status":"ok"}', 0),
        ('{"requested_rows":5,"seed":1,"status":"ok"}', 0),
        ('{"requested_rows":5,"seed":0,"status":"unknown"}', 0),
        ('{"requested_rows":5,"seed":0,"status":"error"}', 0),
        ('{"requested_rows":5,"seed":0,"status":"ok"}', 1),
    ],
)
def test_InvalidWorkerTransportIsFailure(monkeypatch, stdout, returncode):
    """Malformed or contradictory worker evidence must be rejected explicitly."""

    completed = subprocess.CompletedProcess([], returncode, stdout, "diagnostic" * 1000)
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(return_value=completed))
    result = benchmark.RunChild(5, 0, 1)

    assert result["error"]["type"] == "WorkerProtocolError", "Invalid transport cannot count as a benchmark result"
    assert len(result["error"]["stderr_tail"]) <= 4000, "Worker diagnostic retention must be bounded"


def test_WorkerReportedErrorIsPreserved(monkeypatch):
    """A well-formed worker failure preserves its original diagnostics."""

    failure = benchmark.EmptyCase(5, 0)
    failure["error"] = {"type": "ImportError", "message": "dependency unavailable"}
    completed = subprocess.CompletedProcess([], 1, json.dumps(failure), "")
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(return_value=completed))

    assert benchmark.RunChild(5, 0, 1) == failure, "Worker errors must not be replaced with transport errors"


@pytest.mark.parametrize(
    ("field", "value", "returncode"),
    [
        ("requested_rows", 6, 1),
        ("seed", 1, 1),
        ("configuration", {}, 1),
        ("status", "unknown", 1),
        ("status", "error", 0),
        ("error", None, 1),
    ],
)
def test_InvalidCompleteFailureIsRejected(field, value, returncode):
    """A full-shaped failure must still have correct identity and diagnostics."""

    expected = benchmark.EmptyCase(5, 0)
    result = dict(expected, error={"type": "RuntimeError", "message": "failure"})
    result[field] = value

    with pytest.raises(ValueError):
        benchmark.ValidateWorker(result, expected, returncode)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generated_rows", 4),
        ("error", {"type": "RuntimeError", "message": "failure"}),
        ("row_sha256", "invalid"),
        ("elapsed_seconds", None),
        ("elapsed_seconds", float("nan")),
        ("tracemalloc_peak_bytes", -1),
        ("process_peak_rss_bytes", True),
    ],
)
def test_IncompleteSuccessEvidenceIsRejected(field, value):
    """Successful status must be supported by finite measurements and output."""

    expected = benchmark.EmptyCase(5, 0)
    result = dict(expected, status="ok", generated_rows=5, row_sha256="0" * 64, elapsed_seconds=0.1, tracemalloc_peak_bytes=1)
    result[field] = value

    with pytest.raises(ValueError):
        benchmark.ValidateWorker(result, expected, 0)


def test_ValidSuccessWithoutRssIsAccepted():
    """RSS is optional where the platform has no resource module."""

    expected = benchmark.EmptyCase(5, 0)
    result = dict(expected, status="ok", generated_rows=5, row_sha256="0" * 64, elapsed_seconds=0.1, tracemalloc_peak_bytes=1)
    benchmark.ValidateWorker(result, expected, 0)


def test_FailedCaseDoesNotDiscardLaterObservations(monkeypatch):
    """A failed size leaves the remaining diagnostic sequence runnable."""

    failure = benchmark.EmptyCase(5, 0)
    success = benchmark.EmptyCase(10, 0)
    success["status"] = "ok"
    run_child = Mock(side_effect=[failure, success])
    monkeypatch.setattr(benchmark, "RunChild", run_child)
    report = benchmark.BuildReport([5, 10], 0, 1, 1)

    assert report["status"] == "error", "A failed observation must remain visible in the aggregate result"
    assert len(report["cases"]) == 2, "Later requested sizes must still be attempted"
    assert run_child.call_count == 2, "A worker failure must not abort all diagnostic work"


@pytest.mark.parametrize("arguments", [["--sizes", "4"], ["--worker", "3"], ["--repeat", "0"], ["--timeout", "0"], ["--timeout", "nan"], ["--timeout", "inf"]])
def test_InvalidCliInputsAreRejected(arguments):
    """Invalid sizes and unbounded execution settings must not launch workers."""

    with pytest.raises(SystemExit) as error:
        benchmark.Main(arguments)

    assert error.value.code == 2, "Invalid benchmark input must use the CLI usage-error exit code"


def test_OutputFailurePreservesJsonOnStdout(monkeypatch, tmp_path, capsys):
    """An unwritable destination retains evidence and reports a failed exit."""

    monkeypatch.setattr(benchmark, "BuildReport", Mock(return_value={"status": "ok", "cases": []}))
    exit_code = benchmark.Main(["--sizes", "5", "--output", str(tmp_path / "missing" / "evidence.json")])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1, "Failed evidence writing must be reflected in the process exit code"
    assert report["output_error"]["type"] == "FileNotFoundError", "The output problem must remain machine-readable"


def test_WorkerNoiseDoesNotCorruptJson(monkeypatch, capsys):
    """Optional dependency messages must go to stderr instead of JSON stdout."""

    def NoisyCase(row_count, seed):
        """Simulate an optional import message during worker setup."""

        print("optional import diagnostic")

        return benchmark.EmptyCase(row_count, seed)

    monkeypatch.setattr(benchmark, "RunCase", NoisyCase)
    exit_code = benchmark.Main(["--worker", "5"])
    captured = capsys.readouterr()

    assert json.loads(captured.out)["requested_rows"] == 5, "Worker stdout must remain one valid JSON object"
    assert "optional import diagnostic" in captured.err, "Import diagnostics must remain available on stderr"
    assert exit_code == 1, "Worker failure status must control its process exit code"


def test_MissingDistributionAndGitAreExplicit(monkeypatch):
    """Source archives and missing dependency metadata remain valid diagnostics."""

    monkeypatch.setattr(benchmark.metadata, "version", Mock(side_effect=benchmark.metadata.PackageNotFoundError))
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(side_effect=FileNotFoundError("git missing")))

    assert all(value is None for value in benchmark.Environment()["dependencies"].values()), "Missing dependencies must be recorded as null"
    assert benchmark.SourceIdentity()["git_commit"] is None, "Source archives must not invent a Git revision"


@pytest.mark.parametrize("modern_layout", [False, True])
def test_SourceIdentitySupportsVersionLayouts(monkeypatch, tmp_path, modern_layout):
    """Legacy setup.py and the new canonical version file both identify sources."""

    package = tmp_path / "pricegenerator"
    package.mkdir()
    (package / "__init__.py").write_text('"""Fixture package."""\n', encoding="utf-8")
    expected_version = "2.0.0.dev0" if modern_layout else "1.4"
    version_path = package / "_version.py" if modern_layout else tmp_path / "setup.py"
    version_path.write_text(f'"""Fixture version."""\n\n__version__ = "{expected_version}"\n', encoding="utf-8")

    if modern_layout:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pricegenerator"\n', encoding="utf-8")

    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(return_value=SimpleNamespace(stdout="fixture-commit\n")))
    identity = benchmark.SourceIdentity()

    assert identity["declared_source_version"] == expected_version, "Each source layout must expose its declared version"
    assert version_path.relative_to(tmp_path).as_posix() in identity["source_sha256"], "The version source must be hashed"
    assert ("pyproject.toml" in identity["source_sha256"]) == modern_layout, "Only present packaging metadata must be hashed"
    assert ("setup.py" in identity["source_sha256"]) != modern_layout, "Removed legacy setup.py must not be required"


@pytest.mark.parametrize(("target_platform", "expected"), [("linux", 2048), ("darwin", 2)])
def test_PeakRssUnitsAreNormalized(monkeypatch, target_platform, expected):
    """Linux KiB and macOS byte resource counters produce explicit byte units."""

    resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=Mock(return_value=SimpleNamespace(ru_maxrss=2)))
    monkeypatch.setitem(sys.modules, "resource", resource)
    monkeypatch.setattr(sys, "platform", target_platform)

    assert benchmark.PeakRss() == expected, "Peak RSS must use byte units on supported platforms"


def test_UnavailablePeakRssIsNull(monkeypatch):
    """Platforms without resource still retain traced allocation evidence."""

    monkeypatch.setitem(sys.modules, "resource", None)

    assert benchmark.PeakRss() is None, "Unsupported RSS measurement must be reported as unavailable"
