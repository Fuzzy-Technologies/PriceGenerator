"""Compute immutable descriptive OHLCV diagnostics without realism claims."""

from dataclasses import asdict, dataclass
import json
import math

import numpy as np


@dataclass(frozen=True)
class Estimate:
    """A finite scalar or an explicit explanation of undefinedness."""

    value: float | None
    reason: str | None = None


@dataclass(frozen=True)
class Distribution:
    """A marginal distribution with conventions and domain exclusions exposed."""

    name: str
    count: int
    excluded: int
    mean: Estimate
    variance: Estimate
    standard_deviation: Estimate
    skewness: Estimate
    excess_kurtosis: Estimate
    minimum: Estimate
    maximum: Estimate
    quantiles: tuple[tuple[float, Estimate], ...]
    lower_tail_mean: Estimate
    upper_tail_mean: Estimate
    tukey_outlier_fraction: Estimate
    three_sigma_fraction: Estimate


@dataclass(frozen=True)
class ProportionBand:
    """A Hoeffding interval valid for independent Bernoulli trials only."""

    count: int
    trials: int
    confidence: float
    lower: float
    upper: float


@dataclass(frozen=True)
class PricePathSummary:
    """Observed horizon, endpoint movement, candle directions and activity totals."""

    start_datetime: str
    end_datetime: str
    elapsed_seconds: float
    first_close: float
    last_close: float
    close_range: Estimate
    endpoint_change: Estimate
    endpoint_return: Estimate
    up_candles: int
    down_candles: int
    doji_candles: int
    longest_up_run: int
    longest_down_run: int
    total_volume: Estimate


@dataclass(frozen=True)
class AnalysisReport:
    """Detached, strict-JSON descriptive evidence with no mutable frame references."""

    candle_count: int
    cadence_regular: bool
    distributions: tuple[Distribution, ...]
    simple_returns: tuple[float | None, ...]
    log_returns: tuple[float | None, ...]
    return_reasons: tuple[str | None, ...]
    log_return_reasons: tuple[str | None, ...]
    return_acf: tuple[Estimate, ...]
    absolute_return_acf: tuple[Estimate, ...]
    squared_return_acf: tuple[Estimate, ...]
    drawdown: tuple[float | None, ...]
    maximum_drawdown: Estimate
    maximum_drawdown_duration_bars: Estimate
    volume_absolute_return_correlation: Estimate
    volume_range_correlation: Estimate
    up_candle_fraction: Estimate
    zero_volume_fraction: Estimate
    path: PricePathSummary
    notes: tuple[str, ...]

    def ToDict(self) -> dict:
        """Return a fresh JSON-compatible representation on every call."""

        return asdict(self)

    def ToJSON(self) -> str:
        """Serialize deterministically and reject nonstandard NaN/Infinity tokens."""

        return json.dumps(self.ToDict(), allow_nan=False, sort_keys=True, separators=(",", ":"))

    def Summary(self) -> tuple[str, ...]:
        """Produce a compact plain-text report for chart and Markdown adapters."""

        path = self.path
        lines = [f"Candles: {self.candle_count}", f"UTC horizon: {path.start_datetime} to {path.end_datetime} ({path.elapsed_seconds:g} seconds)", f"Regular observed cadence: {self.cadence_regular}", f"Close first/last: {path.first_close:.8g} / {path.last_close:.8g}", f"Endpoint change: {_Format(path.endpoint_change)}; return: {_Format(path.endpoint_return)}", f"Close range: {_Format(path.close_range)}", f"Up/down/doji candles: {path.up_candles} / {path.down_candles} / {path.doji_candles}", f"Longest up/down runs: {path.longest_up_run} / {path.longest_down_run}", f"Total volume: {_Format(path.total_volume)}"]

        for distribution in self.distributions:
            lines.append(f"{distribution.name}: n={distribution.count}, excluded={distribution.excluded}, mean={_Format(distribution.mean)}, min={_Format(distribution.minimum)}, max={_Format(distribution.maximum)}")
            lines.append(f"  Sample variance={_Format(distribution.variance)}, std={_Format(distribution.standard_deviation)}, adjusted skew={_Format(distribution.skewness)}, excess kurtosis={_Format(distribution.excess_kurtosis)}")
            lines.append("  Quantiles: " + ", ".join(f"{level:g}={_Format(value)}" for level, value in distribution.quantiles))
            lines.append(f"  5%/95% tail means={_Format(distribution.lower_tail_mean)} / {_Format(distribution.upper_tail_mean)}; Tukey/3σ fractions={_Format(distribution.tukey_outlier_fraction)} / {_Format(distribution.three_sigma_fraction)}")

        lines.extend((f"Maximum drawdown: {_Format(self.maximum_drawdown)}; longest underwater bars: {_Format(self.maximum_drawdown_duration_bars)}", f"Volume/absolute-return Pearson correlation: {_Format(self.volume_absolute_return_correlation)}", f"Volume/range Pearson correlation: {_Format(self.volume_range_correlation)}", f"Up-candle fraction: {_Format(self.up_candle_fraction)}; zero-volume fraction: {_Format(self.zero_volume_fraction)}"))

        for label, estimates in (("Returns", self.return_acf), ("Absolute returns", self.absolute_return_acf), ("Squared returns", self.squared_return_acf)):
            lines.append(f"{label} ACF lags 1..{len(estimates)}: " + ", ".join(_Format(item) for item in estimates))

        lines.extend(self.notes)

        return tuple(lines)


