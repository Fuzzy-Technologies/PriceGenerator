"""Verify immutable inputs, private replay and declared regime model statistics."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import math
import random

import numpy as np
import pandas as pd
import pytest

from pricegenerator import Generate, GenerationConfig
from pricegenerator.models import GenerateRows
from pricegenerator.scenario import Fingerprint


def test_DefaultsAreExplicitAndImmutable():
    """Configuration construction consumes no random state and has fixed UTC time."""

    state = random.getstate()
    config = GenerationConfig()
    assert random.getstate() == state, "Configuration consumed global random state"
    assert config.start == datetime(2000, 1, 1, tzinfo=timezone.utc), "Default start depends on wallclock"
    assert GenerationConfig.FromDict(config.ToDict()) == config, "Complete configuration did not serialize"

    with pytest.raises(FrozenInstanceError):
        config.seed = 1


def test_SeedZeroReplayAndNoninterference():
    """Private seeds replay exactly across unrelated generation and host RNG draws."""

    config = GenerationConfig(seed=0, horizon=30)
    state = random.getstate()
    first = Generate(config)
    Generate(replace(config, seed=1))
    assert random.getstate() == state, "Generate consumed global random state"
    random.Random(99).random()
    pd.testing.assert_frame_equal(first, Generate(config))
    assert not first.equals(Generate(replace(config, seed=1))), "Distinct seeds generated identical scenarios"
    assert Fingerprint(first) == "58133dd747d104337a3c7be6f58df9bf5526ba214a427347a06b2efaad222eb6", "Versioned regime_v2 seeded output changed"


def test_GenerationCanonicalStructureAndContinuity():
    """Prices stay in-domain, opens remain continuous and timestamps honor input UTC."""

    start = datetime(2024, 2, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    config = GenerationConfig(seed=-7, horizon=300, start=start, timeframe_seconds=17)
    data = Generate(config)
    assert list(data) == ["datetime", "open", "high", "low", "close", "volume"], "Canonical fields changed"
    assert str(data.datetime.dtype) == "datetime64[ns, UTC]", "Generation did not normalize UTC nanoseconds"
    assert all(str(dtype) == "float64" for dtype in data.dtypes.iloc[1:]), "Numeric schema changed"
    assert data.datetime.iloc[0].isoformat() == "2024-02-01T00:00:00+00:00", "UTC conversion changed the instant"
    assert (data.datetime.diff().iloc[1:] == pd.Timedelta(seconds=17)).all(), "Cadence differs from config"
    assert np.array_equal(data.open.iloc[1:], data.close.iloc[:-1]), "Open/previous-close continuity failed"
    assert data.open.iloc[0] == config.initial_price, "First open differs from explicit price"
    assert np.isfinite(data.iloc[:, 1:]).all().all(), "Generation produced nonfinite values"
    assert data.iloc[:, 1:5].ge(config.price_floor).all().all(), "Positive price domain failed"
    assert data.volume.gt(0).all() and data.volume.le(config.volume_ceiling).all(), "Volume domain failed"


@pytest.mark.parametrize("changes", [
    {"seed": True}, {"seed": None}, {"horizon": 0}, {"horizon": 1.5}, {"horizon": 1_000_001},
    {"timeframe_seconds": 0}, {"timeframe_seconds": 0.5}, {"timeframe_seconds": 10**100},
    {"start": datetime(2020, 1, 1)}, {"start": "2020-01-01"},
    {"start": datetime(2262, 1, 1, tzinfo=timezone.utc)},
    {"start": pd.Timestamp("2024-01-01T00:00:00.123456789Z")},
    {"model": "legacy_v1"}, {"initial_price": 0}, {"initial_price": math.nan}, {"initial_price": 10**1000},
    {"volatility": math.inf}, {"volatility": True}, {"volatility": -1}, {"volatility": 3},
    {"price_floor": 1e12}, {"price_floor": 1e90, "price_ceiling": math.nextafter(1e90, math.inf), "initial_price": 1e90}, {"price_ceiling": 1e101}, {"initial_price": 1e14},
    {"drift": -3}, {"regime_scale": 0}, {"regime_persistence": -0.1},
    {"shock_probability": 1.1}, {"wick_outlier_probability": -1}, {"volume_persistence": 2},
    {"volume_base": 0}, {"volume_ceiling": 1},
])
def test_InvalidConfigurationFailsEarly(changes):
    """Reject inputs before partial output, coercion, overflow or model selection."""

    with pytest.raises(ValueError):
        GenerationConfig(**changes)


def test_InvalidDeserializationAndWrongAPIType():
    """Produce useful errors for malformed serialized config and API misuse."""

    with pytest.raises(ValueError, match="ISO"):
        GenerationConfig.FromDict({"start": "invalid"})

    with pytest.raises(ValueError, match="microsecond"):
        GenerationConfig.FromDict({"start": "2024-01-01T00:00:00.123456789Z"})

    with pytest.raises(ValueError, match="Invalid generation"):
        GenerationConfig.FromDict({"unknown": 1})

    with pytest.raises(TypeError, match="GenerationConfig"):
        Generate({"seed": 0})


def test_ExtremeSupportedParametersRemainFiniteAndBounded():
    """Reflection and wick boundaries survive extreme supported shocks and volumes."""

    config = GenerationConfig(
        horizon=2000, price_floor=1e-100, price_ceiling=1e100, initial_price=1e100,
        drift=2, volatility=2, regime_scale=100, regime_persistence=0,
        shock_probability=1, shock_scale=100, wick_scale=100,
        wick_outlier_probability=1, wick_outlier_scale=100,
        volume_base=1e100, volume_ceiling=1e100, volume_sigma=2,
        volume_return_coupling=10, volume_persistence=1,
    )
    data = Generate(config)
    assert np.isfinite(data.iloc[:, 1:]).all().all(), "Supported extremes overflowed"
    assert data.iloc[:, 1:5].ge(config.price_floor).all().all(), "Extreme low crossed the price floor"
    assert data.iloc[:, 1:5].le(config.price_ceiling).all().all(), "Extreme high crossed the price ceiling"
    assert data.volume.le(config.volume_ceiling).all(), "Extreme activity exceeded volume ceiling"


def test_FlatModelAndDriftHaveNoEndpointRewrite():
    """Every drift-only candle follows the same formula, including the final candle."""

    flat = Generate(GenerationConfig(horizon=10, volatility=0, drift=0, volume_sigma=0))
    assert (flat.iloc[:, 1:5] == 100).all().all(), "Zero innovations did not produce flat candles"
    config = GenerationConfig(horizon=25, volatility=0, drift=0.01, volume_sigma=0)
    data = Generate(config)
    returns = np.log(data.close / data.open)
    np.testing.assert_allclose(returns, 0.01, atol=1e-14, rtol=0, err_msg="A drift candle was rewritten to enforce an endpoint")


def test_PerTailOutlierProbabilitiesMatchDeclaredMixture():
    """Independent upper/lower Bernoulli tails match six-sigma finite-sample bounds."""

    count = 30_000
    probability = 0.2
    config = GenerationConfig(
        horizon=count, volatility=0.001, regime_scale=1, shock_probability=0,
        wick_scale=1, wick_outlier_probability=probability, wick_outlier_scale=10,
        volume_return_coupling=0,
    )
    rows = np.array(list(GenerateRows(config, random.Random(8128))))
    upper = np.log(rows[:, 1] / np.maximum(rows[:, 0], rows[:, 3])) / config.volatility
    lower = np.log(np.minimum(rows[:, 0], rows[:, 3]) / rows[:, 2]) / config.volatility
    expected = (1 - probability) * math.erfc(3 / math.sqrt(2)) + probability * math.erfc(0.3 / math.sqrt(2))
    tolerance = 6 * math.sqrt(expected * (1 - expected) / count)

    for observed in (np.mean(upper > 3), np.mean(lower > 3)):
        assert abs(observed - expected) < tolerance, "Tail exceedance differs from the declared Gaussian mixture"

    assert abs(np.corrcoef(upper > 3, lower > 3)[0, 1]) < 0.03, "Upper/lower tail events are coupled"


def test_ReturnShockProbabilityAndVarianceSemantics():
    """Return variance matches the independently sampled shock mixture within bounds."""

    count = 40_000
    config = GenerationConfig(
        horizon=count, volatility=0.001, regime_scale=1, shock_probability=0.2,
        shock_scale=5, wick_scale=0, volume_return_coupling=0,
    )
    rows = np.array(list(GenerateRows(config, random.Random(99))))
    returns = np.log(rows[:, 3] / rows[:, 0])
    expected_variance = config.volatility**2 * (1 + config.shock_probability * config.shock_scale**2)
    assert abs(np.mean(returns)) < 6 * math.sqrt(expected_variance / count), "Return mean differs from zero-drift model"
    assert abs(np.var(returns) / expected_variance - 1) < 0.08, "Shock probability/scale variance semantics changed"


def test_RegimeClusteringAndVolumeActivityCoupling():
    """Persistent regimes and activity coupling produce reproducible positive dependence."""

    config = GenerationConfig(horizon=30_000, volatility=0.001, regime_persistence=0.98, regime_scale=5, shock_probability=0, volume_sigma=0.1)
    data = Generate(config)
    returns = np.log(data.close / data.open).to_numpy()
    normalized_activity = np.abs(returns)
    clustering = np.corrcoef(normalized_activity[:-1], normalized_activity[1:])[0, 1]
    assert clustering > 0.2, "Persistent volatility regimes lost measurable absolute-return dependence"
    fixed = Generate(replace(config, regime_scale=1))
    activity = np.abs(np.log(fixed.close / fixed.open))
    correlation = np.corrcoef(activity, np.log(fixed.volume))[0, 1]
    assert correlation > 0.95, "Configured volume/activity coupling disappeared"


class RecordingRandom:
    """Record explicit model uniforms independently of Gaussian internals."""

    def __init__(self, seed):
        """Own one real private engine and a reproducible event trace."""

        self.engine = random.Random(seed)
        self.uniforms = []

    def random(self):
        """Record Bernoulli inputs without intercepting Gaussian engine draws."""

        value = self.engine.random()
        self.uniforms.append(value)

        return value

    def gauss(self, mean, sigma):
        """Use the actual stdlib normal sampler, including its cached state."""

        return self.engine.gauss(mean, sigma)


def test_OneHundredThousandIndependentModelEventTraces():
    """Check each Bernoulli probability with predeclared six-sigma count bounds."""

    count = 100_000
    config = GenerationConfig(horizon=count, regime_persistence=0.9, shock_probability=0.2, wick_outlier_probability=0.3)
    rng = RecordingRandom(20261016)

    for _ in GenerateRows(config, rng):
        pass

    trace = np.asarray(rng.uniforms).reshape(count, 4)
    events = [trace[:, 0] >= 0.9, trace[:, 1] < 0.2, trace[:, 2] < 0.3, trace[:, 3] < 0.3]

    for event, probability in zip(events, (0.1, 0.2, 0.3, 0.3)):
        expected = count * probability
        tolerance = 6 * math.sqrt(count * probability * (1 - probability))
        assert abs(np.count_nonzero(event) - expected) < tolerance, "A declared per-bar/per-tail probability changed"

    assert abs(np.corrcoef(events[2], events[3])[0, 1]) < 0.02, "Independent tail Bernoulli draws became coupled"
