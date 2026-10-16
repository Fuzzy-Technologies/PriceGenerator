"""Define immutable, serializable inputs for the versioned generation model."""

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class GenerationConfig:
    """Configure continuous positive prices and persistent stochastic activity.

    Drift and volatility are per-candle log-return parameters. Shock probability
    is an independent per-candle Bernoulli probability; its Gaussian log-return
    innovation has standard deviation ``volatility * shock_scale``. Regimes
    switch symmetrically with probability ``1 - regime_persistence`` and scale
    volatility, beginning in the calm state. Price boundaries reflect log prices;
    wicks stop at the boundaries. Each upper/lower wick independently receives
    the outlier multiplier with wick_outlier_probability, separate from shocks.
    Volume is continuous and positive, with a
    persistent log-noise state and activity coupling, capped at volume_ceiling.
    """

    seed: int = 0
    horizon: int = 150
    start: datetime = datetime(2000, 1, 1, tzinfo=timezone.utc)
    timeframe_seconds: int = 3600
    model: str = "regime_v2"
    initial_price: float = 100.0
    price_floor: float = 0.000001
    price_ceiling: float = 1_000_000_000_000.0
    drift: float = 0.0
    volatility: float = 0.01
    regime_persistence: float = 0.95
    regime_scale: float = 3.0
    shock_probability: float = 0.01
    shock_scale: float = 5.0
    wick_scale: float = 0.5
    wick_outlier_probability: float = 0.01
    wick_outlier_scale: float = 5.0
    volume_base: float = 1000.0
    volume_sigma: float = 0.25
    volume_return_coupling: float = 1.0
    volume_persistence: float = 0.5
    volume_ceiling: float = 1_000_000_000_000.0

    def __post_init__(self) -> None:
        """Reject ambiguous, nonfinite, or unsupported generation inputs early."""

        for name in ("seed", "horizon", "timeframe_seconds"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")

        if not 1 <= self.horizon <= 1_000_000:
            raise ValueError("horizon must be between 1 and 1000000")

        if not 1 <= self.timeframe_seconds <= 9_223_372_036:
            raise ValueError("timeframe_seconds must be positive and fit signed nanoseconds")

        if self.model != "regime_v2":
            raise ValueError("model must be 'regime_v2'; historical models are archived only")

        if not isinstance(self.start, datetime) or self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError("start must be a timezone-aware datetime")

        if getattr(self.start, "nanosecond", 0) != 0:
            raise ValueError("start supports at most microsecond precision")

        start = self.start.astimezone(timezone.utc)

        try:
            end = start + timedelta(seconds=self.timeframe_seconds * (self.horizon - 1))

        except OverflowError as error:
            raise ValueError("generation timestamps exceed the supported UTC range") from error

        if start < datetime(1678, 1, 1, tzinfo=timezone.utc) or end >= datetime(2262, 1, 1, tzinfo=timezone.utc):
            raise ValueError("generation timestamps must be between 1678 and 2262 UTC")

        object.__setattr__(self, "start", start)
        numeric_names = {field.name for field in fields(self)} - {"seed", "horizon", "start", "timeframe_seconds", "model"}

        for name in numeric_names:
            value = getattr(self, name)

            try:
                valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

            except OverflowError:
                valid = False

            if not valid:
                raise ValueError(f"{name} must be a finite real number")

            object.__setattr__(self, name, float(value))

        if not 1e-100 <= self.price_floor < self.price_ceiling <= 1e100:
            raise ValueError("price bounds must satisfy 1e-100 <= floor < ceiling <= 1e100")

        if math.log(self.price_floor) >= math.log(self.price_ceiling):
            raise ValueError("price bounds must differ at log-price precision")

        if not self.price_floor <= self.initial_price <= self.price_ceiling:
            raise ValueError("initial_price must lie within the positive price bounds")

        for name in ("regime_persistence", "shock_probability", "wick_outlier_probability", "volume_persistence"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between zero and one")

        for name, maximum in (("volatility", 2), ("shock_scale", 100), ("wick_scale", 100), ("wick_outlier_scale", 100), ("volume_sigma", 2), ("volume_return_coupling", 10)):
            if not 0 <= getattr(self, name) <= maximum:
                raise ValueError(f"{name} must be between zero and {maximum}")

        if not -2 <= self.drift <= 2 or not 1 <= self.regime_scale <= 100:
            raise ValueError("drift must be in [-2, 2] and regime_scale in [1, 100]")

        if not 1e-100 <= self.volume_base <= self.volume_ceiling <= 1e100:
            raise ValueError("volume must satisfy 1e-100 <= base <= ceiling <= 1e100")

    def ToDict(self) -> dict[str, Any]:
        """Return all deterministic inputs as JSON-compatible values."""

        result = asdict(self)
        result["start"] = self.start.isoformat()

        return result

    @classmethod
    def FromDict(cls, configuration: Mapping[str, Any]) -> "GenerationConfig":
        """Construct validated inputs from their complete serialized form."""

        values = dict(configuration)

        if isinstance(values.get("start"), str):
            if any(len(match.group(1)) > 6 for match in re.finditer(r"[.,](\d+)", values["start"])):
                raise ValueError("start supports at most microsecond precision")

            try:
                values["start"] = datetime.fromisoformat(values["start"].replace("Z", "+00:00"))

            except ValueError as error:
                raise ValueError("start must be an ISO timezone-aware datetime") from error

        try:
            return cls(**values)

        except TypeError as error:
            raise ValueError(f"Invalid generation configuration: {error}") from error
