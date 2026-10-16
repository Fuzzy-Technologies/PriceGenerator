"""Verify statistical formulas with hand vectors and deterministic finite-sample policy."""

from dataclasses import FrozenInstanceError
import json
import math
import random

import numpy as np
import pandas as pd
import pytest

from pricegenerator.analysis import ACF, Analyze, Describe, ProbabilityTolerance, ProportionInterval


def Frame(closes=(100, 110, 88, 132, 99)) -> pd.DataFrame:
    """Create valid canonical candles with independently known close returns."""

    return pd.DataFrame({"datetime": pd.date_range("2026-01-01", periods=len(closes), freq="h", tz="UTC"), "open": closes, "high": np.asarray(closes) + 1, "low": np.asarray(closes) - 1, "close": closes, "volume": np.arange(len(closes)) * 10})


def test_HandDistributionAndAcfVector() -> None:
    """A five-point arithmetic progression fixes moment, quantile and ACF conventions."""

    distribution = Describe([1, 2, 3, 4, 5], "hand")
    quantiles = dict(distribution.quantiles)

    assert distribution.mean.value == pytest.approx(3), "Arithmetic mean of 1..5 is 3."
    assert distribution.variance.value == pytest.approx(2.5), "Sample variance divides the centered sum 10 by 4."
    assert distribution.skewness.value == pytest.approx(0), "A symmetric distribution must have zero adjusted skew."
    assert distribution.excess_kurtosis.value == pytest.approx(-1.2), "Adjusted Fisher excess kurtosis for 1..5 is -1.2."
    assert quantiles[0.05].value == pytest.approx(1.2), "Linear 5% quantile interpolates one fifth of the first interval."
    assert distribution.lower_tail_mean.value == 1 and distribution.upper_tail_mean.value == 5, "Inclusive tail means require actual tail observations."
    assert [item.value for item in ACF([1, 2, 3, 4, 5], 4)] == pytest.approx([0.4, -0.1, -0.4, -0.4]), "ACF numerator must use global centering and denominator 10."


def test_ReturnDrawdownAndCouplingHandVector() -> None:
    """Known closes expose simple/log units, peak tracking and unrecovered duration."""

    report = Analyze(Frame(), acf_lags=2)
    distributions = {item.name: item for item in report.distributions}

    assert report.simple_returns[0] is None and report.return_reasons[0], "The first candle has no previous close."
    assert report.simple_returns[1:] == pytest.approx([0.1, -0.2, 0.5, -0.25]), "Simple returns must use adjacent close ratios."
    assert report.log_returns[1:] == pytest.approx([math.log(1.1), math.log(0.8), math.log(1.5), math.log(0.75)]), "Log returns must use the positive adjacent-price domain."
    assert report.drawdown == pytest.approx([0, 0, 0.2, 0, 0.25]), "Percentage drawdown must reset at each new high."
    assert report.maximum_drawdown.value == pytest.approx(0.25), "Maximum drawdown is a positive loss fraction."
    assert report.maximum_drawdown_duration_bars.value == 1, "Underwater duration counts observed bars."
    assert distributions["body_fraction"].mean.value == 0, "Doji bodies occupy zero of a nonzero candle range."
    assert distributions["upper_wick_fraction"].mean.value == pytest.approx(0.5), "Symmetric doji wicks each occupy half of the range."
    assert report.volume_range_correlation.value is None and report.volume_range_correlation.reason, "Constant ranges have undefined correlation."


def test_ExplicitDomainGapsAndConstantUndefinedStatistics() -> None:
    """Zero and negative prices must never produce hidden infinities or compressed ACF."""

    report = Analyze(Frame([2, 0, -1, 3]), acf_lags=2)
    constant = Describe([7, 7, 7, 7])
    empty = Describe([None, math.nan])

    assert report.simple_returns[2] is None and "zero" in report.return_reasons[2], "A zero previous close makes the simple return undefined."
    assert report.log_returns[1:] == (None, None, None), "Log returns require two strictly positive prices."
    assert all(item.value is None and "gaps" in item.reason for item in report.return_acf), "ACF must not join observations across domain gaps."
    assert report.maximum_drawdown.value is None and report.maximum_drawdown.reason, "Relative drawdown requires a strictly positive price path."
    assert constant.variance.value == 0 and constant.skewness.value is None and constant.excess_kurtosis.value is None, "Standardized moments are undefined for constants."
    assert empty.count == 0 and empty.excluded == 2 and empty.mean.reason, "Empty effective samples need exclusion counts and reasons."
    json.loads(report.ToJSON())


def test_ImmutabilityRngAndCadence() -> None:
    """Analysis must preserve canonical values, index, RNG streams and observed gaps."""

    frame = Frame()
    frame.index = [11, 22, 33, 44, 55]
    frame.loc[33:, "datetime"] += pd.Timedelta(hours=3)
    original = frame.copy(deep=True)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    report = Analyze(frame)
    pd.testing.assert_frame_equal(frame, original)
    np.testing.assert_equal(np.random.get_state(), numpy_state)

    assert random.getstate() == python_state, "Descriptive analysis must not consume global Python RNG."
    assert not report.cadence_regular, "Observed timestamp gaps must be reported."

    with pytest.raises(FrozenInstanceError):
        report.candle_count = 99

    copied = report.ToDict()
    copied["candle_count"] = 99

    assert report.candle_count == 5, "Serialization must not expose mutable internal report storage."


