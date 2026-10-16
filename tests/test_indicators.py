"""Verify modern indicator formulas against independent hand-calculated vectors."""

import json
import math
import random

import numpy as np
import pandas as pd
import pytest

from pricegenerator.indicators import Alligator, Bollinger, HMA, Indicators, PSAR, SMA, SmoothedMA, VWMA, WMA, ZigZag


def test_HandMovingAverageVectors() -> None:
    """Small linear prices expose alignment, WMA weighting and Hull rounding."""

    values = [1, 2, 3, 4, 5, 6, 7, 8]

    assert SMA(values, 3) == (None, None, 2, 3, 4, 5, 6, 7), "SMA needs three complete trailing observations."
    assert WMA(values, 3)[2:] == pytest.approx([14 / 6, 20 / 6, 26 / 6, 32 / 6, 38 / 6, 44 / 6]), "WMA weights must increase toward the newest value."
    assert HMA(values, 5)[:5] == (None,) * 5, "HMA 5 warmup is five bars for full WMA plus one for sqrt-period smoothing."
    assert HMA(values, 5)[5:] == pytest.approx([19 / 3, 22 / 3, 25 / 3]), "Hull period 5 uses half=2 and sqrt=2 with no displacement."
    assert HMA(iter(values), 5) == HMA(values, 5), "A generator input must be snapshotted before multiple WMA passes."
    assert HMA(values, 1) == tuple(values), "Period-one HMA should preserve prices."
    assert VWMA([10, 20, 30, 40], [1, 3, 0, 2], 2)[1:] == pytest.approx([17.5, 20, 40]), "VWMA must weight actual activity rather than substitute equal weights."


def test_BollingerPopulationDeviation() -> None:
    """An asymmetric three-point vector distinguishes population and sample bands."""

    lower, middle, upper = Bollinger([1, 2, 3, 4], 3, 2)
    spread = 2 * math.sqrt(2 / 3)

    assert lower[:2] == middle[:2] == upper[:2] == (None, None), "Bands require full windows."
    assert middle[2:] == (2, 3), "The center line must be the trailing SMA."
    assert lower[2:] == pytest.approx([2 - spread, 3 - spread]), "Bollinger lower uses ddof=0 population deviation."
    assert upper[2:] == pytest.approx([2 + spread, 3 + spread]), "Bollinger upper must be symmetric around the SMA."


def test_SmmaAndModernAlligatorHaveSeparateSemantics() -> None:
    """SMMA seed and recursion are hand derived and Alligator shifts median prices."""

    values = list(range(1, 31))
    smma = SmoothedMA(values, 3)
    jaw, teeth, lips = Alligator(np.asarray(values) + 2, np.asarray(values) - 2)

    assert smma[:2] == (None, None), "SMMA requires its initial SMA window."
    assert smma[2:5] == pytest.approx([2, 8 / 3, 31 / 9]), "SMMA follows Wilder smoothing after its SMA seed."
    assert jaw[:20] == (None,) * 20 and jaw[20] == pytest.approx(7), "Jaw uses median SMA seed 7 at index12, displaced eight rows."
    assert teeth[:12] == (None,) * 12 and teeth[12] == pytest.approx(4.5), "Teeth use period8 and shift5."
    assert lips[:7] == (None,) * 7 and lips[7] == pytest.approx(3), "Lips use period5 and shift3."
    assert lips[8] == pytest.approx(3.6), "Forward displacement cannot change the underlying SMMA recursion."
    assert HMA(values, 5) != lips, "An ordinary HMA must remain independent of Alligator."


def test_MissingAndZeroVolumeWindowsRemainExplicit() -> None:
    """Missing observations reset smoothing and never receive invented prices."""

    values = [1, 2, 3, None, 5, 6, 7, 8]

    assert SMA(values, 3) == (None, None, 2, None, None, None, 6, 7), "A missing price invalidates all rolling windows that contain it."
    assert SmoothedMA(values, 3) == (None, None, 2, None, None, None, 6, pytest.approx(20 / 3)), "Recursive smoothing must seed anew after a missing input."
    assert VWMA([1, 2, 3], [0, 0, 0], 2) == (None, None, None), "Zero-volume windows have no defined weighted price."
    assert VWMA([1, None, 3, 4], [1, 1, 1, 1], 2) == (None, None, None, 3.5), "Volume presence cannot mask a missing price."
    long_values, short_values = PSAR([3, 4, None, 6, 7], [1, 2, None, 4, 5])

    assert long_values == (None, 1, None, None, 4) and short_values == (None,) * 5, "PSAR must reinitialize after each missing run."


