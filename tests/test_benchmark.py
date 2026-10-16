"""Verify modern benchmark evidence, actual generation, and isolated error paths."""

import json
import subprocess
import tracemalloc
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.scenario import Fingerprint
from tools import benchmark


@pytest.mark.parametrize("mode", ["full", "chunked"])
def test_ActualRuntimeProducesExactComparableEvidence(mode):
    """Measure actual package execution and match the canonical package fingerprint."""

    result = benchmark.RunCase(21, 0, mode, 4)
    assert result["status"] == "ok", result["error"]
    assert result["generated_rows"] == 21
    assert result["row_sha256"] == Fingerprint(Generate(GenerationConfig(horizon=21, seed=0)))
    assert result["elapsed_seconds"] > 0
    assert result["tracemalloc_peak_bytes"] > 0
    benchmark.ValidateWorker(result, benchmark.EmptyCase(21, 0, mode, 4), 0)


def test_ActualWorkerCLIProducesValidJSON():
    """Exercise real subprocess transport and exact source package loading."""

    result = benchmark.RunChild(5, 0, 20, "chunked", 2)
    assert result["status"] == "ok", result["error"]
    assert result["row_sha256"] == Fingerprint(Generate(GenerationConfig(horizon=5)))


def test_ExistingTracerRemainsOwnedByCaller():
    """Refuse nested allocation tracing without stopping the caller's tracer."""

    tracemalloc.start()

    try:
        result = benchmark.RunCase(5, 0)
        assert "must own tracemalloc" in result["error"]["message"]
        assert tracemalloc.is_tracing()

    finally:
        tracemalloc.stop()


def test_GenerationFailureStopsOwnedTracer(monkeypatch):
    """Release tracing after an injected runtime failure and retain diagnostics."""

    config_class, _, chunks = benchmark.LoadRuntime()
    monkeypatch.setattr(benchmark, "LoadRuntime", Mock(return_value=(config_class, Mock(side_effect=RuntimeError("injected")), chunks)))
    result = benchmark.RunCase(5, 0)
    assert result["error"] == {"type": "RuntimeError", "message": "injected"}
    assert result["elapsed_seconds"] is not None
    assert not tracemalloc.is_tracing()


def test_RowCountMismatchCannotPass(monkeypatch):
    """Fail short model output even when its rows are otherwise valid."""

    config_class, _, chunks = benchmark.LoadRuntime()
    monkeypatch.setattr(benchmark, "LoadRuntime", Mock(return_value=(config_class, Mock(return_value=Generate(GenerationConfig(horizon=1))), chunks)))
    result = benchmark.RunCase(5, 0)
    assert result["status"] == "error"
    assert result["generated_rows"] == 1
    assert result["row_sha256"] is None


@pytest.mark.parametrize("error", [FileNotFoundError("missing"), subprocess.TimeoutExpired("worker", 1)])
def test_WorkerLaunchFailureIsSerializable(monkeypatch, error):
    """Preserve infrastructure failure identity and allow subsequent cases."""

    monkeypatch.setattr(benchmark.subprocess, "run", Mock(side_effect=error))
    result = benchmark.RunChild(5, 0, 1)
    assert result["error"]["type"] == type(error).__name__
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("stdout,returncode", [("not JSON", 1), ("null", 0), ('{"status":"ok"}', 0)])
def test_InvalidWorkerTransportRetainsBoundedDiagnostics(monkeypatch, stdout, returncode):
    """Reject corrupted transport without trusting a successful process exit."""

    monkeypatch.setattr(benchmark.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], returncode, stdout, "x" * 5000)))
    result = benchmark.RunChild(5, 0, 1)
    assert result["error"]["type"] == "WorkerProtocolError"
    assert len(result["error"]["stderr_tail"]) == 4000


@pytest.mark.parametrize("field,value", [
    ("requested_rows", 6), ("seed", 2), ("mode", "unknown"),
    ("configuration", {}), ("row_sha256", "invalid"), ("generated_rows", 4),
    ("elapsed_seconds", float("nan")), ("tracemalloc_peak_bytes", -1),
    ("process_peak_rss_bytes", True), ("error", {"type": "Error", "message": "failed"}),
])
def test_RejectInvalidSuccessEvidence(field, value):
    """Require measured counts, identity, finite metrics, and a valid output hash."""

    expected = benchmark.EmptyCase(5, 0)
    result = dict(expected, status="ok", configuration=GenerationConfig(horizon=5).ToDict(), generated_rows=5, row_sha256="0" * 64, elapsed_seconds=.1, tracemalloc_peak_bytes=1)
    result[field] = value

    with pytest.raises(ValueError):
        benchmark.ValidateWorker(result, expected, 0)


