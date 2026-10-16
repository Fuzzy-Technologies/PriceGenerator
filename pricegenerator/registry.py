"""Describe admitted model semantics and the limits of their evidence."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelInfo:
    """Record a model's reproducibility and suitability contract."""

    model: str
    version: int
    rng: str
    status: str
    supported_parameters: tuple[str, ...]
    suitability: tuple[str, ...]
    limitations: tuple[str, ...]
    required_validation: tuple[str, ...]

    def ToDict(self) -> dict:
        """Return an independent JSON-compatible description."""

        result = asdict(self)

        for key, value in result.items():
            if isinstance(value, tuple):
                result[key] = list(value)

        return result


_VALIDATION = ("OHLCV invariants", "seed replay", "declared marginal metrics", "temporal dependence", "independent holdout")
_MODELS = (
    ModelInfo("regime_v2", 2, "python.random.Random/MT19937", "experimental",
              ("seed", "horizon", "start", "timeframe_seconds", "model", "initial_price", "price_floor", "price_ceiling", "drift", "volatility", "regime_persistence", "regime_scale", "shock_probability", "shock_scale", "wick_scale", "wick_outlier_probability", "wick_outlier_scale", "volume_base", "volume_sigma", "volume_return_coupling", "volume_persistence", "volume_ceiling"),
              ("deterministic software fixtures", "regime and shock sensitivity experiments"),
              ("not a forecast", "no market microstructure", "moment calibration does not identify latent regimes"), _VALIDATION),
    ModelInfo("bootstrap_v1", 1, "numpy.PCG64", "experimental",
              ("count", "seed", "block_length", "initial_price", "start", "timeframe_seconds"),
              ("empirical joint candle and volume resampling", "block dependence sensitivity"),
              ("cannot create unseen candle geometry", "block boundaries break long dependence", "reference gaps are rejected"), _VALIDATION),
    ModelInfo("scripted_v1", 1, "none", "experimental",
              ("count", "initial_price", "start", "timeframe_seconds", "drift", "wick_fraction", "volume", "steps"),
              ("deterministic stress fixtures", "explicit step and drift transitions"),
              ("designed paths have no estimated market probability", "no endpoint targeting"),
              ("OHLCV invariants", "exact replay", "event timing")),
)


def ListModels() -> tuple[ModelInfo, ...]:
    """Return the immutable modern model registry without selecting a default."""

    return _MODELS


def GetModel(model: str) -> ModelInfo:
    """Resolve a modern model or reject unknown and historical runtimes."""

    for item in _MODELS:
        if item.model == model:
            return item

    raise ValueError(f"Unknown modern model: {model!r}; historical models are evidence only")
