"""Exercise bounded worker cleanup and chart benchmark evidence validation."""

import json
import signal
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import benchmark_charts


@pytest.mark.parametrize(("stdout", "returncode"), [
    ("not JSON", 1), ("[]", 0), ('{"status":"unknown"}', 0),
    ('{"status":"ok"}', 1), ('{"status":"error"}', 0),
    ('{"status":"ok","milliseconds":NaN}', 0),
])
def test_InvalidWorkerEvidenceFailsClosed(monkeypatch, tmp_path, stdout, returncode):
    """Malformed, contradictory or non-finite results cannot become observations."""

    process = Mock(returncode=returncode)
    process.communicate.return_value = (stdout, "diagnostic" * 1000)
    monkeypatch.setattr(benchmark_charts.subprocess, "Popen", Mock(return_value=process))
    result = benchmark_charts.RunJSON(["worker"], 1, tmp_path)

    assert result["error"]["type"] == "WorkerProtocolError", "Invalid transport must retain an explicit protocol failure"
    assert len(result["error"]["stderr_tail"]) <= 4000, "Retained worker diagnostics must remain bounded"


def test_SpawnFailureRemainsSerializable(monkeypatch, tmp_path):
    """Missing Node or Python executables yield evidence instead of a crash."""

    monkeypatch.setattr(benchmark_charts.subprocess, "Popen", Mock(side_effect=FileNotFoundError("missing runtime")))
    result = benchmark_charts.RunJSON(["worker"], 1, tmp_path)

    assert result["error"]["type"] == "FileNotFoundError", "The missing runtime must remain identifiable"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("isolate", [False, True])
def test_TimeoutTerminatesAndReapsWorkers(monkeypatch, tmp_path, isolate):
    """A bounded observation must terminate its owned process or process group."""

    process = Mock(pid=12345)
    process.communicate.side_effect = [subprocess.TimeoutExpired("worker", 1), ("", "")]
    monkeypatch.setattr(benchmark_charts.subprocess, "Popen", Mock(return_value=process))
    kill_group = Mock()
    monkeypatch.setattr(benchmark_charts.os, "killpg", kill_group, raising=False)
    result = benchmark_charts.RunJSON(["worker"], 1, tmp_path, isolate=isolate)

    if isolate and benchmark_charts.os.name == "posix":
        kill_group.assert_called_once_with(process.pid, signal.SIGKILL)

    else:
        process.kill.assert_called_once()

    assert process.communicate.call_count == 2, "Terminated workers must be reaped before returning"
    assert result["error"]["type"] == "TimeoutExpired", "Timeouts must not become fabricated performance data"


def test_WellFormedFailureIsPreserved(monkeypatch, tmp_path):
    """A real renderer's structured error must survive the orchestration layer."""

    expected = {"status": "error", "error": {"type": "ImportError", "message": "missing extra"}}
    process = Mock(returncode=1)
    process.communicate.return_value = (json.dumps(expected), "")
    monkeypatch.setattr(benchmark_charts.subprocess, "Popen", Mock(return_value=process))

    assert benchmark_charts.RunJSON(["worker"], 1, tmp_path) == expected, "Worker diagnostics must not be replaced"


def test_SuccessMustIdentifyRequestedSize(monkeypatch, tmp_path, capsys):
    """A success record from another size cannot be attached to this scenario."""

    monkeypatch.setattr(benchmark_charts, "SourceIdentity", Mock(return_value={}))
    monkeypatch.setattr(benchmark_charts, "RunJSON", Mock(return_value={"status": "ok", "requested_rows": 100}))
    exit_code = benchmark_charts.Main(["--sizes", "1000", "--source-root", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1, "Misidentified evidence must fail the command"
    assert report["cases"][0]["error"]["type"] == "WorkerProtocolError", "A mismatched worker must be reported explicitly"


def test_OutputFailureRetainsReport(monkeypatch, tmp_path, capsys):
    """A failed output write must retain machine-readable evidence on stdout."""

    monkeypatch.setattr(benchmark_charts, "SourceIdentity", Mock(return_value={}))
    monkeypatch.setattr(benchmark_charts, "RunJSON", Mock(return_value={"status": "ok", "requested_rows": 1000}))
    exit_code = benchmark_charts.Main(["--sizes", "1000", "--output", str(tmp_path / "missing" / "report.json")])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1, "Evidence write failure must change the process exit status"
    assert report["output_error"]["type"] == "FileNotFoundError", "The output failure must be actionable"


def test_SourceChangeInvalidatesMeasurements(monkeypatch, tmp_path, capsys):
    """A concurrent source edit must not receive an unqualified success record."""

    monkeypatch.setattr(benchmark_charts, "SourceIdentity", Mock(side_effect=[{"revision": "before"}, {"revision": "after"}]))
    monkeypatch.setattr(benchmark_charts, "RunJSON", Mock(return_value={"status": "ok", "requested_rows": 1000}))
    exit_code = benchmark_charts.Main(["--sizes", "1000", "--source-root", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1, "Concurrent edits must invalidate the observation"
    assert report["source_error"]["type"] == "SourceChangedError", "The reproducibility failure must remain explicit"
    assert report["cases"][0]["status"] == "ok", "Completed observations must remain available for diagnosis"


def test_FixtureUsesCanonicalDataWithoutLegacyModel():
    """The benchmark fixture is independent of all retired generator classes."""

    prices, overlay, markers = benchmark_charts.Fixture(1000)
    assert list(prices.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert len(prices) == len(overlay) == len(markers) == 1000
    assert overlay.Reference.isna().sum() == 19
    assert (markers.markersUpper == "Signal").sum() == 1


def test_MissingCanvasRuntimePreservesRealStaticExportEvidence(tmp_path):
    """A native Node spawn failure cannot turn completed static work into success."""

    pytest.importorskip("resvg_py")
    pytest.importorskip("PIL")
    arguments = SimpleNamespace(worker=1000, source_root=benchmark_charts.ROOT,
        work_directory=tmp_path, node=str(tmp_path / "missing-node"),
        canvas_module="@napi-rs/canvas", timeout=5)
    result = benchmark_charts.PythonCase(arguments)
    assert result["status"] == "error"
    assert result["canvas"]["error"]["type"] == "FileNotFoundError"
    assert result["stages"]["static_svg"]["candle_rows"] == 1000
    assert result["stages"]["static_png"]["format"] == "PNG"
    assert result["stages"]["static_jpeg"]["mode"] == "RGB"
    assert "legacy_bokeh_html" not in result["stages"]


def test_MissingExportBindingRetainsActionableFailure(monkeypatch, tmp_path):
    """Missing optional raster support produces explicit diagnostic evidence."""

    pytest.importorskip("PIL")
    from pricegenerator.rendering import exports

    def Missing(name):
        """Represent an absent resvg binding while preserving actual SVG output."""

        raise ImportError('Raster export requires: python -m pip install "pricegenerator[export]"')

    monkeypatch.setattr(exports, "_ExportModule", Missing)
    arguments = SimpleNamespace(worker=1000, source_root=benchmark_charts.ROOT,
        work_directory=tmp_path, node="node", canvas_module="@napi-rs/canvas", timeout=5)
    result = benchmark_charts.PythonCase(arguments)
    assert result["status"] == "error" and result["error"]["type"] == "ImportError"
    assert "pricegenerator[export]" in result["error"]["message"]
    assert result["stages"]["static_svg"]["candle_rows"] == 1000
    assert "static_png" not in result["stages"] and "canvas" not in result
