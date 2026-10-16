"""Provide explicit empirical bootstrap and deterministic stress-path models."""

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import math
import json
from typing import Mapping

import numpy as np
import pandas as pd

from pricegenerator._version import __version__
from pricegenerator.market_data import ValidateOHLCV
from pricegenerator.scenario import Environment, Fingerprint


_BOOTSTRAP_SOURCE_SEMANTICS = "regular timestamps; first source row excluded; joint gap/body/wicks/volume; non-circular blocks"


def _ConfigFields(values: Mapping, config_type: type) -> dict:
    """Require a complete standard-JSON configuration without hidden state."""

    if not isinstance(values, Mapping) or set(values) != {item.name for item in fields(config_type)}:
        raise ValueError("Serialized configuration fields must match the complete schema")

    try:
        result = json.loads(json.dumps(dict(values), allow_nan=False))

    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Serialized configuration must contain finite standard-JSON values") from error

    if not isinstance(result["start"], str):
        raise ValueError("Serialized configuration start must be an ISO timestamp string")

    return result


def _Integer(value: int, name: str, minimum: int) -> None:
    """Reject bools and out-of-domain discrete scenario parameters."""

    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _Finite(value: float, name: str, minimum: float | None = None) -> None:
    """Reject nonfinite or out-of-domain continuous parameters."""

    try:
        valid = not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value)

    except OverflowError:
        valid = False

    if not valid:
        raise ValueError(f"{name} must be finite")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _Times(start: datetime | str, count: int, timeframe_seconds: int) -> pd.DatetimeIndex:
    """Construct an explicit regular UTC timeline without wall-clock defaults."""

    try:
        timestamp = pd.Timestamp(start)

    except (TypeError, ValueError) as error:
        raise ValueError("start must be a valid timezone-aware timestamp") from error

    if timestamp.tz is None:
        raise ValueError("start must contain an explicit timezone")

    try:
        return pd.date_range(timestamp.tz_convert("UTC"), periods=count, freq=pd.Timedelta(seconds=timeframe_seconds)).as_unit("ns")

    except (ValueError, OverflowError) as error:
        raise ValueError("Scenario timeline exceeds nanosecond timestamp range") from error


def _PositivePrices(frame: pd.DataFrame) -> None:
    """Enforce the positive-price domain of multiplicative scenario models."""

    prices = frame[["open", "high", "low", "close"]].to_numpy()

    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Multiplicative scenarios require finite strictly positive prices")


@dataclass(frozen=True)
class BootstrapConfig:
    """Declare joint candle resampling and its target timeline.

    Training timestamps must be regular and are never resampled. Geometry,
    previous-close gap and volume are sampled jointly from contiguous source
    blocks, excluding the first source row whose previous close is unknown.
    Blocks do not wrap and their joins may break long serial dependence.
    """

    count: int = 150
    seed: int = 0
    block_length: int = 1
    initial_price: float = 100.0
    start: datetime = datetime(2000, 1, 1, tzinfo=timezone.utc)
    timeframe_seconds: int = 3600

    def __post_init__(self) -> None:
        """Validate all replay-relevant inputs before sampling."""

        _Integer(self.count, "count", 1)
        _Integer(self.seed, "seed", 0)
        _Integer(self.block_length, "block_length", 1)
        _Integer(self.timeframe_seconds, "timeframe_seconds", 1)
        _Finite(self.initial_price, "initial_price", 0)

        if self.count > 1_000_000:
            raise ValueError("count exceeds the one-million-candle limit")

        if self.initial_price == 0:
            raise ValueError("initial_price must be strictly positive")

        timestamp = _Times(self.start, self.count, self.timeframe_seconds)[0]
        object.__setattr__(self, "start", timestamp)

    def ToDict(self) -> dict:
        """Return a JSON-compatible configuration with explicit UTC start."""

        result = asdict(self)
        result["start"] = self.start.isoformat()

        return result

    @classmethod
    def FromDict(cls, values: Mapping) -> "BootstrapConfig":
        """Reconstruct and validate a serialized bootstrap configuration."""

        parameters = _ConfigFields(values, cls)

        try:
            return cls(**parameters)

        except TypeError as error:
            raise ValueError("Invalid bootstrap configuration fields") from error


