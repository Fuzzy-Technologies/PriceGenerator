"""Verify market-reference comparison provenance, explicit assumptions and unfitted inputs."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.io import WriteCSV
from pricegenerator.scenario import Fingerprint, Replay
from tools import compare_market


ROOT = Path(__file__).resolve().parents[1]


def CanonicalFile(tmp_path):
    """Create an independent canonical reference with a deliberately different price scale."""

    path = tmp_path / "reference.csv"
    frame = Generate(GenerationConfig(horizon=12, seed=815, initial_price=320, timeframe_seconds=86400))
    WriteCSV(frame, path)

    return path, frame


def test_CanonicalSourceHashWindowAndCompactSummary(tmp_path) -> None:
    """Hash the exact file bytes and selected inclusive rows without raw-vector output."""

    path, frame = CanonicalFile(tmp_path)
    config = GenerationConfig(horizon=7, seed=74)
    result = compare_market.BuildComparison(path, config=config, start=frame.datetime.iloc[2].isoformat(), end=frame.datetime.iloc[8].isoformat())
    source = result["reference"]
    reference = frame.iloc[2:9].reset_index(drop=True)
    comparison = result["comparison"]

    assert source["file_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(), "Source identity must hash the same file bytes that were parsed."
    assert source["canonical_fingerprint"] == Fingerprint(reference), "Selected data fingerprint must include exactly the declared UTC window."
    assert source["total_source_rows"] == 12 and source["selected_rows"] == 7, "Both source and selected sample sizes must remain visible."
    assert source["selected_row_positions_zero_based_inclusive"] == [2, 8], "Inclusive window positions must be independently auditable."
    assert "simple_returns" not in comparison["reference_analysis"], "Compact evidence must omit observation-sized return vectors."
    assert len(comparison["reference_analysis"]["squared_return_acf"]) == 10, "Selected evidence must retain temporal diagnostics."
    assert result["scenario_manifest"]["configuration"] == config.ToDict(), "Window choice must not change generator inputs."
    assert all(metric["within_tolerance"] is None for metric in comparison["metrics"]), "No supplied thresholds means no acceptance decisions."
    assert set(result["recipe"]["implementation_source_sha256"]) >= {"tools.compare_market", "pricegenerator.models", "pricegenerator.analysis"}, "Recipe provenance must identify actual model and estimator implementations."


def test_AfltAdapterRequiresDeclaredTimezoneAndKeepsTradingGaps(tmp_path) -> None:
    """The tool-only format adapter must not infer Moscow time or insert missing sessions."""

    path = tmp_path / "aflt.csv"
    path.write_text("2010.01.15,10:00,10,12,9,11,100\n2010.01.18,10:00:00,11,13,10,12,200\n", encoding="utf-8")

    with pytest.raises(ValueError, match="explicit --timezone"):
        compare_market.LoadReference(path, format="aflt-day")

    frame, source = compare_market.LoadReference(path, format="aflt-day", timezone="Europe/Moscow")

    assert frame.datetime.iloc[0] == pd.Timestamp("2010-01-15T07:00:00Z"), "A stated Moscow assumption must localize the supplied naive clock time."
    assert len(frame) == 2 and frame.datetime.iloc[1] - frame.datetime.iloc[0] == pd.Timedelta(days=3), "The weekend must remain an observed gap."
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "volume"], "The adapter must return canonical OHLCV without temporary columns."
    assert source["assume_timezone"] == "Europe/Moscow", "The caller's timezone assumption must remain in provenance."

    with pytest.raises(ValueError, match="header"):
        compare_market.LoadReference(path)


def test_NoFitNoReferenceDrivenConfigurationOrGlobalRng(tmp_path, monkeypatch) -> None:
    """Generation must receive exactly caller inputs regardless of reference price/activity."""

    path, frame = CanonicalFile(tmp_path)
    config = GenerationConfig(horizon=4, seed=932, initial_price=17, volume_base=41)
    real_generate = compare_market.Generate
    generate = Mock(wraps=real_generate)
    monkeypatch.setattr(compare_market, "Generate", generate)
    state = np.random.get_state()
    result = compare_market.BuildComparison(path, config=config)
    generate.assert_called_once_with(config)
    np.testing.assert_equal(np.random.get_state(), state)
    manifest = result["scenario_manifest"]
    replay = Replay(manifest)

    assert manifest["configuration"]["horizon"] == 4 != len(frame), "Reference length must not silently configure the synthetic horizon."
    assert manifest["configuration"]["initial_price"] == 17 != frame.open.iloc[0], "Reference prices must not silently fit the generator price level."
    assert result["procedure"] == {"parameter_fit": False, "calendar_alignment": False, "resampling": False, "seed_search": False, "price_or_volume_scaling": False, "generator_inputs": "Explicit complete configuration in scenario_manifest; defaults are library defaults, never inferred from reference data"}, "The report must state the intentionally unfitted comparison procedure."
    assert Fingerprint(replay) == manifest["fingerprint"], "The recorded scenario must replay exactly from its independent inputs."


def test_ExplicitToleranceResultsDoNotCreateGlobalAcceptance(tmp_path) -> None:
    """Only supplied metric tolerances receive decisions and failures remain visible."""

    path, _ = CanonicalFile(tmp_path)
    result = compare_market.BuildComparison(path, config=GenerationConfig(horizon=12), tolerances={"volume_mean": 0})
    metrics = {metric["name"]: metric for metric in result["comparison"]["metrics"]}

    assert metrics["volume_mean"]["within_tolerance"] is False, "Zero tolerance must expose independently generated volume differences."
    assert metrics["log_return_std"]["within_tolerance"] is None, "Unsupplied metric thresholds cannot receive a pass."
    assert "no universal" in result["comparison"]["decision_scope"], "Metric assessment must not become a universal realism claim."


@pytest.mark.parametrize("row", ["2010.01.11,10:00,1,2,0,1", "2010-01-11,10:00,1,2,0,1,2", "2010.01.11,10:00,1,2,0,1,NaN", "2010.02.30,10:00,1,2,0,1,2", "2010.01.11,10:00,1,0,2,1,2"])
def test_InvalidAfltInputFailsWithoutGuessing(tmp_path, row) -> None:
    """Reject malformed schema, dates, numeric tokens and candle geometry."""

    path = tmp_path / "bad.csv"
    path.write_text(row + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        compare_market.LoadReference(path, format="aflt-day", timezone="UTC")


@pytest.mark.parametrize("start,end", [("2001-01-01", None), ("2001-01-01T00:00:00", None), ("2000-01-01T00:00:00.0000000001Z", None), ("2000-01-01T00:00:00 UTC", None), ("2000-02-01T00:00:00Z", "2000-01-01T00:00:00Z"), ("2030-01-01T00:00:00Z", None)])
def test_InvalidOrEmptyReferenceWindowsFail(tmp_path, start, end) -> None:
    """Window selection must be explicit, ordered and nonempty."""

    path, _ = CanonicalFile(tmp_path)

    with pytest.raises(ValueError):
        compare_market.LoadReference(path, start=start, end=end)


@pytest.mark.parametrize("raw", ['{"seed":1,"seed":2}', '{"seed":NaN}', '[]'])
def test_InvalidDeclaredJsonDoesNotProduceEvidence(tmp_path, raw) -> None:
    """Duplicate keys and nonstandard JSON must not undermine input provenance."""

    source, _ = CanonicalFile(tmp_path)
    config = tmp_path / "config.json"
    config.write_text(raw, encoding="utf-8")
    output = tmp_path / "evidence.json"

    with pytest.raises(SystemExit) as captured:
        compare_market.Main([str(source), "--config", str(config), "--output", str(output)])

    assert captured.value.code == 2 and not output.exists(), "Invalid declared inputs must fail before an output is written."


def test_CliRecordsConfigSourceAndWritesMatchingHumanReport(tmp_path, capsys) -> None:
    """The real CLI must retain complete inputs, source hashes and readable results."""

    source, _ = CanonicalFile(tmp_path)
    config = tmp_path / "config.json"
    config.write_text('{"horizon":8,"seed":741}', encoding="utf-8")
    output = tmp_path / "evidence.json"
    markdown = tmp_path / "evidence.md"
    result = compare_market.Main([str(source), "--config", str(config), "--output", str(output), "--markdown", str(markdown)])
    evidence = json.loads(output.read_text())

    assert result == 0, "Successful descriptive execution must not imply a tolerance-based global gate."
    assert markdown.read_text() == capsys.readouterr().out, "Console and saved Markdown must show the same complete report."
    assert evidence["declared_input_sources"]["configuration"]["file_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest(), "Configuration provenance must identify the exact declared bytes."
    assert "not assessed" in markdown.read_text() and "Parameters were not fitted" in markdown.read_text(), "Readable output must distinguish descriptive differences from acceptance."
    assert "python -m tools.compare_market" in evidence["command"], "Evidence must retain its actual generating command."


def test_OutputAliasesCannotDestroyReferenceOrInputs(tmp_path) -> None:
    """Check resolved paths and existing filesystem aliases before generating files."""

    source, _ = CanonicalFile(tmp_path)
    original = source.read_bytes()
    alias = tmp_path / "alias.json"
    alias.hardlink_to(source)

    with pytest.raises(SystemExit) as captured:
        compare_market.Main([str(source), "--output", str(alias)])

    assert captured.value.code == 2 and source.read_bytes() == original, "Output aliases must preserve every source byte."


def test_BundledAfltEvidenceIsDeterministicAndAuditable() -> None:
    """Execute the actual supplied reference fixture rather than a synthetic substitute."""

    source = ROOT / "tests" / "AFLT_day.csv"
    config = GenerationConfig(horizon=2775, seed=20261016, timeframe_seconds=86400,
                              start=datetime(2010, 1, 11, 7, tzinfo=timezone.utc))
    evidence = compare_market.BuildComparison(source, config=config, format="aflt-day", timezone="Europe/Moscow")
    reference = evidence["reference"]

    assert reference["total_source_rows"] == reference["selected_rows"] == 2775, "The full bundled AFLT fixture must be evaluated without dropping sessions."
    assert reference["file_sha256"] == "55419201cc5af61892a80df68f70b36e8dd6be9c859816e37f85a4a9227f4f09", "Changing the real reference bytes must invalidate its evidence identity."
    assert not evidence["comparison"]["reference_analysis"]["cadence_regular"], "Historical trading gaps must remain visible."
    assert evidence["comparison"]["synthetic_analysis"]["cadence_regular"], "The declared uniform synthetic cadence must remain separate from reference sessions."
    assert len(json.dumps(evidence)) < 35000, "Selected evidence size must remain bounded by diagnostics rather than observation count."


@pytest.mark.parametrize("tolerances", ['{"not_a_metric":1}', '{"volume_mean":true}', '{"volume_mean":-1}'])
def test_InvalidToleranceDeclarationsCannotProduceOutput(tmp_path, tolerances) -> None:
    """Unknown, boolean and negative tolerances must fail without a fake assessment."""

    source, _ = CanonicalFile(tmp_path)
    declared = tmp_path / "tolerances.json"
    declared.write_text(tolerances, encoding="utf-8")
    output = tmp_path / "evidence.json"

    with pytest.raises(SystemExit) as captured:
        compare_market.Main([str(source), "--tolerances", str(declared), "--output", str(output)])

    assert captured.value.code == 2 and not output.exists(), "Invalid thresholds must not create an acceptance artifact."


def test_WindowSubnanosecondPrecisionCannotIncludeAnEarlierCandle(tmp_path) -> None:
    """Reject a bound pandas would truncate instead of changing inclusive membership."""

    source = tmp_path / "nanoseconds.csv"
    source.write_text("datetime,open,high,low,close,volume\n2000-01-01T00:00:00.000000000Z,1,1,1,1,1\n2000-01-01T00:00:00.000000001Z,2,2,2,2,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ISO timestamps"):
        compare_market.LoadReference(source, start="2000-01-01T00:00:00.0000000001Z")

    frame, provenance = compare_market.LoadReference(source, start="2000-01-01T00:00:00.000000001Z")

    assert len(frame) == 1 and frame.close.iloc[0] == 2, "A valid nanosecond bound must retain exact inclusive selection."
    assert provenance["window"]["requested_start_utc"].endswith("000000001+00:00"), "Requested bound provenance must preserve all supported fractional digits."
