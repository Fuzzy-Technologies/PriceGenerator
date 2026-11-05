"""Exercise actual v2 generation/replay adapters and deterministic failure paths."""

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV
from pricegenerator.cli import Main
from pricegenerator.monte_carlo import DerivePathSeed


def test_GenerateReplayAndValidateRealCSV(tmp_path, capsys):
    """Seed zero flows through the CLI, full manifest and canonical CSV replay."""

    source, replay, manifest = (tmp_path / name for name in ("prices.csv", "replayed.csv", "scenario.json"))
    assert Main(["generate", "--seed", "0", "--horizon", "7", "--output", str(source), "--manifest", str(manifest)]) == 0, "Generation command failed"
    assert Main(["replay", str(manifest), "--output", str(replay)]) == 0, "Replay command failed"
    pd.testing.assert_frame_equal(ReadCSV(source), ReadCSV(replay))
    pd.testing.assert_frame_equal(ReadCSV(source), Generate(GenerationConfig(seed=0, horizon=7)))
    assert json.loads(manifest.read_text())["seed"] == 0, "CLI discarded seed zero"
    assert Main(["validate", str(source), "--timeframe-seconds", "3600", "--no-gaps"]) == 0, "Validation command failed"
    assert json.loads(capsys.readouterr().out)["rows"] == 7, "Validation summary lost row count"


def test_ConfigFileAndExplicitOverrides(tmp_path):
    """Full JSON configuration supports intentional common CLI overrides."""

    config_path, output = tmp_path / "config.json", tmp_path / "prices.csv"
    config_path.write_text(json.dumps(GenerationConfig(seed=99, horizon=10).ToDict()))
    Main(["generate", "--config", str(config_path), "--seed", "0", "--horizon", "1", "--start", "2024-01-01T03:00:00+03:00", "--timeframe-seconds", "60", "--output", str(output)])
    actual = ReadCSV(output)
    assert len(actual) == 1, "Explicit horizon did not override JSON"
    assert actual.datetime.iloc[0].isoformat() == "2024-01-01T00:00:00+00:00", "Explicit timestamp instant changed"


@pytest.mark.parametrize("command", [
    ["--horizon", "5"], ["generate", "--output", "x.csv", "--seed", "invalid"],
    ["generate", "--output", "x.csv", "--horizon", "0"],
    ["generate", "--output", "x.csv", "--start", "2024-01-01"],
])
def test_InvalidAndHistoricalCommandsFail(command, tmp_path, monkeypatch):
    """Reject old flags and invalid inputs without producing scenario files."""

    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        Main(command)

    assert error.value.code == 2, "CLI input errors must use argparse status 2"
    assert not (tmp_path / "x.csv").exists(), "Invalid configuration wrote partial output"


def test_InputAndOutputCollisionsFailBeforeWriting(tmp_path):
    """Protect direct aliases and filesystem hardlinks from destructive overwrite."""

    source = tmp_path / "config.json"
    source.write_text("{}")
    alias = tmp_path / "alias.json"
    alias.hardlink_to(source)

    for output in (source, alias):
        with pytest.raises(SystemExit):
            Main(["generate", "--config", str(source), "--output", str(output)])

    assert source.read_text() == "{}", "CLI overwrote an aliased input file"

    with pytest.raises(SystemExit):
        Main(["generate", "--output", str(tmp_path / "x.csv"), "--manifest", str(tmp_path / "x.csv")])


def test_CLIReportsMalformedJSONAndIOErrors(tmp_path):
    """Expected input and filesystem failures remain readable command errors."""

    invalid = tmp_path / "invalid.json"

    for serialized in ("{", "[]", '{"seed":0,"seed":1}', '{"drift":NaN}', '{"drift":Infinity}'):
        invalid.write_text(serialized)

        with pytest.raises(SystemExit):
            Main(["generate", "--config", str(invalid), "--output", str(tmp_path / "x.csv")])

    with pytest.raises(SystemExit):
        Main(["replay", str(invalid), "--output", str(tmp_path / "x.csv")])

    with pytest.raises(SystemExit):
        Main(["generate", "--output", str(tmp_path / "absent" / "x.csv")])


