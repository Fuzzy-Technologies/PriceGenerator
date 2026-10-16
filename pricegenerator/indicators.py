"""Compute explicit project-owned indicators independently of generation and charts."""

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
import json
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorSeries:
    """One immutable observation-aligned overlay with null warmup/domain gaps."""

    key: str
    label: str
    values: tuple[float | None, ...]
    group: str
    kind: str = "line"
    reasons: tuple[str | None, ...] = ()


@dataclass(frozen=True)
class IndicatorReport:
    """Indicator values and formula conventions detached from canonical OHLCV."""

    series: tuple[IndicatorSeries, ...]
    notes: tuple[str, ...]

    def ToDict(self) -> dict:
        """Return a detached serializable copy of indicator results."""

        return asdict(self)

    def ToJSON(self) -> str:
        """Serialize without nonstandard floating-point tokens."""

        return json.dumps(self.ToDict(), allow_nan=False, sort_keys=True, separators=(",", ":"))


def _Period(period: int) -> int:
    """Reject coerced booleans, fractional periods and empty windows."""

    if type(period) is not int or period < 1:
        raise ValueError("period must be a positive integer")

    return period


def _Array(values) -> np.ndarray:
    """Normalize missing values while rejecting booleans, infinities and nonnumbers."""

    result = []

    for value in values:
        if value is None or value is pd.NA:
            result.append(math.nan)
            continue

        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or np.iscomplexobj(value):
            raise ValueError("indicator values must be real numbers or missing")

        number = float(value)

        if math.isinf(number):
            raise ValueError("indicator values cannot be infinite")

        result.append(number)

    return np.asarray(result, dtype=float)


def _Values(values) -> tuple[float | None, ...]:
    """Make undefined warmup and arithmetic overflow explicit portable gaps."""

    return tuple(float(value) if math.isfinite(value) else None for value in values)


def SMA(values, period: int) -> tuple[float | None, ...]:
    """Arithmetic mean of each complete trailing observation window."""

    array = _Array(values)
    result = pd.Series(array).rolling(_Period(period), min_periods=period).mean()

    return _Values(result)


def WMA(values, period: int) -> tuple[float | None, ...]:
    """Linearly weighted trailing mean, with newest weight equal to period."""

    array = _Array(values)
    period = _Period(period)
    weights = np.arange(1, period + 1, dtype=float)
    weights /= weights.sum()
    result = pd.Series(array).rolling(period, min_periods=period).apply(lambda window: float(np.dot(window, weights)), raw=True)

    return _Values(result)


