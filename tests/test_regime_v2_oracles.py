"""Check model equations with scripted draws and hand-computed OHLCV values."""

from collections.abc import Iterable
from math import exp

import pytest

from pricegenerator import GenerationConfig
from pricegenerator.models import GenerateRows


class ScriptedRandom:
    """Supply explicit uniform and standard normal draws in one fixed order."""

    def __init__(self, draws: Iterable[tuple[str, float]]) -> None:
        """Create a fresh draw stream and track exact consumption."""

        self._draws = iter(draws)

    def _Take(self, kind: str) -> float:
        """Fail on missing draws or a change in the documented call order."""

        draw = next(self._draws, None)
        assert draw is not None, f"Unexpected {kind} draw after the script was exhausted"
        expected_kind, value = draw
        assert kind == expected_kind, f"Expected a {expected_kind} draw, received {kind}"

        return value

    def random(self) -> float:
        """Return the next scripted uniform draw through the RNG interface."""

        return self._Take("uniform")

    def gauss(self, mean: float, sigma: float) -> float:
        """Return the next scripted draw for a requested standard normal."""

        assert (mean, sigma) == (0, 1), "The model must request standard normal draws"

        return self._Take("normal")

    def AssertExhausted(self) -> None:
        """Detect skipped draws, including draws for inactive shocks."""

        assert next(self._draws, None) is None, "The model left scripted draws unused"


def test_RegimeSwitchShockAndIndependentWicksMatchHandComputedRows():
    """Pin stress and calm candles with distinct shocks, wicks and AR(1) noise."""

    config = GenerationConfig(
        model="regime_v2",
        horizon=2, initial_price=1, drift=0.125, volatility=0.125,
        regime_persistence=0.6, regime_scale=2,
        shock_probability=0.25, shock_scale=2,
        wick_scale=0.5, wick_outlier_probability=0.25, wick_outlier_scale=4,
        volume_base=16, volume_sigma=0.5, volume_persistence=0.6, volume_return_coupling=0.25,
    )
    rng = ScriptedRandom((
        ("uniform", 0.7), ("normal", 1),
        ("uniform", 0.125), ("normal", -1),
        ("uniform", 0.125), ("normal", -0.5),
        ("uniform", 0.75), ("normal", 1),
        ("normal", 1),
        ("uniform", 0.6), ("normal", -2),
        ("uniform", 0.25), ("normal", 2),
        ("uniform", 0.25), ("normal", 0.5),
        ("uniform", 0.125), ("normal", -2),
        ("normal", -0.5),
    ))

    first, second = GenerateRows(config, rng)

    # Stress: log return 1/8 + 1/4 - 1/4. Upper/lower wick widths 1/4 and 1/8.
    # Volume noise 0.4 plus 0.125 from activity (realized return / sigma = 1/2).
    expected_first = (1, exp(3 / 8), exp(-1 / 8), exp(1 / 8), 16 * exp(0.525))
    assert first == pytest.approx(expected_first, rel=1e-12), "The stressed candle differs from the hand-derived values"

    # Calm: log return 1/8 - 1/4. The shock and upper outlier draws hit their thresholds.
    # The lower outlier extends 1/2. Volume noise 0.6 × 0.4 - 0.2 plus 0.25 from activity.
    expected_second = (exp(1 / 8), exp(5 / 32), exp(-1 / 2), 1, 16 * exp(0.29))
    assert second == pytest.approx(expected_second, rel=1e-12), "The calm candle differs from the hand-derived values"
    assert second[0] == first[3], "The second open must reuse the previous close exactly"
    rng.AssertExhausted()


def test_ReflectedCloseFeedsActivityAndWicksClipToBounds():
    """Check a return reflected twice and volume based on the realized move."""

    config = GenerationConfig(
        model="regime_v2",
        horizon=1, initial_price=exp(1 / 4), price_floor=1, price_ceiling=exp(1 / 2),
        volatility=0.125, regime_persistence=1, shock_probability=0,
        wick_scale=1, wick_outlier_probability=0,
        volume_base=16, volume_sigma=0, volume_return_coupling=0.5,
    )
    rng = ScriptedRandom((
        ("uniform", 0.5), ("normal", 7),
        ("uniform", 0.5), ("normal", 3),
        ("uniform", 0.5), ("normal", 4),
        ("uniform", 0.5), ("normal", -3),
        ("normal", 1),
    ))

    row, = GenerateRows(config, rng)

    # In log prices, 9/8 reflects to -1/8 at 1/2, then to 1/8 at 0.
    # Both raw wicks cross the bounds. The realized move is one sigma, giving log activity 1/2.
    expected = (exp(1 / 4), exp(1 / 2), 1, exp(1 / 8), 16 * exp(1 / 2))
    assert row == pytest.approx(expected, rel=1e-12), "Reflection, wick clipping, or realized-return activity changed"
    rng.AssertExhausted()
