"""Test profile provenance, withheld evaluation and explicit comparison gates."""

from dataclasses import FrozenInstanceError
import json

import numpy as np
import pandas as pd
import pytest

from pricegenerator.calibration import Calibrate, ChronologicalSplit, ExtractProfile, Profile
from pricegenerator.config import GenerationConfig
from pricegenerator.evaluation import BootstrapMeanInterval, Compare
from pricegenerator.extended_models import Scripted, ScriptedConfig, ScriptStep
from pricegenerator.scenario import Replay


def _ShiftedFixture() -> pd.DataFrame:
    """Create an intentionally changed withheld drift and volume regime."""

    return Scripted(ScriptedConfig(count=40, drift=.001, volume=100,
                                  steps=(ScriptStep(30, drift=.04, volume=900),)))


def test_ProfileRoundTripAndDeclaredRestrictions() -> None:
    """Make observable moments reproducible without implying latent identification."""

    training, _ = ChronologicalSplit(_ShiftedFixture())
    profile = ExtractProfile(training)
    loaded = Profile.FromDict(json.loads(json.dumps(profile.ToDict())))
    assert loaded == profile and loaded.Reference() == profile.Reference(), "Profile roundtrip must preserve all source and estimator identity"
    assert profile.drift == pytest.approx(.001), "Profile drift must fit training candle-body log returns"
    assert profile.volume_base == 100, "Holdout volume must not contaminate training profile"
    config = profile.ToConfig(GenerationConfig(seed=9, wick_scale=.7))
    assert config.shock_probability == 0 and config.regime_scale == 1 and config.volume_sigma == 0, "Fitted submodel restrictions must be explicit"
    assert config.seed == 9 and config.wick_scale == .7, "Unfitted base inputs must remain explicit assumptions"
    assert "wick_scale" in profile.ManifestMetadata()["unidentified_parameters"], "Unfitted wick parameters must not masquerade as estimates"

    with pytest.raises(FrozenInstanceError):
        profile.drift = .5


@pytest.mark.parametrize("field,value", [("volatility", float("nan")), ("volume_base", 0),
                                         ("source_rows", True), ("schema_version", True), ("model", "legacy_v1"),
                                         ("source_fingerprint", "bad"), ("source_end", "2000-01-01"),
                                         ("timeframe_seconds", 1), ("timeframe_seconds", 1e308),
                                         ("drift", 10 ** 1000), ("estimator", "unknown"),
                                         ("source_start", pd.Timestamp("2000-01-01T00:00:00Z"))])
def test_ProfileRejectsUnusableSerialization(field: str, value) -> None:
    """Reject unsupported versions, nonfinite values and inconsistent provenance."""

    payload = ExtractProfile(_ShiftedFixture()).ToDict()
    payload[field] = value

    with pytest.raises(ValueError):
        Profile.FromDict(payload)


def test_ProfileRejectsUnknownFieldsAndModels() -> None:
    """Prevent silently accepting opaque state and incompatible model profiles."""

    profile = ExtractProfile(_ShiftedFixture())

    with pytest.raises(ValueError, match="fields"):
        Profile.FromDict({**profile.ToDict(), "hidden_state": [1, 2]})

    incomplete = profile.ToDict()
    del incomplete["data_schema"]

    with pytest.raises(ValueError, match="fields"):
        Profile.FromDict(incomplete)

    with pytest.raises(ValueError, match="regime_v2"):
        ExtractProfile(_ShiftedFixture(), model="scripted_v1")

    with pytest.raises(ValueError, match="regular"):
        ExtractProfile(_ShiftedFixture().drop(index=3).reset_index(drop=True))

    with pytest.raises(TypeError, match="GenerationConfig"):
        profile.ToConfig({})

    with pytest.raises(ValueError, match="three"):
        ExtractProfile(_ShiftedFixture().iloc[:2])

    nonpositive = _ShiftedFixture()
    nonpositive[["open", "high", "low", "close"]] = 0

    with pytest.raises(ValueError, match="positive"):
        ExtractProfile(nonpositive)


def test_HoldoutZeroVolumeRemainsEvaluationOnly() -> None:
    """Accept a valid held-out volume domain without attempting to fit it."""

    training, holdout = ChronologicalSplit(_ShiftedFixture())
    holdout["volume"] = 0
    report = Calibrate(training, holdout)
    assert report.profile.volume_base == 100, "Evaluation volume must never alter the fitted positive volume base"
    assert next(metric for metric in report.holdout.metrics if metric.name == "volume_mean").reference == 0, "Held-out zero volume must remain in the independent report"


def test_CalibrationWithheldShiftDoesNotRefitAndManifestsReplay() -> None:
    """Expose changed withheld statistics while preserving training-only estimates."""

    training, holdout = ChronologicalSplit(_ShiftedFixture())
    report = Calibrate(training, holdout, tolerances={"log_return_mean": .01, "volume_mean": 10})
    assert report.profile == ExtractProfile(training), "Calibration must estimate parameters from training only"
    train_metrics = {metric.name: metric for metric in report.training.metrics}
    test_metrics = {metric.name: metric for metric in report.holdout.metrics}
    assert train_metrics["volume_mean"].within_tolerance is True, "Fitted training volume mean should match the restricted constant-volume model"
    assert test_metrics["volume_mean"].within_tolerance is False, "Withheld volume shift must remain visible instead of being fitted away"
    assert test_metrics["log_return_mean"].within_tolerance is False, "Withheld drift shift must remain visible"
    manifests = [json.loads(report.training_manifest_json), json.loads(report.holdout_manifest_json)]

    for manifest in manifests:
        assert manifest["metadata"]["profile_reference"] == report.profile.Reference(), "Each generated experiment must identify the exact fitted profile"
        assert len(Replay(manifest)) > 0, "Calibration scenario manifests must replay through the public generation contract"