def HMA(values, period: int) -> tuple[float | None, ...]:
    """Hull's WMA(2 WMA(x,floor(n/2))-WMA(x,n),floor(sqrt(n))), unshifted."""

    period = _Period(period)
    array = _Array(values)
    half = _Array(WMA(array, max(1, period // 2)))
    full = _Array(WMA(array, period))

    with np.errstate(over="ignore", invalid="ignore"):
        difference = half + (half - full)

    difference[~np.isfinite(difference)] = np.nan

    return WMA(difference, max(1, math.isqrt(period)))


def VWMA(values, volume, period: int) -> tuple[float | None, ...]:
    """Volume-weighted trailing mean; missing and zero-sum windows are gaps."""

    array = _Array(values)
    weights = _Array(volume)
    period = _Period(period)

    if len(array) != len(weights) or np.any(weights < 0):
        raise ValueError("volume must be aligned and nonnegative")

    result = [None] * len(array)

    for index in range(period - 1, len(array)):
        window = array[index - period + 1:index + 1]
        activity = weights[index - period + 1:index + 1]

        if np.any(~np.isfinite(window)) or np.any(~np.isfinite(activity)) or not np.any(activity):
            continue

        nonzero_prices = np.abs(window[window != 0])
        nonzero_volume = activity[activity != 0]
        extreme = any(np.any((values < 1e-100) | (values > 1e100)) for values in (nonzero_prices, nonzero_volume))

        if extreme:
            # Float inputs can span 616 decimal exponents. Local high precision
            # preserves tiny weighted contributions without cross-window scaling.
            with localcontext() as context:
                context.prec = 800
                pairs = [(Decimal.from_float(float(price)), Decimal.from_float(float(weight))) for price, weight in zip(window, activity)]
                total = sum((weight for _, weight in pairs), Decimal(0))
                average = sum((price * weight for price, weight in pairs), Decimal(0)) / total
                result[index] = float(average)

        else:
            scaled = activity / nonzero_volume.max()
            denominator = math.fsum(scaled)
            result[index] = math.fsum(float(price) * (float(weight) / denominator) for price, weight in zip(window, scaled))

    return _Values(value if value is not None else math.nan for value in result)


def Bollinger(values, period: int = 20, deviations: float = 2.0) -> tuple[tuple[float | None, ...], ...]:
    """Return lower, middle, upper bands using population window deviation (ddof=0)."""

    if isinstance(deviations, bool) or not isinstance(deviations, (int, float)) or not math.isfinite(deviations) or deviations < 0:
        raise ValueError("deviations must be finite and nonnegative")

    array = _Array(values)
    period = _Period(period)
    rolling = pd.Series(array).rolling(period, min_periods=period)
    middle = rolling.mean()
    spread = rolling.std(ddof=0) * deviations

    return _Values(middle - spread), _Values(middle), _Values(middle + spread)


def SmoothedMA(values, period: int) -> tuple[float | None, ...]:
    """Seed each contiguous run with SMA, then use (previous*(n-1)+x)/n."""

    array = _Array(values)
    period = _Period(period)
    result = []
    window = []
    previous = None

    for value in array:
        if not math.isfinite(value):
            window = []
            previous = None
            result.append(None)
            continue

        if previous is None:
            window.append(float(value))

            if len(window) < period:
                result.append(None)
                continue

            previous = float(np.sum(np.asarray(window) / period))

        else:
            previous = previous * ((period - 1) / period) + float(value) / period

        result.append(previous if math.isfinite(previous) else None)

    return tuple(result)


def _Shift(values, shift: int) -> tuple[float | None, ...]:
    """Displace into later existing rows without appending invented timestamps."""

    values = tuple(values)

    return (None,) * min(shift, len(values)) + values[:max(0, len(values) - shift)]


def Alligator(high, low) -> tuple[tuple[float | None, ...], ...]:
    """Return SMMA median-price jaw(13,+8), teeth(8,+5), lips(5,+3)."""

    upper = _Array(high)
    lower = _Array(low)

    if len(upper) != len(lower) or np.any(upper < lower):
        raise ValueError("high and low must be aligned with high >= low")

    midpoint = upper / 2 + lower / 2

    return tuple(_Shift(SmoothedMA(midpoint, period), shift) for period, shift in ((13, 8), (8, 5), (5, 3)))


def PSAR(high, low, *, step: float = 0.02, maximum: float = 0.2) -> tuple[tuple[float | None, ...], ...]:
    """Wilder SAR with two-bar directional initialization and prior-two-bar clamps."""

    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (step, maximum)) or not 0 < step <= maximum <= 1:
        raise ValueError("PSAR requires 0 < step <= maximum <= 1")

    upper = _Array(high)
    lower = _Array(low)

    if len(upper) != len(lower) or np.any(upper < lower):
        raise ValueError("high and low must be aligned with high >= low")

    long_values = [None] * len(upper)
    short_values = [None] * len(upper)
    start = 0

    while start < len(upper):
        if not math.isfinite(upper[start]) or not math.isfinite(lower[start]):
            start += 1
            continue

        end = start

        while end < len(upper) and math.isfinite(upper[end]) and math.isfinite(lower[end]):
            end += 1

        if end - start < 2:
            start = end
            continue

        with np.errstate(over="ignore"):
            upward_movement = upper[start + 1] - upper[start]
            downward_movement = lower[start] - lower[start + 1]

        if not math.isfinite(upward_movement) or not math.isfinite(downward_movement):
            upward_movement = Decimal.from_float(float(upper[start + 1])) - Decimal.from_float(float(upper[start]))
            downward_movement = Decimal.from_float(float(lower[start])) - Decimal.from_float(float(lower[start + 1]))

        rising = upward_movement >= downward_movement
        extreme = max(upper[start:start + 2]) if rising else min(lower[start:start + 2])
        sar = min(lower[start:start + 2]) if rising else max(upper[start:start + 2])
        acceleration = step
        (long_values if rising else short_values)[start + 1] = float(sar)

        for index in range(start + 2, end):
            candidate = sar * (1 - acceleration) + acceleration * extreme

            if rising:
                candidate = min(candidate, lower[index - 1], lower[index - 2])

                if lower[index] < candidate:
                    rising = False
                    sar = extreme
                    extreme = lower[index]
                    acceleration = step

                else:
                    sar = candidate

                    if upper[index] > extreme:
                        extreme = upper[index]
                        acceleration = min(maximum, acceleration + step)

            else:
                candidate = max(candidate, upper[index - 1], upper[index - 2])

                if upper[index] > candidate:
                    rising = True
                    sar = extreme
                    extreme = upper[index]
                    acceleration = step

                else:
                    sar = candidate

                    if lower[index] < extreme:
                        extreme = lower[index]
                        acceleration = min(maximum, acceleration + step)

            (long_values if rising else short_values)[index] = float(sar)

        start = end

    return tuple(long_values), tuple(short_values)


def ZigZag(values, deviation: float = 0.05) -> tuple[float | None, ...]:
    """Return confirmed close pivots; the last evolving extreme is deliberately omitted."""

    if isinstance(deviation, bool) or not isinstance(deviation, (int, float)) or not math.isfinite(deviation) or not 0 < deviation < 1:
        raise ValueError("deviation must lie strictly between zero and one")

    array = _Array(values)
    result = [None] * len(array)

    if not len(array) or np.any(~np.isfinite(array)) or np.any(array <= 0):
        return tuple(result)

    low_index = high_index = 0
    direction = 0
    extreme_index = 0

    for index in range(1, len(array)):
        value = array[index]

        if direction == 0:
            if value < array[low_index]:
                low_index = index

            if value > array[high_index]:
                high_index = index

            if index > low_index and value / array[low_index] >= 1 + deviation:
                result[low_index] = float(array[low_index])
                direction = 1
                extreme_index = index

            elif index > high_index and value / array[high_index] <= 1 - deviation:
                result[high_index] = float(array[high_index])
                direction = -1
                extreme_index = index

        elif direction == 1:
            if value >= array[extreme_index]:
                extreme_index = index

            elif value / array[extreme_index] <= 1 - deviation:
                result[extreme_index] = float(array[extreme_index])
                direction = -1
                extreme_index = index

        else:
            if value <= array[extreme_index]:
                extreme_index = index

            elif value / array[extreme_index] >= 1 + deviation:
                result[extreme_index] = float(array[extreme_index])
                direction = 1
                extreme_index = index

    return tuple(result)


def _ExplainSeries(item: IndicatorSeries, prices) -> IndicatorSeries:
    """Distinguish null warmup, inactive direction, zero activity and domain states."""

    key = item.key
    warmup = 0

    if key.startswith("sma"):
        warmup = int(key[3:]) - 1

    elif key.startswith("hma"):
        period = int(key[3:])
        warmup = period + max(1, math.isqrt(period)) - 2

    elif key.startswith("vwma"):
        warmup = int(key[4:]) - 1

    elif key.startswith("bbands-"):
        warmup = 19

    elif key.startswith("alligator-"):
        warmup = {"alligator-jaw": 20, "alligator-teeth": 12, "alligator-lips": 7}[key]

    elif key.startswith("psar-"):
        warmup = 1

    reasons = []
    zigzag_domain_invalid = bool((prices.close <= 0).any()) if key == "zigzag" else False

    for index, value in enumerate(item.values):
        reason = None

        if value is None:
            if index < warmup:
                reason = "insufficient trailing observations or forward-shift warmup"

            elif key.startswith("psar-"):
                reason = "inactive PSAR direction"

            elif key == "zigzag":
                reason = "requires strictly positive closes" if zigzag_domain_invalid else "no confirmed pivot at this candle; final extreme remains provisional"

            elif key.startswith("vwma") and prices.volume.iloc[index - warmup:index + 1].sum() == 0:
                reason = "complete window has zero total volume"

            else:
                reason = "arithmetic overflow in indicator calculation"

        reasons.append(reason)

    return IndicatorSeries(item.key, item.label, item.values, item.group, item.kind, tuple(reasons))


def Indicators(frame, *, zigzag_deviation: float = 0.05) -> IndicatorReport:
    """Calculate the retained chart capability set with deliberate modern formulas."""

    from .market_data import ValidateOHLCV

    prices = ValidateOHLCV(frame)
    closing = tuple(prices.close)
    result = []

    for period in (5, 20, 50, 200):
        group = "SMA 5 / 20" if period < 50 else "SMA 50 / 200"
        result.append(IndicatorSeries(f"sma{period}", f"SMA {period}", SMA(closing, period), group))

    for period in (5, 20):
        result.append(IndicatorSeries(f"hma{period}", f"HMA {period} (unshifted)", HMA(closing, period), "HMA 5 / 20"))
        result.append(IndicatorSeries(f"vwma{period}", f"VWMA {period}", VWMA(closing, prices.volume, period), "VWMA 5 / 20"))

    for key, values in zip(("lower", "mid", "upper"), Bollinger(closing)):
        result.append(IndicatorSeries(f"bbands-{key}", f"Bollinger {key} (20, 2σ, ddof=0)", values, "Bollinger bands"))

    for key, values in zip(("long", "short"), PSAR(prices.high, prices.low)):
        result.append(IndicatorSeries(f"psar-{key}", f"PSAR {key}", values, "PSAR", "points"))

    for key, period, shift, values in zip(("jaw", "teeth", "lips"), (13, 8, 5), (8, 5, 3), Alligator(prices.high, prices.low)):
        result.append(IndicatorSeries(f"alligator-{key}", f"Alligator {key}: SMMA {period}, shift {shift}", values, "Alligator (SMMA median price)"))

    result.append(IndicatorSeries("zigzag", f"Confirmed Zig-Zag ({zigzag_deviation:.1%})", ZigZag(closing, zigzag_deviation), "Zig-Zag"))
    notes = (
        "All periods and shifts count observations, including across timestamp gaps; no calendar resampling or price filling occurs.",
        "Missing inputs reset recursive indicators; complete rolling windows are required; null values mean warmup, missing/domain input or arithmetic overflow.",
        "HMA is always unshifted and independent of Alligator; Alligator uses SMA-seeded SMMA of (high+low)/2 and forward row shifts.",
        "PSAR starts after two bars; direction compares upward/downward movement (ties upward), initial SAR spans both bars, reversal SAR is prior extreme; equal touches do not reverse.",
        "Zig-Zag requires strictly positive complete closes; only threshold-confirmed pivots are shown, with no provisional final endpoint.",
    )

    return IndicatorReport(tuple(_ExplainSeries(item, prices) for item in result), notes)
