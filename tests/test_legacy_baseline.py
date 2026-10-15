"""Lock published OHLCV behavior and expose known defects without correcting it."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import random
import sys

import numpy as np
import pytest

from legacy_harness import (
    Fingerprint,
    GenerateLegacy,
    LegacyRuntime,
    LoadCases,
    OHLCV_COLUMNS,
    SerializePrices,
)


CASES = LoadCases()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_PublishedGoldenRows(case):
    """Protect exact generation, constructor draws and trend endpoint behavior."""

    model = GenerateLegacy(case["configuration"], case["seed"])
    rows = SerializePrices(model.prices, model.precision)
    assert rows == case["rows"], "Legacy output changed; classify a model change before replacing the golden rows"
    assert Fingerprint(rows) == case["sha256"], "Legacy canonical OHLCV fingerprint changed"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("seed", [0, 17, 42])
def test_OhlcvAndContinuityInvariants(case, seed):
    """Check structural contracts that hold for these explicit historical scenarios."""

    configuration = case["configuration"]
    model = GenerateLegacy(configuration, seed)
    prices = model.prices
    assert list(prices.columns) == OHLCV_COLUMNS, "Legacy OHLCV column order changed"
    assert len(prices) == max(configuration["horizon"] or 5, 5), "Legacy horizon coercion changed"
    assert np.isfinite(prices.iloc[:, 1:].to_numpy()).all(), "Generated OHLCV contains nonfinite numbers"
    assert (prices.high >= prices[["open", "close"]].max(axis=1)).all(), "A high is below its candle body"
    assert (prices.low <= prices[["open", "close"]].min(axis=1)).all(), "A low is above its candle body"
    assert (prices.high >= prices.low).all(), "A candle has reversed high and low"
    assert prices.close.between(model.minClose, model.maxClose).all(), "A close exceeds this scenario's configured bounds"
    assert prices.volume.between(1, model.maxVolume).all(), "Volume is outside the declared positive integer domain"
    assert np.equal(prices.volume, prices.volume.astype(int)).all(), "Legacy volume must be integral"
    assert np.array_equal(prices.open.iloc[1:], prices.close.iloc[:-1]), "An open does not equal the previous close"
    assert prices.datetime.is_monotonic_increasing and prices.datetime.is_unique, "Timestamps must increase uniquely"
    assert prices.datetime.iloc[0].isoformat() == configuration["timeStart"], "Explicit UTC start changed"
    assert (prices.datetime.diff().iloc[1:] == timedelta(seconds=configuration["timeframeSeconds"])).all(), "Timeframe spacing changed"

    if configuration["initClose"] is not None:
        assert prices.open.iloc[0] == round(configuration["initClose"], model.precision), "First open must equal rounded initClose"

    if not configuration["trendSplit"]:
        tolerance = 10 ** (-model.precision)
        assert ((prices.close - prices.open).abs() <= model.maxCandleBody + tolerance).all(), "Unsplit candle body exceeds configured maximum plus rounding tolerance"


def test_ReplayRestoresGlobalState():
    """Repeated characterization must neither depend on nor consume caller RNG state."""

    configuration = CASES[1]["configuration"]
    initial_state = random.getstate()
    first = SerializePrices(GenerateLegacy(configuration, 0).prices, configuration["precision"])
    assert random.getstate() == initial_state, "The harness leaked global random consumption"
    second = SerializePrices(GenerateLegacy(configuration, 0).prices, configuration["precision"])
    assert first == second, "Seed zero must replay the same historical sequence"
    assert random.getstate() == initial_state, "Replay changed the caller's global random state"


def test_PublishedIndicatorVectors():
    """Preserve real historical indicator outputs for optional-backend migration checks."""

    fixture = json.loads(Path(__file__).with_name("legacy_indicators.json").read_text(encoding="utf-8"))
    model = GenerateLegacy(fixture["configuration"], fixture["seed"])

    with LegacyRuntime(fixture["seed"]):
        model.GetStatistics()

    for name, expected in fixture["indicators"].items():
        if "." in name:
            table, column = name.split(".")
            actual = model.stat[table][column]

        else:
            actual = model.prices[name]

        expected = np.array([np.nan if value is None else value for value in expected], dtype=float)
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12, equal_nan=True, err_msg=f"Legacy {name} indicator changed")


def test_RuntimeRestoresStateAfterFailure():
    """Exceptions must restore logging, stderr, timezone lookup and global RNG state."""

    # Bootstrap through the helper so this test also works first in a fresh process.
    with LegacyRuntime(0) as module:
        pass

    initial_state = random.getstate()
    initial_timezone = module.tzlocal
    initial_level = module.uLogger.level
    initial_stderr = sys.stderr

    with pytest.raises(RuntimeError, match="intentional characterization failure"):
        with LegacyRuntime(123):
            random.random()
            raise RuntimeError("intentional characterization failure")

    assert random.getstate() == initial_state, "Failure leaked global RNG changes"
    assert module.tzlocal is initial_timezone, "Failure leaked the test timezone override"
    assert module.uLogger.level == initial_level, "Failure leaked the logger override"
    assert sys.stderr is initial_stderr, "Failure leaked the legacy stderr redirection"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="https://github.com/Fuzzy-Technologies/PriceGenerator/issues/64 (characterized in #46): legacy wick sampling can produce a negative low",
)
def test_KnownNegativeLowDefect():
    """Expose negative lows under positive close bounds without silently repairing 1.x."""

    configuration = deepcopy(CASES[1]["configuration"])
    configuration.update(
        minClose=1.0, maxClose=2.0, initClose=1.0, maxOutlier=5.0,
        maxCandleBody=0.1, outliersProb=1.0, precision=2, horizon=5,
    )
    model = GenerateLegacy(configuration, 0)
    assert (model.prices.low >= 0).all(), "Positive close bounds do not prevent negative legacy wicks"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="https://github.com/Fuzzy-Technologies/PriceGenerator/issues/63 (characterized in #46): trend endpoint correction bypasses maxCandleBody",
)
def test_KnownTrendBodyBoundDefect():
    """Expose the forced trend endpoint body jump while retaining published semantics."""

    configuration = deepcopy(CASES[2]["configuration"])
    configuration.update(horizon=10, trendSplit="up", splitCount=[10], maxCandleBody=0.1)
    model = GenerateLegacy(configuration, 0)
    assert ((model.prices.close - model.prices.open).abs() <= model.maxCandleBody + 0.01).all(), "Legacy trend endpoint exceeds maxCandleBody"
