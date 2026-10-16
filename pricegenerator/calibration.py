"""Extract versioned moment profiles and evaluate a restricted fitted model."""

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
import math
import re
from typing import Mapping

import numpy as np
import pandas as pd

from pricegenerator.config import GenerationConfig
from pricegenerator.evaluation import Compare, ComparisonReport
from pricegenerator.generation import Generate
from pricegenerator.market_data import ValidateOHLCV
from pricegenerator.scenario import Fingerprint


_FIXED = (("regime_scale", 1.0), ("shock_probability", 0.0),
          ("wick_outlier_probability", 0.0), ("volume_sigma", 0.0),
          ("volume_return_coupling", 0.0), ("volume_persistence", 0.0))
_UNIDENTIFIED = ("regime_persistence", "regime_scale", "shock_probability", "shock_scale",
                 "wick_scale", "wick_outlier_probability", "wick_outlier_scale",
                 "volume_sigma", "volume_return_coupling", "volume_persistence")


def _RegularTimeframeNanoseconds(frame: pd.DataFrame) -> int:
    """Check exact spacing with Python integers, including broad UTC windows."""

    instants = [int(value) for value in frame["datetime"].array.asi8]
    differences = [current - previous for previous, current in zip(instants[:-1], instants[1:])]

    if len(set(differences)) != 1:
        raise ValueError("Profile and evaluation sources must have a regular timeframe")

    return differences[0]