def _Format(estimate: Estimate) -> str:
    """Keep undefined reasons visible in human-readable reports."""

    return f"{estimate.value:.8g}" if estimate.value is not None else f"undefined ({estimate.reason})"


def _LongestRun(values) -> int:
    """Count a direction run with doji candles breaking either directional chain."""

    longest = current = 0

    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)

    return longest


def _Estimate(value: float, reason: str = "numerical overflow") -> Estimate:
    """Never expose an unrepresentable floating-point result as valid evidence."""

    return Estimate(float(value)) if math.isfinite(value) else Estimate(None, reason)


def Describe(values, name: str = "values") -> Distribution:
    """Use sample variance, adjusted Fisher moments, and linear quantiles."""

    supplied = tuple(values)
    array = np.array([value for value in supplied if value is not None and math.isfinite(value)], dtype=float)
    count = len(array)
    missing = Estimate(None, "no valid observations")
    quantile_levels = (0.01, 0.05, 0.25, 0.5, 0.75, 0.8, 0.95, 0.99)

    if not count:
        return Distribution(name, 0, len(supplied), missing, missing, missing, missing, missing, missing, missing, tuple((level, missing) for level in quantile_levels), missing, missing, missing, missing)

    # Normalize moments before taking powers to avoid overflow for finite prices.
    scale = float(np.max(np.abs(array))) or 1.0
    normalized = array / scale
    mean_normalized = float(np.mean(normalized))
    centered = normalized - mean_normalized
    second = float(np.mean(centered ** 2))
    mean = _Estimate(mean_normalized * scale)
    variance = Estimate(None, "requires at least two observations")
    deviation = variance

    if count >= 2:
        std_normalized = math.sqrt(second * count / (count - 1))
        deviation = _Estimate(std_normalized * scale)
        variance = _Estimate((std_normalized * scale) ** 2 if std_normalized * scale <= math.sqrt(np.finfo(float).max) else math.inf)

    skew = Estimate(None, "requires at least three observations with nonzero variance")
    kurtosis = Estimate(None, "requires at least four observations with nonzero variance")

    if second > 0 and count >= 3:
        third = float(np.mean((centered / math.sqrt(second)) ** 3))
        skew = _Estimate(math.sqrt(count * (count - 1)) / (count - 2) * third)

    if second > 0 and count >= 4:
        fourth = float(np.mean((centered / math.sqrt(second)) ** 4))
        kurtosis = _Estimate((count - 1) / ((count - 2) * (count - 3)) * ((count + 1) * (fourth - 3) + 6))

    quantiles = np.quantile(normalized, quantile_levels, method="linear")
    lower = normalized[normalized <= quantiles[1]]
    upper = normalized[normalized >= quantiles[-2]]
    iqr = quantiles[4] - quantiles[2]
    outliers = (normalized < quantiles[2] - 1.5 * iqr) | (normalized > quantiles[4] + 1.5 * iqr)
    sigma = math.sqrt(second)
    extreme = np.abs(centered) > 3 * sigma

    return Distribution(name, count, len(supplied) - count, mean, variance, deviation, skew, kurtosis, _Estimate(float(array.min())), _Estimate(float(array.max())), tuple((level, _Estimate(float(value) * scale)) for level, value in zip(quantile_levels, quantiles)), _Estimate(float(lower.mean()) * scale), _Estimate(float(upper.mean()) * scale), _Estimate(float(outliers.mean())), _Estimate(float(extreme.mean())))