def test_HandPsarTrendAndReversalVector() -> None:
    """SAR arithmetic, acceleration, prior-two clamps and reversals have fixed evidence."""

    long_values, short_values = PSAR([11, 12, 13, 14, 10, 9, 15], [9, 10, 11, 12, 8, 7, 10])

    assert long_values[:4] == (None, 9, 9, pytest.approx(9.16)), "First clamp retains9; next SAR is9 + .04*(13-9)."
    assert long_values[4:6] == (None, None), "A down reversal must end the long series."
    assert short_values[4] == pytest.approx(14), "Down reversal SAR equals the preceding uptrend extreme14."
    assert short_values[5] == pytest.approx(14), "Prior-two high clamp prevents immediate SAR penetration."
    assert long_values[6] == pytest.approx(7) and short_values[6] is None, "An up reversal SAR equals the prior downtrend low7."


def test_ZigZagConfirmsPivotsAndOmitsProvisionalEndpoint() -> None:
    """Reversal-threshold pivots must not turn the unconfirmed last price into a signal."""

    assert ZigZag([100, 110, 105, 99, 100, 112, 110], 0.1) == (100, 110, None, 99, None, None, None), "Only extrema with a threshold-sized following reversal are confirmed."
    assert ZigZag([0, 1, 2]) == (None, None, None), "Percentage Zig-Zag requires strictly positive prices."
    assert ZigZag([100, 100, 100]) == (None, None, None), "A flat path has no confirmed directional reversal."


def test_ReportsDoNotMutateFramesOrRng() -> None:
    """The retained chart set is portable, aligned and never changes canonical columns."""

    values = np.arange(1, 241, dtype=float)
    frame = pd.DataFrame({"datetime": pd.date_range("2026-01-01", periods=240, tz="UTC", freq="h"), "open": values, "high": values + 1, "low": values - 1, "close": values, "volume": values * 10})
    original = frame.copy(deep=True)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    report = Indicators(frame)
    pd.testing.assert_frame_equal(frame, original)
    np.testing.assert_equal(np.random.get_state(), numpy_state)
    series = {item.key: item for item in report.series}

    assert random.getstate() == python_state, "Indicators must not consume Python RNG."
    assert len(series) == 17 and all(len(item.values) == 240 for item in series.values()), "All retained indicators must have exactly one aligned value per candle."
    assert all(len(item.reasons) == len(item.values) for item in report.series), "Every report series must carry aligned null explanations."
    assert series["hma5"].reasons[0] and series["hma5"].reasons[5] is None, "Warmup explanations must stop when valid HMA values begin."
    assert series["hma5"].values != series["alligator-lips"].values, "Alligator must not overwrite HMA5."
    assert series["psar-long"].kind == series["psar-short"].kind == "points", "PSAR direction series must remain separate point overlays."
    assert json.loads(report.ToJSON())["series"][0]["values"][0] is None, "Portable reports must preserve warmup as JSON null."


@pytest.mark.parametrize("period", [0, -1, 1.5, True])
def test_InvalidPeriodsFail(period) -> None:
    """Reject noninteger, boolean and nonpositive period configurations."""

    with pytest.raises(ValueError, match="period"):
        SMA([1, 2, 3], period)


@pytest.mark.parametrize("operation", [lambda: SMA([True], 1), lambda: HMA([math.inf], 5), lambda: VWMA([1, 2], [1], 2), lambda: VWMA([1], [-1], 1), lambda: Bollinger([1], deviations=-1), lambda: PSAR([2], [1], step=0), lambda: PSAR([0], [1]), lambda: ZigZag([1], 1)])
def test_InvalidInputsCannotSilentlyCoerce(operation) -> None:
    """Invalid prices, alignment and numerical policies must fail explicitly."""

    with pytest.raises(ValueError):
        operation()


def test_ExtremeVwmaWindowsPreserveLocalScale() -> None:
    """Widely separated magnitudes must not underflow unrelated complete windows."""

    assert VWMA([1e308, 1e-308, 1e-308], [1, 1, 1], 1) == (1e308, 1e-308, 1e-308), "Period-one VWMA must preserve every positive-volume price."
    result = VWMA([10, 20, 30], [1e308, 1e-200, 1e-200], 2)

    assert result[1:] == pytest.approx([10, 25]), "Leaving a huge historical volume must not erase later small-volume windows."
    assert VWMA([1e308, 1e-308], [1e-308, 1e308], 2)[1] == pytest.approx(2e-308, rel=1e-12, abs=0), "Opposing extreme price/activity scales must retain both weighted products."


def test_PsarDirectionPreservesSmallFiniteMovement() -> None:
    """A large high level must not underflow a smaller but real downward move."""

    long_values, short_values = PSAR([1e308, 1e308], [2e-308, 1e-308])

    assert long_values == (None, None) and short_values == (None, 1e308), "Zero upward movement and positive downward movement must initialize a falling SAR."
    assert HMA([1e308] * 8, 5)[5:] == (1e308,) * 3, "Hull arithmetic must avoid intermediate2*price overflow when the final difference is representable."
