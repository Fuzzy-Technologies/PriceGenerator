"""Summarize bounded, seeded ensembles of synthetic closing-price paths."""

from dataclasses import dataclass, replace
import hashlib
from typing import Any

import numpy as np

from pricegenerator._version import __version__
from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.models import RNG_ID
from pricegenerator.scenario import Environment


SEED_DERIVATION = "pricegenerator-monte-carlo-path-seed-v1"
QUANTILE_LEVELS = (0.05, 0.5, 0.95)
QUANTILE_METHOD = "linear"
MAX_ENSEMBLE_PATHS = 10_000
MAX_ENSEMBLE_CANDLES = 1_000_000


@dataclass(frozen=True)
class EnsembleReport:
    """Record synthetic quantiles and immutable run inputs and provenance.

    Close quantiles are ordered by level, with one value per candle position.
    Maximum drawdowns are nonnegative fractions in path-index order. Their
    quantiles use the same levels and linear sample interpolation.
    """

    configuration: GenerationConfig
    path_count: int
    close_quantiles: tuple[tuple[float, ...], ...]
    maximum_drawdowns: tuple[float, ...]
    drawdown_quantiles: tuple[float, ...]
    environment: tuple[tuple[str, str], ...]
    quantile_levels: tuple[float, ...] = QUANTILE_LEVELS
    quantile_method: str = QUANTILE_METHOD
    metric_version: str = "close-ensemble-v1"
    seed_derivation: str = SEED_DERIVATION
    rng: str = RNG_ID
    library_version: str = __version__

    def ToDict(self) -> dict[str, Any]:
        """Return a JSON-compatible snapshot of the results and run metadata."""

        result = dict(vars(self))
        result["configuration"] = self.configuration.ToDict()
        result["environment"] = dict(self.environment)

        return result


def DerivePathSeed(root_seed: int, path_index: int) -> int:
    """Derive a path seed independently of run size and execution order."""

    if type(root_seed) is not int:
        raise ValueError("root_seed must be an integer")

    if type(path_index) is not int or path_index < 0:
        raise ValueError("path_index must be a nonnegative integer")

    payload = f"{SEED_DERIVATION}\n{root_seed:x}\n{path_index:x}\n".encode("ascii")

    return int.from_bytes(hashlib.sha256(payload).digest(), "big")


def RunEnsemble(config: GenerationConfig, *, path_count: int) -> EnsembleReport:
    """Generate seeded paths and summarize closes and close-to-close drawdowns.

    The configuration seed is the root seed. Each path uses an isolated RNG
    through Generate. Only the close matrix and one OHLCV path are retained
    during accumulation. Drawdown starts at the first close and uses the
    running peak of closes, matching Analyze's positive-price convention.
    """

    if not isinstance(config, GenerationConfig):
        raise TypeError("RunEnsemble requires a GenerationConfig")

    if type(path_count) is not int or not 2 <= path_count <= MAX_ENSEMBLE_PATHS:
        raise ValueError(f"path_count must be an integer between 2 and {MAX_ENSEMBLE_PATHS}")

    if path_count * config.horizon > MAX_ENSEMBLE_CANDLES:
        raise ValueError(f"The ensemble supports at most {MAX_ENSEMBLE_CANDLES} total candles")

    close_paths = np.empty((path_count, config.horizon), dtype=np.float64)
    drawdowns = np.empty(path_count, dtype=np.float64)

    for path_index in range(path_count):
        path_config = replace(config, seed=DerivePathSeed(config.seed, path_index))
        closes = close_paths[path_index]
        closes[:] = Generate(path_config)["close"].to_numpy(copy=False)
        running_peaks = np.maximum.accumulate(closes)
        drawdowns[path_index] = np.max(1 - closes / running_peaks)

    close_quantiles = np.quantile(close_paths, QUANTILE_LEVELS, axis=0, method=QUANTILE_METHOD, overwrite_input=True)
    drawdown_quantiles = np.quantile(drawdowns, QUANTILE_LEVELS, method=QUANTILE_METHOD)

    return EnsembleReport(
        configuration=config,
        path_count=path_count,
        close_quantiles=tuple(tuple(series) for series in close_quantiles.tolist()),
        maximum_drawdowns=tuple(drawdowns.tolist()),
        drawdown_quantiles=tuple(drawdown_quantiles.tolist()),
        environment=tuple(sorted(Environment().items())),
    )