def test_ChartAdapterForwardsModernOptions(tmp_path, monkeypatch):
    """CLI preparation preserves the explicit chart boundary without opening browsers."""

    import types

    source = tmp_path / "prices.csv"
    output, report = tmp_path / "chart.svg", tmp_path / "report.md"
    WriteCSV(Generate(GenerationConfig(horizon=2)), source)
    captured = {}

    def Chart(data, destination, **options):
        """Capture the adapter contract independently of optional rendering code."""

        captured.update(options)
        captured["rows"], captured["destination"] = len(data), destination

        return Path(destination)

    monkeypatch.setitem(sys.modules, "pricegenerator.rendering.api", types.SimpleNamespace(Chart=Chart))
    Main(["chart", str(source), "--output", str(output), "--format", "svg", "--no-view", "--analysis", "--summary", "Example", "--report", str(report)])
    assert captured["view"] is False and captured["analysis"] is True, "Chart options were discarded"
    assert captured["rows"] == 2 and captured["destination"] == output, "Chart adapter received the wrong data/path"
    assert captured["summary"] == ("Example",) and captured["markdown_report"] == report, "Report options were discarded"


def test_ModuleEntryPointHasOnlyModernCommands():
    """Python module invocation reaches the new adapter in a fresh process."""

    completed = subprocess.run([sys.executable, "-m", "pricegenerator", "--help"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, f"Module entry point failed: {completed.stderr}"
    assert "generate,replay,validate,analyze,chart,monte-carlo,replay-ensemble" in completed.stdout, "Module entry point did not expose modern commands"
    assert "--legacy" not in completed.stdout, "Historical command alias remains active"


def test_EnsembleCLIExportsReportManifestAndRealPathChart(tmp_path):
    """Export real path-zero candles and reproduce the report with two workers."""

    output, manifest, chart, replay = (tmp_path / name for name in ("report.json", "experiment.json", "quantiles.svg", "replay.json"))
    assert Main([
        "monte-carlo", "--seed", "42", "--horizon", "16", "--paths", "7",
        "--output", str(output), "--manifest", str(manifest), "--chart", str(chart),
    ]) == 0, "Monte Carlo CLI failed to write the ensemble artifacts"
    assert Main(["replay-ensemble", str(manifest), "--workers", "2", "--output", str(replay)]) == 0, "Parallel replay CLI failed"
    assert output.read_bytes() == replay.read_bytes(), "Worker count changed the serialized result"

    actual_path = Generate(GenerationConfig(seed=DerivePathSeed(42, 0), horizon=16))
    svg = chart.read_text(encoding="utf-8")
    assert "Monte Carlo | regime_v2 | 7 paths" in svg, "The chart must identify the model and sample size"
    assert "Candles and volume: ensemble path 0" in svg, "The chart must disclose the candle source"
    assert "pointwise synthetic range" in svg, "The chart must describe the quantile range"
    assert f"C={actual_path.close.iloc[0]} " in svg, "Displayed candles must come from an actual derived path"

    for level in ("05", "50", "95"):
        assert f'data-series="close-p{level}"' in svg, f"The chart lost the P{level} quantile"


def test_EnsembleCLIProtectsManifestAndConfiguration(tmp_path):
    """Reject output aliases and a tampered replay before writing results."""

    config, manifest, output = (tmp_path / name for name in ("config.json", "manifest.json", "report.json"))
    config.write_text('{"seed": 0, "horizon": 2}', encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        Main(["monte-carlo", "--paths", "2", "--config", str(config), "--manifest", str(config)])

    assert error.value.code == 2 and json.loads(config.read_text())["horizon"] == 2, "The CLI overwrote an aliased configuration"
    Main(["monte-carlo", "--paths", "2", "--config", str(config), "--manifest", str(manifest)])
    valid = json.loads(manifest.read_text())

    with pytest.raises(SystemExit) as error:
        Main(["replay-ensemble", str(manifest), "--output", str(manifest)])

    assert error.value.code == 2 and json.loads(manifest.read_text()) == valid, "Replay overwrote its input manifest"
    manifest.write_text(json.dumps({**valid, "path_count": 3}), encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        Main(["replay-ensemble", str(manifest), "--output", str(output)])

    assert error.value.code == 2 and not output.exists(), "Tampered replay wrote a result"