def ProportionInterval(count: int, trials: int, *, confidence: float = 0.99) -> ProportionBand:
    """Bound independent Bernoulli rates using Hoeffding's finite-sample inequality."""

    if type(trials) is not int or type(count) is not int or trials < 1 or not 0 <= count <= trials:
        raise ValueError("count and trials must be integers with 0 <= count <= trials and trials > 0")

    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 < confidence < 1:
        raise ValueError("confidence must lie strictly between zero and one")

    width = math.sqrt(math.log(2 / (1 - confidence)) / (2 * trials))
    rate = count / trials

    return ProportionBand(count, trials, float(confidence), max(0.0, rate - width), min(1.0, rate + width))


def ProbabilityTolerance(trials: int, *, confidence: float = 0.99) -> float:
    """Return a predeclared absolute rate tolerance for independent event tests."""

    band = ProportionInterval(0, trials, confidence=confidence)

    return band.upper


def ACF(values, lags: int = 10) -> tuple[Estimate, ...]:
    """Use global-mean biased ACF at observation lags 1 through lags, without gaps."""

    if type(lags) is not int or lags < 0:
        raise ValueError("lags must be a nonnegative integer")

    supplied = tuple(values)

    if any(value is None or not math.isfinite(value) for value in supplied):
        return (Estimate(None, "domain gaps prevent contiguous-lag ACF"),) * lags

    count = len(supplied)
    array = np.array(supplied, dtype=float)
    scale = float(np.max(np.abs(array))) if count else 1.0
    centered = array / (scale or 1.0)
    centered = centered - centered.mean() if count else centered
    denominator = float(np.dot(centered, centered))
    result = []

    for lag in range(1, lags + 1):
        if count <= lag:
            result.append(Estimate(None, "lag requires more observations"))

        elif denominator == 0:
            result.append(Estimate(None, "constant observations have undefined ACF"))

        else:
            result.append(_Estimate(float(np.dot(centered[:-lag], centered[lag:])) / denominator))

    return tuple(result)


def _Correlation(left, right) -> Estimate:
    """Use Pearson correlation on explicitly paired valid observations."""

    pairs = [(first, second) for first, second in zip(left, right) if first is not None and second is not None]

    if len(pairs) < 2:
        return Estimate(None, "requires at least two valid pairs")

    array = np.array(pairs, dtype=float)
    scales = np.max(np.abs(array), axis=0)
    centered = array / np.where(scales == 0, 1, scales)
    centered -= centered.mean(axis=0)
    sums = np.sum(centered ** 2, axis=0)

    if np.any(sums == 0):
        return Estimate(None, "correlation requires nonconstant paired observations")

    return _Estimate(float(np.dot(centered[:, 0], centered[:, 1]) / math.sqrt(sums[0] * sums[1])))