@dataclass(frozen=True)
class Profile:
    """Store finite observable moments and the exact training source identity.

    This profile fits a restricted model using candle-body log-return mean and
    population standard deviation and arithmetic mean volume. It does not
    identify latent regimes, shocks, wick tails or volume dependence.
    """

    schema_version: int
    model: str
    model_version: int
    source_start: str
    source_end: str
    timeframe_seconds: float
    source_rows: int
    source_fingerprint: str
    drift: float
    volatility: float
    volume_base: float
    data_schema: str = "datetime:UTC-ns;OHLCV:float64/v1"
    estimator: str = "body-log-return-population-moments/volume-arithmetic-mean/v1"
    source_semantics: str = "training-only; regular bars; candle-body returns exclude inter-bar price gaps"

    def __post_init__(self) -> None:
        """Reject unsupported, ambiguous or nonfinite serialized profiles."""

        if type(self.schema_version) is not int or type(self.model_version) is not int or self.schema_version != 1 or self.model != "regime_v2" or self.model_version != 2:
            raise ValueError("Unsupported profile schema or model version")

        if isinstance(self.source_rows, bool) or not isinstance(self.source_rows, int) or self.source_rows < 3:
            raise ValueError("A profile requires at least three training rows")

        for name in ("timeframe_seconds", "drift", "volatility", "volume_base"):
            value = getattr(self, name)

            try:
                valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

            except OverflowError:
                valid = False

            if not valid:
                raise ValueError(f"Profile {name} must be a finite number")

        if not 0 < self.timeframe_seconds < 20_000_000_000 or self.volatility < 0 or self.volume_base <= 0:
            raise ValueError("Profile timeframe/volume must be positive and volatility nonnegative")

        if not -2 <= self.drift <= 2 or self.volatility > 2 or not 1e-100 <= self.volume_base <= 1e100:
            raise ValueError("Profile moments exceed the supported regime_v2 parameter domain")

        if not isinstance(self.source_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", self.source_fingerprint):
            raise ValueError("Profile source_fingerprint must be a SHA-256 digest")

        if not isinstance(self.source_start, str) or not isinstance(self.source_end, str):
            raise ValueError("Profile source window must contain ISO timestamp strings")

        try:
            start = pd.Timestamp(self.source_start).as_unit("ns")
            end = pd.Timestamp(self.source_end).as_unit("ns")

        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Invalid source window") from error

        if start.tz is None or end.tz is None or end <= start:
            raise ValueError("Profile source window must be timezone-aware and increasing")

        if end.value - start.value != round(self.timeframe_seconds * 1e9) * (self.source_rows - 1):
            raise ValueError("Profile timeframe and row count do not match its source window")

        if self.data_schema != "datetime:UTC-ns;OHLCV:float64/v1" or self.estimator != "body-log-return-population-moments/volume-arithmetic-mean/v1":
            raise ValueError("Unsupported profile data schema or estimator")

        if self.source_semantics != "training-only; regular bars; candle-body returns exclude inter-bar price gaps":
            raise ValueError("Unsupported profile training semantics")

    def ToDict(self) -> dict:
        """Return a versioned JSON-compatible profile without opaque state."""

        return asdict(self)

    @classmethod
    def FromDict(cls, values: Mapping) -> "Profile":
        """Load an exact supported profile schema and reject unknown fields."""

        if not isinstance(values, Mapping) or set(values) != {item.name for item in fields(cls)}:
            raise ValueError("Profile fields must match the complete serialized schema")

        try:
            return cls(**dict(values))

        except TypeError as error:
            raise ValueError("Invalid profile fields") from error

    def Reference(self) -> str:
        """Hash the complete serialized profile for scenario provenance."""

        payload = json.dumps(self.ToDict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def ToConfig(self, base: GenerationConfig | None = None) -> GenerationConfig:
        """Apply fitted moments and declared neutral restrictions to a base config.

        Wick scale and bounds remain explicit base configuration assumptions.
        No fitted value estimates latent-state transition or tail parameters.
        """

        config = base if base is not None else GenerationConfig()

        if not isinstance(config, GenerationConfig):
            raise TypeError("Profile.ToConfig requires a GenerationConfig base")

        if config.model != self.model:
            raise ValueError("Profile and generation model must match")

        return replace(config, drift=self.drift, volatility=self.volatility,
                       volume_base=self.volume_base, **dict(_FIXED))

    def ManifestMetadata(self) -> dict:
        """Provide explicit profile identity and estimation limits for manifests."""

        return {"profile": self.ToDict(), "profile_reference": self.Reference(),
                "fitted_parameters": ["drift", "volatility", "volume_base"],
                "fixed_restrictions": dict(_FIXED), "unidentified_parameters": list(_UNIDENTIFIED)}


def ExtractProfile(frame: pd.DataFrame, *, model: str = "regime_v2") -> Profile:
    """Extract only modeled observable moments from a regular training window."""

    source = ValidateOHLCV(frame)

    if model != "regime_v2":
        raise ValueError("Moment profiles support only regime_v2")

    if len(source) < 3:
        raise ValueError("Profile extraction requires at least three rows")

    if (source[["open", "high", "low", "close"]].to_numpy() <= 0).any():
        raise ValueError("regime_v2 profiles require strictly positive source prices")

    timeframe_ns = _RegularTimeframeNanoseconds(source)
    timeframe_seconds = timeframe_ns / 1e9

    if round(timeframe_seconds * 1e9) != timeframe_ns:
        raise ValueError("Source timeframe is not exactly representable by the profile schema")

    returns = np.log(source["close"].to_numpy()) - np.log(source["open"].to_numpy())

    return Profile(1, model, 2, source["datetime"].iloc[0].isoformat(), source["datetime"].iloc[-1].isoformat(),
                   timeframe_seconds, len(source), Fingerprint(source), float(returns.mean()),
                   float(returns.std(ddof=0)), float(source["volume"].mean()))


def ChronologicalSplit(frame: pd.DataFrame, *, holdout_fraction: float = .25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detach chronological training and evaluation windows without overlap."""

    source = ValidateOHLCV(frame)

    if not math.isfinite(holdout_fraction) or not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be strictly between zero and one")

    split = math.floor(len(source) * (1 - holdout_fraction))

    if min(split, len(source) - split) < 3:
        raise ValueError("Both chronological windows require at least three rows")

    return source.iloc[:split].reset_index(drop=True).copy(), source.iloc[split:].reset_index(drop=True).copy()


@dataclass(frozen=True)
class CalibrationReport:
    """Keep fitted source, training diagnostics and unseen evaluation separate."""

    profile: Profile
    training: ComparisonReport
    holdout: ComparisonReport
    training_manifest_json: str
    holdout_manifest_json: str

    def ToDict(self) -> dict:
        """Return reproducible experiments with explicit scientific limits."""

        return {"profile": self.profile.ToDict(), "training": self.training.ToDict(),
                "holdout": self.holdout.ToDict(), "training_manifest": json.loads(self.training_manifest_json),
                "holdout_manifest": json.loads(self.holdout_manifest_json),
                "limitation": "Restricted observable-moment fit, not full parameter identification or forecast validation"}


def Calibrate(training: pd.DataFrame, holdout: pd.DataFrame, *, base: GenerationConfig | None = None,
              tolerances: Mapping[str, float] | None = None) -> CalibrationReport:
    """Fit training only and compare a separately generated chronological holdout.

    Holdout values affect only evaluation, its starting observed price and its
    output time window. They never update fitted moments or hidden model state.
    The two generated paths use distinct explicit seeds.
    """

    from pricegenerator.scenario import CreateManifest

    train = ValidateOHLCV(training)
    test = ValidateOHLCV(holdout)

    if len(train) < 3 or len(test) < 3:
        raise ValueError("Training and holdout require at least three rows each")

    if train["datetime"].iloc[-1] >= test["datetime"].iloc[0]:
        raise ValueError("Training must strictly precede holdout without timestamp overlap")

    profile = ExtractProfile(train)
    holdout_timeframe_ns = _RegularTimeframeNanoseconds(test)
    training_timeframe_ns = _RegularTimeframeNanoseconds(train)

    if training_timeframe_ns != holdout_timeframe_ns:
        raise ValueError("Training and holdout must have the same timeframe")

    config = profile.ToConfig(base)

    if training_timeframe_ns % 1_000_000_000:
        raise ValueError("Generation calibration requires whole-second source timeframes")

    if any(int(frame["datetime"].array.asi8[0]) % 1000 for frame in (train, test)):
        raise ValueError("Generation calibration requires microsecond-aligned starting timestamps")

    timeframe_seconds = training_timeframe_ns // 1_000_000_000
    train_config = replace(config, horizon=len(train), start=train["datetime"].iloc[0].to_pydatetime(),
                           timeframe_seconds=timeframe_seconds, initial_price=float(train["open"].iloc[0]))
    test_config = replace(config, seed=config.seed + 1, horizon=len(test), start=test["datetime"].iloc[0].to_pydatetime(),
                          timeframe_seconds=timeframe_seconds, initial_price=float(test["open"].iloc[0]))
    train_generated = Generate(train_config)
    test_generated = Generate(test_config)
    metadata = profile.ManifestMetadata()

    return CalibrationReport(profile, Compare(train, train_generated, tolerances=tolerances),
                             Compare(test, test_generated, tolerances=tolerances),
                             json.dumps(CreateManifest(train_config, train_generated, metadata=metadata), sort_keys=True),
                             json.dumps(CreateManifest(test_config, test_generated, metadata=metadata), sort_keys=True))
