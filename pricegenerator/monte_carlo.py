"""Summarize bounded, seeded ensembles of synthetic closing-price paths."""

from collections.abc import Iterator, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import re
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
MAX_ENSEMBLE_WORKERS = 8
METRIC_VERSION = "close-ensemble-v1"
MANIFEST_VERSION = 1


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
    metric_version: str = METRIC_VERSION
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


def _Path(config: GenerationConfig, index: int):
    """Generate the complete OHLCV path for one stable ensemble index."""

    return Generate(replace(config, seed=DerivePathSeed(config.seed, index)))


def _PathCloses(index: int, *, config: GenerationConfig) -> np.ndarray:
    """Return only the closing prices across the worker boundary."""

    return _Path(config, index)["close"].to_numpy(copy=False)


def _OrderedCloses(config: GenerationConfig, path_count: int, workers: int) -> Iterator[np.ndarray]:
    """Keep result order independent of which worker finishes first."""

    generate = partial(_PathCloses, config=config)
    indices = range(path_count)

    if workers == 1:
        yield from map(generate, indices)

    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            chunksize = max(1, min(64, path_count // (4 * workers)))
            yield from executor.map(generate, indices, chunksize=chunksize)


def RunEnsemble(config: GenerationConfig, *, path_count: int, workers: int = 1) -> EnsembleReport:
    """Generate seeded paths and summarize closes and close-to-close drawdowns.

    The configuration seed is the root seed. Each path uses an isolated RNG
    through Generate. Each worker generates one OHLCV path at a time and
    returns only closes. Drawdown starts at the first close and uses the
    running peak of closes, matching Analyze's positive-price convention.
    """

    if not isinstance(config, GenerationConfig):
        raise TypeError("RunEnsemble requires a GenerationConfig")

    if type(path_count) is not int or not 2 <= path_count <= MAX_ENSEMBLE_PATHS:
        raise ValueError(f"path_count must be an integer between 2 and {MAX_ENSEMBLE_PATHS}")

    if type(workers) is not int or not 1 <= workers <= MAX_ENSEMBLE_WORKERS:
        raise ValueError(f"workers must be an integer between 1 and {MAX_ENSEMBLE_WORKERS}")

    if path_count * config.horizon > MAX_ENSEMBLE_CANDLES:
        raise ValueError(f"The ensemble supports at most {MAX_ENSEMBLE_CANDLES} total candles")

    close_paths = np.empty((path_count, config.horizon), dtype=np.float64)
    drawdowns = np.empty(path_count, dtype=np.float64)

    for path_index, closes in enumerate(_OrderedCloses(config, path_count, min(workers, path_count))):
        close_paths[path_index] = closes
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


def _IdentityFingerprint(identity: Mapping[str, Any]) -> str:
    """Hash a canonical JSON snapshot of deterministic experiment inputs."""

    try:
        canonical = json.dumps(dict(identity), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)

    except (TypeError, ValueError) as error:
        raise ValueError("ensemble manifest must contain standard JSON values") from error

    return hashlib.sha256(b"pricegenerator-ensemble-identity-v1\n" + canonical.encode("ascii")).hexdigest()


def _OutputFingerprint(report: EnsembleReport) -> str:
    """Hash exact little-endian binary64 arrays in declared result order."""

    digest = hashlib.sha256(b"pricegenerator-ensemble-output-v1\n")

    for values in (report.close_quantiles, report.maximum_drawdowns, report.drawdown_quantiles):
        digest.update(np.asarray(values, dtype="<f8").tobytes())

    return digest.hexdigest()


def CreateEnsembleManifest(report: EnsembleReport) -> dict[str, Any]:
    """Record complete experiment inputs and fingerprints for exact replay."""

    if not isinstance(report, EnsembleReport):
        raise TypeError("CreateEnsembleManifest requires an EnsembleReport")

    identity = {
        "manifest_version": MANIFEST_VERSION,
        "configuration": report.configuration.ToDict(),
        "environment": dict(report.environment),
        "path_count": report.path_count,
        "seed_derivation": report.seed_derivation,
        "rng": report.rng,
        "library_version": report.library_version,
        "metric_version": report.metric_version,
        "quantile_method": report.quantile_method,
        "quantile_levels": list(report.quantile_levels),
    }

    return {**identity, "identity_fingerprint": _IdentityFingerprint(identity), "output_fingerprint": _OutputFingerprint(report)}


def ReplayEnsemble(manifest: Mapping[str, Any], *, workers: int = 1, strict_environment: bool = True) -> EnsembleReport:
    """Regenerate an experiment and reject changes to its recorded result."""

    supported = {
        "manifest_version": MANIFEST_VERSION,
        "seed_derivation": SEED_DERIVATION,
        "rng": RNG_ID,
        "library_version": __version__,
        "metric_version": METRIC_VERSION,
        "quantile_method": QUANTILE_METHOD,
        "quantile_levels": list(QUANTILE_LEVELS),
    }
    identity_fields = set(supported) | {"configuration", "environment", "path_count"}

    if not isinstance(manifest, Mapping) or set(manifest) != identity_fields | {"identity_fingerprint", "output_fingerprint"}:
        raise ValueError("ensemble manifest fields are incomplete or unsupported")

    if type(manifest["manifest_version"]) is not int:
        raise ValueError("ensemble manifest version must be an integer")

    for name, value in supported.items():
        if manifest[name] != value:
            raise ValueError(f"ensemble manifest {name} is incompatible with this runtime")

    configuration = manifest["configuration"]
    environment = manifest["environment"]
    runtime = Environment()

    if not isinstance(configuration, Mapping) or set(configuration) != set(GenerationConfig().ToDict()):
        raise ValueError("ensemble manifest must contain the complete generation configuration")

    if not isinstance(environment, Mapping) or set(environment) != set(runtime) or not all(isinstance(value, str) for value in environment.values()):
        raise ValueError("ensemble manifest must contain the complete string-valued environment")

    if _IdentityFingerprint({name: manifest[name] for name in identity_fields}) != manifest["identity_fingerprint"]:
        raise ValueError("ensemble identity fingerprint does not match the manifest")

    output_fingerprint = manifest["output_fingerprint"]

    if not isinstance(output_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", output_fingerprint) is None:
        raise ValueError("ensemble output fingerprint must be a SHA-256 digest")

    if strict_environment and environment != runtime:
        raise ValueError("ensemble manifest environment differs; use strict_environment=False to verify portable replay")

    report = RunEnsemble(GenerationConfig.FromDict(configuration), path_count=manifest["path_count"], workers=workers)

    if _OutputFingerprint(report) != output_fingerprint:
        raise ValueError("replayed ensemble output fingerprint does not match the manifest")

    return report


def ChartEnsemble(report: EnsembleReport, output: str | Path) -> Path:
    """Export pointwise close quantiles over the actual path-zero OHLCV chart."""

    from pricegenerator.rendering.api import Chart
    from pricegenerator.rendering.spec import ChartSeries

    if not isinstance(report, EnsembleReport):
        raise TypeError("ChartEnsemble requires an EnsembleReport")

    kind = "points" if report.configuration.horizon == 1 else "line"
    series = tuple(
        ChartSeries(f"close-p{level * 100:02.0f}", f"P{level * 100:02.0f} close", values, kind=kind)
        for level, values in zip(report.quantile_levels, report.close_quantiles, strict=True)
    )

    return Chart(
        _Path(report.configuration, 0), output, view=False, series=series,
        title=f"Monte Carlo | {report.configuration.model} | {report.path_count:,} paths",
        summary=(
            "Candles and volume: ensemble path 0. Lines or points: close quantiles across all paths.",
            "P05-P95 is a pointwise synthetic range. Simultaneous path coverage has not been estimated.",
        ),
    )
