"""Compare explicit synthetic-data metrics and report resampling uncertainty."""

from dataclasses import asdict, dataclass
import json
import math
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from pricegenerator.analysis import Analyze
from pricegenerator._version import __version__
from pricegenerator.market_data import ValidateOHLCV
from pricegenerator.scenario import Environment, Fingerprint


@dataclass(frozen=True)
class MeanInterval:
    """Describe a seeded percentile interval under a stated resampling model."""

    lower: float
    upper: float
    confidence: float
    resamples: int
    seed: int
    block_length: int
    observations: int
    method: str = "moving-block percentile bootstrap of mean"
    rng: str = "numpy.PCG64"
    numpy_version: str = np.__version__

    def ToDict(self) -> dict:
        """Return interval values and reproducibility inputs."""

        return asdict(self)


def BootstrapMeanInterval(values: Sequence[float], *, seed: int, confidence: float = .95,
                          resamples: int = 2000, block_length: int = 1) -> MeanInterval:
    """Estimate mean uncertainty without assuming serial observations are independent.

    Blocks are contiguous, overlapping and non-circular. The last sampled block
    is truncated to the original length. Block length one is an IID bootstrap;
    larger blocks preserve dependence only within blocks. Percentile intervals
    are diagnostic finite-sample estimates, not exact coverage guarantees.
    """

    array = np.asarray(values, dtype=float)

    if array.ndim != 1 or len(array) < 2 or not np.isfinite(array).all():
        raise ValueError("Bootstrap requires at least two finite scalar observations")

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between zero and one")

    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 100:
        raise ValueError("resamples must be an integer of at least 100")

    if isinstance(block_length, bool) or not isinstance(block_length, int) or not 1 <= block_length <= len(array):
        raise ValueError("block_length must be between one and observation count")

    rng = np.random.Generator(np.random.PCG64(seed))
    scale = float(np.abs(array).max()) or 1.0
    normalized = array / scale
    means = np.empty(resamples)
    blocks = math.ceil(len(array) / block_length)
    offsets = np.arange(block_length)

    for index in range(resamples):
        starts = rng.integers(0, len(array) - block_length + 1, size=blocks)
        sample = normalized[(starts[:, None] + offsets).reshape(-1)[:len(array)]]
        means[index] = sample.mean()

    tail = (1 - confidence) / 2
    lower, upper = np.quantile(means, [tail, 1 - tail]) * scale

    return MeanInterval(float(lower), float(upper), confidence, resamples, seed, block_length, len(array))


@dataclass(frozen=True)
class MetricComparison:
    """Record a named metric difference and optional predeclared tolerance."""

    name: str
    reference: float | None
    synthetic: float | None
    difference: float | None
    absolute_tolerance: float | None
    within_tolerance: bool | None
    reason: str | None


@dataclass(frozen=True)
class ComparisonReport:
    """Keep metric evidence and provenance separate from global realism claims."""

    reference_fingerprint: str
    synthetic_fingerprint: str
    reference_rows: int
    synthetic_rows: int
    metrics: tuple[MetricComparison, ...]
    reference_analysis_json: str
    synthetic_analysis_json: str
    environment_json: str
    metric_version: str = "comparison_v1"
    library_version: str = __version__

    def ToDict(self) -> dict:
        """Return the two independent analyses and explicit metric decisions."""

        result = asdict(self)
        result["reference_analysis"] = json.loads(result.pop("reference_analysis_json"))
        result["synthetic_analysis"] = json.loads(result.pop("synthetic_analysis_json"))
        result["environment"] = json.loads(result.pop("environment_json"))
        result["decision_scope"] = "Only supplied absolute tolerances; no universal model acceptance or forecast claim"

        return result


def _Metrics(report) -> dict[str, float | None]:
    """Select predefined auditable metrics from the complete analysis report."""

    distributions = {item.name: item for item in report.distributions}

    return {
        "log_return_mean": distributions["log_returns"].mean.value,
        "log_return_std": distributions["log_returns"].standard_deviation.value,
        "body_fraction_mean": distributions["body_fraction"].mean.value,
        "volume_mean": distributions["volume"].mean.value,
        "squared_return_acf_lag1": report.squared_return_acf[0].value,
        "volume_absolute_return_correlation": report.volume_absolute_return_correlation.value,
        "maximum_drawdown": report.maximum_drawdown.value,
    }


def Compare(reference: pd.DataFrame, synthetic: pd.DataFrame, *,
            tolerances: Mapping[str, float] | None = None) -> ComparisonReport:
    """Compare deterministic metrics with user-declared absolute tolerances.

    Missing or degenerate statistics remain undefined and cannot pass a gate.
    The complete independent analyses preserve tails and temporal diagnostics;
    tolerances should be selected before looking at evaluation data.
    """

    reference_frame = ValidateOHLCV(reference)
    synthetic_frame = ValidateOHLCV(synthetic)
    reference_report = Analyze(reference_frame)
    synthetic_report = Analyze(synthetic_frame)
    reference_metrics = _Metrics(reference_report)
    synthetic_metrics = _Metrics(synthetic_report)
    selected = dict(tolerances or {})

    for name, tolerance in selected.items():
        if name not in reference_metrics:
            raise ValueError(f"Unknown comparison metric: {name}")

        if isinstance(tolerance, bool) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError(f"Tolerance for {name} must be finite and nonnegative")

    comparisons = []

    for name, reference_value in reference_metrics.items():
        synthetic_value = synthetic_metrics[name]
        tolerance = selected.get(name)
        defined = reference_value is not None and synthetic_value is not None
        difference = synthetic_value - reference_value if defined else None
        decision = abs(difference) <= tolerance if defined and tolerance is not None else None
        reason = None if defined else "Undefined statistic; inspect independent analysis reasons"
        comparisons.append(MetricComparison(name, reference_value, synthetic_value, difference, tolerance, decision, reason))

    return ComparisonReport(Fingerprint(reference_frame), Fingerprint(synthetic_frame), len(reference_frame), len(synthetic_frame),
                            tuple(comparisons), reference_report.ToJSON(), synthetic_report.ToJSON(), json.dumps(Environment(), sort_keys=True))