def Analyze(frame, *, acf_lags: int = 10) -> AnalysisReport:
    """Validate canonical OHLCV, then compute separate unrounded descriptive diagnostics."""

    from .market_data import ValidateOHLCV

    prices = ValidateOHLCV(frame)
    if prices.empty:
        raise ValueError("analysis requires at least one candle")

    closing = prices.close.to_numpy()
    count = len(prices)
    simple = [None]
    logs = [None]
    reasons = ["no previous close"]
    log_reasons = ["no previous close"]

    for previous, current in zip(closing, closing[1:]):
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            value = float(current / previous - 1) if previous != 0 else math.inf

        valid = previous != 0 and math.isfinite(value)
        simple.append(value if valid else None)
        reasons.append(None if valid else "previous close is zero" if previous == 0 else "return overflow")
        positive = previous > 0 and current > 0
        logs.append(float(math.log(current) - math.log(previous)) if positive else None)
        log_reasons.append(None if positive else "log returns require positive adjacent closes")

    with np.errstate(over="ignore", invalid="ignore"):
        body = prices.close.to_numpy() - prices.open.to_numpy()
        candle_range = prices.high.to_numpy() - prices.low.to_numpy()
        upper_wick = prices.high.to_numpy() - np.maximum(prices.open, prices.close)
        lower_wick = np.minimum(prices.open, prices.close) - prices.low.to_numpy()

    body_ratio = [float(abs(value) / span) if span > 0 and math.isfinite(span) else None for value, span in zip(body, candle_range)]
    upper_ratio = [float(value / span) if span > 0 and math.isfinite(span) else None for value, span in zip(upper_wick, candle_range)]
    lower_ratio = [float(value / span) if span > 0 and math.isfinite(span) else None for value, span in zip(lower_wick, candle_range)]
    named = (("simple_returns", simple[1:]), ("log_returns", logs[1:]), ("body", body), ("absolute_body", np.abs(body)), ("upper_wick", upper_wick), ("lower_wick", lower_wick), ("range", candle_range), ("body_fraction", body_ratio), ("upper_wick_fraction", upper_ratio), ("lower_wick_fraction", lower_ratio), ("volume", prices.volume))
    distributions = tuple(Describe(values, name) for name, values in named)
    drawdown = (None,) * count
    maximum = Estimate(None, "percentage drawdown requires strictly positive closes")
    duration = maximum

    if np.all(closing > 0):
        peak = closing[0]
        elapsed = 0
        longest = 0
        drawdowns = []

        for value in closing:
            peak = max(peak, value)
            drawdowns.append(float(1 - value / peak))
            elapsed = elapsed + 1 if value < peak else 0
            longest = max(longest, elapsed)

        drawdown = tuple(drawdowns)
        maximum = Estimate(max(drawdowns))
        duration = Estimate(float(longest))

    instants = [int(value) for value in prices.datetime.array.asi8]
    deltas = [current - previous for previous, current in zip(instants, instants[1:])]
    regular = len(set(deltas)) <= 1
    returns = simple[1:]
    absolute = [abs(value) if value is not None else None for value in returns]
    # Rescaling before squaring preserves ACF and avoids return-power overflow.
    return_scale = max((abs(value) for value in returns if value is not None), default=1.0) or 1.0
    squared = [(value / return_scale) ** 2 if value is not None else None for value in returns]
    notes = (
        "Descriptive diagnostics are not evidence of universal market realism or investment suitability.",
        "Variance uses ddof=1; skewness and excess kurtosis use adjusted Fisher estimators; quantiles use linear interpolation.",
        "Tails are inclusive observations at/beyond empirical 5% and 95% quantiles; Tukey outliers use 1.5 IQR fences; 3σ uses population deviation.",
        "ACF uses observation lags, global centering and a full-sample denominator; irregular cadence is not resampled.",
        "Domain-invalid returns remain aligned nulls; marginal summaries exclude them; ACF does not compress gaps.",
        "ProbabilityTolerance applies only to independent Bernoulli generator events with a predeclared confidence and sample size.",
        "Drawdown is a positive peak-to-trough fraction; duration counts consecutive underwater observed bars, including unrecovered periods.",
    )

    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        endpoint_change = _Estimate(float(closing[-1] - closing[0]))
        close_range = _Estimate(float(closing.max() - closing.min()))
        endpoint_return = _Estimate(float(closing[-1] / closing[0] - 1)) if closing[0] != 0 else Estimate(None, "first close is zero")
        total_volume = _Estimate(float(prices.volume.sum()))

    up = prices.close > prices.open
    down = prices.close < prices.open
    path = PricePathSummary(prices.datetime.iloc[0].isoformat(), prices.datetime.iloc[-1].isoformat(), (instants[-1] - instants[0]) / 1e9, float(closing[0]), float(closing[-1]), close_range, endpoint_change, endpoint_return, int(up.sum()), int(down.sum()), int((~up & ~down).sum()), _LongestRun(up), _LongestRun(down), total_volume)

    return AnalysisReport(count, regular, distributions, tuple(simple), tuple(logs), tuple(reasons), tuple(log_reasons), ACF(returns, acf_lags), ACF(absolute, acf_lags), ACF(squared, acf_lags), drawdown, maximum, duration, _Correlation(absolute, prices.volume.iloc[1:]), _Correlation([float(value) if math.isfinite(value) else None for value in candle_range], prices.volume), Estimate(float((prices.close > prices.open).mean())), Estimate(float((prices.volume == 0).mean())), path, notes)