def test_FiniteSamplePolicyUsesSeededIndependentTrials() -> None:
    """Predeclared Hoeffding tolerance evaluates a rate rather than an exact p-value."""

    trials = 10000
    probability = 0.37
    confidence = 0.999
    rng = np.random.default_rng(20261016)
    count = int(np.sum(rng.random(trials) < probability))
    tolerance = ProbabilityTolerance(trials, confidence=confidence)
    band = ProportionInterval(count, trials, confidence=confidence)

    assert tolerance == pytest.approx(math.sqrt(math.log(2000) / 20000)), "Hoeffding tolerance must match its declared confidence and sample size."
    assert abs(count / trials - probability) <= tolerance, "A seeded independent event count must satisfy the predeclared finite-sample bound."
    assert band.lower <= probability <= band.upper, "The corresponding independent-trial interval must include the known event probability."
    assert ProbabilityTolerance(40000) < ProbabilityTolerance(10000), "Larger samples must tighten the same-confidence tolerance."


@pytest.mark.parametrize("values", [[], [1], [1, 1], [1, 2, 3]])
def test_SmallSamplesHaveExplicitReasons(values) -> None:
    """Insufficient sample sizes cannot fabricate skewness, kurtosis or lag values."""

    distribution = Describe(values)

    if len(values) < 4:
        assert distribution.excess_kurtosis.value is None and distribution.excess_kurtosis.reason, "Fourth-order estimates require at least four observations."

    assert ACF(values, 5)[4].reason, "Unavailable lags must explain their undefined value."


@pytest.mark.parametrize("count,trials,confidence", [(1, 0, 0.99), (-1, 5, 0.99), (6, 5, 0.99), (True, 5, 0.99), (1, 5, 1), (1, 5, True)])
def test_InvalidTolerancePoliciesFail(count, trials, confidence) -> None:
    """Invalid finite-sample policy inputs must fail before statistical evaluation."""

    with pytest.raises(ValueError):
        ProportionInterval(count, trials, confidence=confidence)


def test_ExtremeFiniteValuesRemainStrictJson() -> None:
    """Unrepresentable moments are null estimates rather than JSON Infinity."""

    distribution = Describe([-1e308, 1e308, -1e308, 1e308])
    report = Analyze(Frame([1e308, 1e-308, 1e308]))

    assert distribution.variance.value is None and distribution.variance.reason, "Overflowing sample variance must carry a reason."
    assert report.simple_returns[-1] is None and "overflow" in report.return_reasons[-1], "Unrepresentable returns must remain explicit gaps."
    assert "Infinity" not in report.ToJSON() and "NaN" not in report.ToJSON(), "Strict reports must contain only standard JSON numbers or null."


def test_EmptyAndInvalidLagRequestsFail() -> None:
    """Reject empty canonical analysis and invalid lag configuration explicitly."""

    with pytest.raises(ValueError, match="at least one"):
        Analyze(Frame([]))

    with pytest.raises(ValueError, match="lags"):
        Analyze(Frame(), acf_lags=True)


def test_CanonicalWideTimestampRangeDoesNotOverflowTimedelta() -> None:
    """Valid canonical dates can span more than pandas Timedelta's 292-year range."""

    frame = Frame([1, 2])
    frame["datetime"] = pd.to_datetime(["1700-01-01", "2200-01-01"], utc=True)
    report = Analyze(frame)

    assert report.cadence_regular and report.path.elapsed_seconds == 15778454400, "Elapsed time must use exact Python integer nanosecond differences."


def test_PairedOutlierEventsSeparateTailAndCandleFrequencies() -> None:
    """Independent masks fix upper/lower, union and intersection event semantics."""

    from pricegenerator.analysis import SummarizeOutlierEvents

    upper = [True, False, True, False]
    lower = [False, True, True, False]
    original_upper = list(upper)
    summary = SummarizeOutlierEvents(upper, lower, definition="Fixture flags identify two explicitly observed tail events")

    assert (summary.upper_count, summary.lower_count, summary.either_count, summary.both_count) == (2, 2, 3, 1), "Per-candle union and intersection cannot be replaced by per-tail counts."
    assert [summary.upper_frequency.value, summary.lower_frequency.value, summary.either_frequency.value, summary.both_frequency.value] == [0.5, 0.5, 0.75, 0.25], "Every frequency uses the number of paired candles as its denominator."
    assert upper == original_upper and summary.trials == 4, "Event summarization must not alter masks or invent candle observations."
    assert "confidence" not in summary.ToDict(), "Descriptive masks cannot imply an independence-based confidence claim."

    with pytest.raises(FrozenInstanceError):
        summary.trials = 99


@pytest.mark.parametrize("upper,lower,definition", [([True], [], "known"), ([1], [False], "known"), ([None], [False], "known"), ([True], [float("nan")], "known"), ([], [], " "), ([], [], None)])
def test_InvalidPairedOutlierMasksFail(upper, lower, definition) -> None:
    """Reject unaligned, numeric, missing or unexplained event masks explicitly."""

    from pricegenerator.analysis import SummarizeOutlierEvents

    with pytest.raises(ValueError):
        SummarizeOutlierEvents(upper, lower, definition=definition)


def test_EmptyPairedOutlierMasksHaveUndefinedFrequencies() -> None:
    """An empty event observation set has zero counts and no frequency estimate."""

    from pricegenerator.analysis import SummarizeOutlierEvents

    result = SummarizeOutlierEvents(np.array([], dtype=bool), [], definition="No event observations supplied")

    assert result.trials == result.either_count == result.both_count == 0, "No supplied events cannot create trials or successes."
    assert result.upper_frequency.value is None and result.upper_frequency.reason, "An empty denominator must remain explicitly undefined."