def test_ReportedFailureIsPreservedAndExitContradictionFails(monkeypatch):
    """Keep actionable worker failures and reject success exits reporting failure."""

    result = dict(benchmark.EmptyCase(5, 0), error={"type": "ImportError", "message": "missing"})
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1, json.dumps(result), "")))
    assert benchmark.RunChild(5, 0, 1) == result

    with pytest.raises(ValueError):
        benchmark.ValidateWorker(result, benchmark.EmptyCase(5, 0), 0)


def test_FailedCaseDoesNotDiscardLaterCases(monkeypatch):
    """Preserve independent observations after a worker failure."""

    monkeypatch.setattr(benchmark, "RunChild", Mock(side_effect=[benchmark.EmptyCase(5, 0), dict(benchmark.EmptyCase(6, 0), status="ok")]))
    report = benchmark.BuildReport([5, 6], 0, 1, 1)
    assert report["status"] == "error"
    assert len(report["cases"]) == 2


@pytest.mark.parametrize("arguments", [["--sizes", "0"], ["--worker", "1000001"], ["--repeat", "0"], ["--chunk-size", "0"], ["--timeout", "nan"], ["--timeout", "inf"]])
def test_InvalidCLIInputsFailBeforeLaunchingWorkers(arguments):
    """Reject invalid row counts and unbounded execution settings."""

    with pytest.raises(SystemExit) as error:
        benchmark.Main(arguments)

    assert error.value.code == 2


def test_OutputFailureRetainsJSONOnStdout(monkeypatch, tmp_path, capsys):
    """Keep evidence available when the requested output path cannot be written."""

    monkeypatch.setattr(benchmark, "BuildReport", Mock(return_value={"status": "ok", "cases": []}))
    assert benchmark.Main(["--sizes", "1", "--output", str(tmp_path / "missing" / "file.json")]) == 1
    assert json.loads(capsys.readouterr().out)["output_error"]["type"] == "FileNotFoundError"


def test_SourceIdentityHashesActualRuntimeAndRecipe():
    """Identify actual modern sources rather than silently using installed code."""

    identity = benchmark.SourceIdentity()
    assert "pricegenerator/generation.py" in identity["source_sha256"]
    assert "pricegenerator/streaming.py" in identity["source_sha256"]
    assert "tools/benchmark.py" in identity["source_sha256"]
    assert identity["declared_source_version"] is not None


def test_MissingDistributionAndGitRemainExplicit(monkeypatch):
    """Record unavailable optional metadata without inventing provenance."""

    monkeypatch.setattr(benchmark.metadata, "version", Mock(side_effect=benchmark.metadata.PackageNotFoundError))
    monkeypatch.setattr(benchmark.subprocess, "run", Mock(side_effect=FileNotFoundError("git missing")))
    assert all(value is None for value in benchmark.Environment()["dependencies"].values())
    assert benchmark.SourceIdentity()["git_commit"] is None


@pytest.mark.parametrize("target_platform,expected", [("linux", 2048), ("darwin", 2)])
def test_RssCounterUnitsAreNormalized(monkeypatch, target_platform, expected):
    """Use explicit bytes for supported process-lifetime RSS counters."""

    import sys

    resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=Mock(return_value=SimpleNamespace(ru_maxrss=2)))
    monkeypatch.setitem(sys.modules, "resource", resource)
    monkeypatch.setattr(sys, "platform", target_platform)
    assert benchmark.PeakRss() == expected


def test_ForeignRuntimeIsRejectedAndImportPathIsRestored(monkeypatch, tmp_path):
    """Refuse silently benchmarking another checkout and restore caller import state."""

    import sys

    original_path = list(sys.path)
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="does not belong"):
        benchmark.LoadRuntime()

    assert sys.path == original_path


def test_ImportFailureRestoresCallerPath(monkeypatch):
    """Clean import-path changes when the real runtime cannot be imported."""

    import sys

    original_path = list(sys.path)
    monkeypatch.setattr(benchmark.importlib, "import_module", Mock(side_effect=ImportError("injected")))

    with pytest.raises(ImportError, match="injected"):
        benchmark.LoadRuntime()

    assert sys.path == original_path