def Bootstrap(reference: pd.DataFrame, config: BootstrapConfig | None = None) -> pd.DataFrame:
    """Resample joint normalized OHLC geometry, price gaps and observed volume."""

    settings = config if config is not None else BootstrapConfig()

    if not isinstance(settings, BootstrapConfig):
        raise TypeError("Bootstrap requires a BootstrapConfig")

    source = ValidateOHLCV(reference)
    _PositivePrices(source)

    if len(source) < 3:
        raise ValueError("Bootstrap requires at least three source rows")

    times = source["datetime"].astype("int64").to_numpy()

    if not np.all(np.diff(times) == times[1] - times[0]):
        raise ValueError("Bootstrap reference timestamp gaps are unsupported")

    if settings.block_length > len(source) - 1:
        raise ValueError("block_length exceeds available joint source candles")

    previous = source["close"].to_numpy()[:-1]
    source = source.iloc[1:]
    opens = source["open"].to_numpy()
    closes = source["close"].to_numpy()
    geometry = np.column_stack((np.log(opens) - np.log(previous), np.log(closes) - np.log(opens),
                                np.log(source["high"].to_numpy()) - np.log(np.maximum(opens, closes)),
                                np.log(source["low"].to_numpy()) - np.log(np.minimum(opens, closes)),
                                source["volume"].to_numpy()))
    rng = np.random.Generator(np.random.PCG64(settings.seed))
    block_count = math.ceil(settings.count / settings.block_length)
    starts = rng.integers(0, len(source) - settings.block_length + 1, size=block_count)
    indices = (starts[:, None] + np.arange(settings.block_length)).reshape(-1)[:settings.count]
    rows = []
    previous_close = settings.initial_price

    try:
        for gap, body, upper_log_ratio, lower_log_ratio, volume in geometry[indices]:
            log_opening = math.log(previous_close) + float(gap)
            log_closing = log_opening + float(body)
            opening = math.exp(log_opening)
            closing = math.exp(log_closing)
            high = math.exp(max(log_opening, log_closing) + float(upper_log_ratio))
            low = math.exp(min(log_opening, log_closing) + float(lower_log_ratio))
            rows.append((opening, high, low, closing, volume))
            previous_close = closing

    except OverflowError as error:
        raise ValueError("Bootstrap path overflowed; shorten horizon or rebase reference") from error

    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    frame.insert(0, "datetime", _Times(settings.start, settings.count, settings.timeframe_seconds))
    _PositivePrices(frame)

    return ValidateOHLCV(frame)


@dataclass(frozen=True)
class ScriptStep:
    """Apply a one-bar opening log jump and optional persistent regime settings."""

    index: int
    log_jump: float = 0.0
    drift: float | None = None
    volume: float | None = None

    def __post_init__(self) -> None:
        """Validate an explicit event without assigning a market probability."""

        _Integer(self.index, "step index", 0)
        _Finite(self.log_jump, "log_jump")

        if self.drift is not None:
            _Finite(self.drift, "step drift")

        if self.volume is not None:
            _Finite(self.volume, "step volume", 0)


@dataclass(frozen=True)
class ScriptedConfig:
    """Declare a deterministic piecewise drift path with explicit shock events."""

    count: int = 150
    initial_price: float = 100.0
    start: datetime = datetime(2000, 1, 1, tzinfo=timezone.utc)
    timeframe_seconds: int = 3600
    drift: float = 0.0
    wick_fraction: float = .01
    volume: float = 1000.0
    steps: tuple[ScriptStep, ...] = ()

    def __post_init__(self) -> None:
        """Validate immutable event order and complete timeline inputs."""

        _Integer(self.count, "count", 1)
        _Integer(self.timeframe_seconds, "timeframe_seconds", 1)
        _Finite(self.initial_price, "initial_price", 0)
        _Finite(self.drift, "drift")
        _Finite(self.wick_fraction, "wick_fraction", 0)
        _Finite(self.volume, "volume", 0)

        if self.count > 1_000_000:
            raise ValueError("count exceeds the one-million-candle limit")

        if self.initial_price == 0 or self.wick_fraction >= 1:
            raise ValueError("Price must be positive and wick_fraction less than one")

        if not isinstance(self.steps, tuple) or any(not isinstance(step, ScriptStep) for step in self.steps):
            raise ValueError("steps must be an immutable tuple of ScriptStep values")

        indices = [step.index for step in self.steps]

        if indices != sorted(set(indices)) or any(index >= self.count for index in indices):
            raise ValueError("Step indices must be unique, increasing and inside the horizon")

        timestamp = _Times(self.start, self.count, self.timeframe_seconds)[0]
        object.__setattr__(self, "start", timestamp)

    def ToDict(self) -> dict:
        """Serialize the path and all shock/regime event parameters."""

        result = asdict(self)
        result["start"] = self.start.isoformat()
        result["steps"] = [asdict(step) for step in self.steps]

        return result

    @classmethod
    def FromDict(cls, values: Mapping) -> "ScriptedConfig":
        """Load a strict event schema into immutable validated inputs."""

        parameters = _ConfigFields(values, cls)
        steps = parameters["steps"]
        expected_step_fields = {item.name for item in fields(ScriptStep)}

        if not isinstance(steps, list) or any(not isinstance(step, dict) or set(step) != expected_step_fields for step in steps):
            raise ValueError("Serialized steps must contain the complete event schema")

        try:
            parameters["steps"] = tuple(ScriptStep(**step) for step in steps)

            return cls(**parameters)

        except TypeError as error:
            raise ValueError("Invalid scripted configuration fields") from error