def test_CalibrationRejectsOverlapTimeframeAndFractionErrors() -> None:
    """Enforce chronological separation before any profile fitting or generation."""

    frame = _ShiftedFixture()

    with pytest.raises(ValueError, match="overlap"):
        Calibrate(frame.iloc[:30], frame.iloc[29:])

    training, holdout = ChronologicalSplit(frame)
    changed = holdout.copy()
    changed["datetime"] = pd.date_range(holdout["datetime"].iloc[0], periods=len(holdout), freq="2h")

    with pytest.raises(ValueError, match="same timeframe"):
        Calibrate(training, changed)

    with pytest.raises(ValueError, match="whole-second"):
        subsecond = frame.copy()
        subsecond["datetime"] = pd.date_range(frame["datetime"].iloc[0], periods=len(frame), freq="500ms")
        Calibrate(*ChronologicalSplit(subsecond))

    with pytest.raises(ValueError, match="microsecond"):
        nanosecond = frame.copy()
        nanosecond["datetime"] += pd.Timedelta(nanoseconds=1)
        Calibrate(*ChronologicalSplit(nanosecond))

    with pytest.raises(ValueError, match="three"):
        Calibrate(training.iloc[:2], holdout)

    with pytest.raises(ValueError, match="regular"):
        Calibrate(training, holdout.drop(index=4).reset_index(drop=True))

    for fraction in (0, 1, float("nan"), .99):
        with pytest.raises(ValueError):
            ChronologicalSplit(frame, holdout_fraction=fraction)


def test_ComparisonTolerancesUndefinedMetricsAndNoImplicitAcceptance() -> None:
    """Evaluate only predeclared finite metrics and retain degenerate reasons."""

    data = Scripted(ScriptedConfig(count=10))
    report = Compare(data, data, tolerances={"volume_mean": 0, "volume_absolute_return_correlation": .1})
    metrics = {metric.name: metric for metric in report.metrics}
    assert metrics["volume_mean"].within_tolerance is True, "Equal observable metrics must pass zero tolerance"
    assert metrics["volume_absolute_return_correlation"].within_tolerance is None, "Undefined correlation cannot pass a tolerance"
    assert metrics["log_return_mean"].within_tolerance is None, "Metrics without selected tolerance must not receive an acceptance result"
    assert json.loads(json.dumps(report.ToDict()))["metric_version"] == "comparison_v1", "Reports must serialize reproducibly"

    for tolerances in ({"unknown": 1}, {"volume_mean": -1}, {"volume_mean": float("nan")}, {"volume_mean": True}):
        with pytest.raises(ValueError):
            Compare(data, data, tolerances=tolerances)


def test_BootstrapIntervalDeterminismConstantsAndEmpiricalQuantiles() -> None:
    """Check percentile mechanics against independently reconstructed IID draws."""

    values = np.array([1, 2, 5, 8.0])
    interval = BootstrapMeanInterval(values, seed=0, confidence=.9, resamples=1000)
    rng = np.random.Generator(np.random.PCG64(0))
    expected = np.array([values[rng.integers(0, 4, size=4)].mean() for _ in range(1000)])
    np.testing.assert_allclose([interval.lower, interval.upper], np.quantile(expected, [.05, .95]))
    assert interval == BootstrapMeanInterval(values, seed=0, confidence=.9, resamples=1000), "Same resampling inputs must reproduce interval exactly"
    constant = BootstrapMeanInterval([3.0] * 10, seed=0, block_length=3)
    assert constant.lower == constant.upper == 3, "A constant statistic must have a degenerate bootstrap interval"
    assert constant.ToDict()["block_length"] == 3, "Uncertainty reports must retain their declared dependence assumption"
    full_block = BootstrapMeanInterval(values, seed=0, block_length=4)
    assert full_block.lower == full_block.upper == values.mean(), "Full non-circular block can only resample the complete observed sequence"
    extreme = BootstrapMeanInterval([1e308, 1e308], seed=0, resamples=100)
    assert extreme.lower == extreme.upper == 1e308, "Finite constant observations must not overflow the mean or percentile interpolation"
    assert json.loads(json.dumps(extreme.ToDict(), allow_nan=False))["lower"] == 1e308, "Interval evidence must remain standard JSON for extreme finite observations"


@pytest.mark.parametrize("values,updates", [([1], {}), ([1, float("inf")], {}), ([[1, 2], [3, 4]], {}),
                                          ([1, 2], {"block_length": 3}), ([1, 2], {"confidence": 1}),
                                          ([1, 2], {"resamples": 99}), ([1, 2], {"seed": True})])
def test_BootstrapIntervalRejectsInvalidAssumptions(values, updates: dict) -> None:
    """Require declared finite observations and valid resampling controls."""

    settings = {"seed": 0, **updates}

    with pytest.raises(ValueError):
        BootstrapMeanInterval(values, **settings)