def Scripted(config: ScriptedConfig | None = None) -> pd.DataFrame:
    """Construct step, shock and regime fixtures without forcing an endpoint."""

    settings = config if config is not None else ScriptedConfig()

    if not isinstance(settings, ScriptedConfig):
        raise TypeError("Scripted requires a ScriptedConfig")

    events = {step.index: step for step in settings.steps}
    previous_close = settings.initial_price
    drift = settings.drift
    volume = settings.volume
    rows = []

    try:
        for index in range(settings.count):
            event = events.get(index)
            opening = previous_close

            if event is not None:
                opening *= math.exp(event.log_jump)
                drift = drift if event.drift is None else event.drift
                volume = volume if event.volume is None else event.volume

            closing = opening * math.exp(drift)
            high = max(opening, closing) * (1 + settings.wick_fraction)
            low = min(opening, closing) * (1 - settings.wick_fraction)
            rows.append((opening, high, low, closing, volume))
            previous_close = closing

    except OverflowError as error:
        raise ValueError("Scripted path overflowed; reduce drift, shock size or horizon") from error

    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    frame.insert(0, "datetime", _Times(settings.start, settings.count, settings.timeframe_seconds))
    _PositivePrices(frame)

    return ValidateOHLCV(frame)


def CreateBootstrapManifest(reference: pd.DataFrame, config: BootstrapConfig,
                            data: pd.DataFrame | None = None) -> dict:
    """Record empirical source identity, model, RNG and exact resampling inputs."""

    generated = Bootstrap(reference, config)

    if data is not None and Fingerprint(data) != Fingerprint(generated):
        raise ValueError("Supplied data does not match bootstrap inputs")

    return {"manifest_version": 1, "model": "bootstrap_v1", "model_version": 1,
            "rng": "numpy.PCG64", "library_version": __version__, "environment": Environment(),
            "config": config.ToDict(), "source_fingerprint": Fingerprint(reference),
            "output_fingerprint": Fingerprint(generated),
            "source_semantics": _BOOTSTRAP_SOURCE_SEMANTICS}


def ReplayBootstrap(manifest: Mapping, reference: pd.DataFrame) -> pd.DataFrame:
    """Replay against the identical explicit reference, rejecting version drift."""

    manifest = _CheckManifest(manifest, "bootstrap_v1", "numpy.PCG64")

    if manifest.get("source_fingerprint") != Fingerprint(reference):
        raise ValueError("Bootstrap reference differs from manifest")

    data = Bootstrap(reference, BootstrapConfig.FromDict(manifest["config"]))

    if manifest.get("output_fingerprint") != Fingerprint(data):
        raise ValueError("Bootstrap replay fingerprint mismatch")

    return data


def CreateScriptedManifest(config: ScriptedConfig, data: pd.DataFrame | None = None) -> dict:
    """Record every designed event and complete deterministic path inputs."""

    generated = Scripted(config)

    if data is not None and Fingerprint(data) != Fingerprint(generated):
        raise ValueError("Supplied data does not match scripted inputs")

    return {"manifest_version": 1, "model": "scripted_v1", "model_version": 1, "rng": "none",
            "library_version": __version__, "environment": Environment(), "config": config.ToDict(), "output_fingerprint": Fingerprint(generated)}


def _CheckManifest(manifest: Mapping, model: str, rng: str) -> dict:
    """Reject incompatible scenario identities before executing a model."""

    expected = {"manifest_version": 1, "model": model, "model_version": 1, "rng": rng, "library_version": __version__,
                "environment": Environment()}
    required = set(expected) | {"config", "output_fingerprint"}

    if model == "bootstrap_v1":
        expected["source_semantics"] = _BOOTSTRAP_SOURCE_SEMANTICS
        required |= {"source_fingerprint", "source_semantics"}

    if not isinstance(manifest, Mapping) or set(manifest) != required:
        raise ValueError("Scenario manifest fields must match the complete schema")

    try:
        payload = json.loads(json.dumps(dict(manifest), allow_nan=False))

    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Scenario manifest requires finite standard-JSON values") from error

    if any(type(payload[key]) is not int for key in ("manifest_version", "model_version")) or any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("Unsupported or mismatched scenario manifest identity")

    return payload


def ReplayScripted(manifest: Mapping) -> pd.DataFrame:
    """Reconstruct a deterministic stress fixture and verify its output digest."""

    manifest = _CheckManifest(manifest, "scripted_v1", "none")
    data = Scripted(ScriptedConfig.FromDict(manifest["config"]))

    if manifest.get("output_fingerprint") != Fingerprint(data):
        raise ValueError("Scripted replay fingerprint mismatch")

    return data
