"""Check ensemble seed identity, aggregation and resource bounds."""

from dataclasses import replace
import hashlib
import json
import random
from statistics import quantiles
from struct import pack

import pytest

from pricegenerator import monte_carlo
from pricegenerator.analysis import Analyze
from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.monte_carlo import CreateEnsembleManifest, DerivePathSeed, ReplayEnsemble, RunEnsemble


@pytest.mark.parametrize("root_seed,path_index,digest", [
    (0, 0, "1de256f0bbaf20eb58ee351277dcace976dea6940fc3365eb9da6f109cef9f69"),
    (-42, 17, "1c8d7de79b2ce719105d9bbbcff7db48907175d8c699cc1ca1bc751a1c466a59"),
    (42, 17, "7d5b8dfeab5d59ecae5b229a238fca80701965731d3f17ebcfbbbcbb1a3b907b"),
])
def test_PathSeedFramingMatchesGoldenDigest(root_seed: int, path_index: int, digest: str) -> None:
    """Pin domain separation, signed hexadecimal framing and byte order."""

    assert DerivePathSeed(root_seed, path_index) == int(digest, 16), "The versioned seed encoding changed"


@pytest.mark.parametrize("root_seed,path_index", [(True, 1), (1.0, 1), (1, True), (1, 1.0), (1, -1)])
def test_PathSeedRejectsAmbiguousInputs(root_seed, path_index) -> None:
    """Require a signed integer root and a nonnegative integer path index."""

    with pytest.raises(ValueError, match="seed|index"):
        DerivePathSeed(root_seed, path_index)


def test_EnsembleMatchesSeparatelyGeneratedPaths() -> None:
    """Cross-check NumPy aggregation with the standard-library quantile oracle."""

    config = GenerationConfig(seed=42, horizon=16, volatility=.03)
    path_count = 4
    report = RunEnsemble(config, path_count=path_count)
    paths = [Generate(replace(config, seed=DerivePathSeed(config.seed, index))) for index in range(path_count)]
    reference_drawdowns = tuple(Analyze(path).maximum_drawdown.value for path in paths)

    assert report.configuration == config and report.path_count == path_count, "The report lost the original run inputs"
    assert report.quantile_levels == (.05, .5, .95), "The quantile levels must remain in declared order"
    assert report.maximum_drawdowns == reference_drawdowns, "Each drawdown must match the corresponding path's close-to-close analysis"
    assert max(reference_drawdowns) > 0, "The oracle fixture must exercise nonzero drawdown"

    closes_by_candle = zip(*(path["close"] for path in paths), strict=True)
    quantiles_by_candle = zip(*report.close_quantiles, strict=True)

    for values, observed in zip(closes_by_candle, quantiles_by_candle, strict=True):
        reference = quantiles(values, n=20, method="inclusive")
        assert observed == pytest.approx((reference[0], reference[9], reference[18])), "Each close quantile must aggregate paths at the same candle"

    reference = quantiles(reference_drawdowns, n=20, method="inclusive")
    assert report.drawdown_quantiles == pytest.approx((reference[0], reference[9], reference[18])), "Drawdown quantiles must aggregate per-path maxima"


def test_EnsembleReproducibilityAndMetadata() -> None:
    """Preserve path order and provenance without consuming ambient randomness."""

    config = GenerationConfig(seed=0, horizon=8, volatility=.03)
    global_state = random.getstate()
    report = RunEnsemble(config, path_count=3)

    assert RunEnsemble(config, path_count=3) == report, "Identical inputs must reproduce the complete report"
    assert RunEnsemble(config, path_count=5).maximum_drawdowns[:3] == report.maximum_drawdowns, "Changing the ensemble size must preserve earlier paths"
    assert RunEnsemble(replace(config, seed=1), path_count=3).close_quantiles != report.close_quantiles, "The root seed must affect stochastic outcomes"
    assert random.getstate() == global_state, "The ensemble consumed process-global randomness"

    payload = json.loads(json.dumps(report.ToDict(), allow_nan=False))
    assert payload["configuration"] == config.ToDict(), "Report serialization must retain the complete root configuration"
    assert payload["seed_derivation"] == monte_carlo.SEED_DERIVATION, "Report serialization must identify path seed derivation"
    assert payload["rng"] == "python.random.Random/MT19937", "Report serialization must identify the path RNG"
    assert "numpy" in payload["environment"], "Report serialization must retain numerical environment provenance"


def test_SingleCandleDrawdownStartsAtTheFirstClose() -> None:
    """Exclude the first open even when the first candle falls sharply."""

    config = GenerationConfig(seed=0, horizon=1, volatility=0, drift=-1)
    report = RunEnsemble(config, path_count=2)

    assert report.close_quantiles == ((report.close_quantiles[0][0],),) * 3, "A deterministic close must give degenerate quantiles"
    assert report.close_quantiles[0][0] < config.initial_price, "The fixture must lose value from the opening price"
    assert report.maximum_drawdowns == (0.0, 0.0), "A single close has zero close-to-close drawdown"
    assert report.drawdown_quantiles == (0.0, 0.0, 0.0), "Degenerate drawdown samples must give degenerate quantiles"


@pytest.mark.parametrize("path_count", [True, 2.0, 1, monte_carlo.MAX_ENSEMBLE_PATHS + 1])
def test_EnsembleRejectsInvalidPathCounts(path_count) -> None:
    """Validate a path count before allocation or generation."""

    with pytest.raises(ValueError, match="path_count"):
        RunEnsemble(GenerationConfig(), path_count=path_count)


def test_EnsembleRejectsUnsupportedConfigAndCandleBudget() -> None:
    """Reject incompatible inputs and a valid shape beyond the total budget."""

    with pytest.raises(TypeError, match="GenerationConfig"):
        RunEnsemble({}, path_count=2)

    oversized = GenerationConfig(horizon=monte_carlo.MAX_ENSEMBLE_CANDLES // 2 + 1)

    with pytest.raises(ValueError, match="total candles"):
        RunEnsemble(oversized, path_count=2)


def test_ParallelReplayMatchesExactSerialReport() -> None:
    """Verify worker-count invariance and the output wire format independently."""

    serial = RunEnsemble(GenerationConfig(seed=-42, horizon=12, volatility=.03), path_count=9)
    manifest = json.loads(json.dumps(CreateEnsembleManifest(serial), allow_nan=False))
    expected = hashlib.sha256(b"pricegenerator-ensemble-output-v1\n")

    for values in (*serial.close_quantiles, serial.maximum_drawdowns, serial.drawdown_quantiles):
        for value in values:
            expected.update(pack("<d", value))

    assert manifest["output_fingerprint"] == expected.hexdigest(), "The binary64 report fingerprint format changed"

    parallel = ReplayEnsemble(manifest, workers=2)
    assert parallel == serial, "Parallel replay must preserve every quantile and path-indexed drawdown"
    assert CreateEnsembleManifest(parallel) == manifest, "Worker count must not alter the experiment identity"


def test_EnsembleReplayRejectsEditedInputsAndOutputs() -> None:
    """Distinguish tampered identity and changed result fingerprints."""

    report = RunEnsemble(GenerationConfig(horizon=2), path_count=3)
    manifest = CreateEnsembleManifest(report)

    with pytest.raises(ValueError, match="identity fingerprint"):
        ReplayEnsemble({**manifest, "path_count": 4})

    with pytest.raises(ValueError, match="output fingerprint"):
        ReplayEnsemble({**manifest, "output_fingerprint": "0" * 64})

    with pytest.raises(ValueError, match="SHA-256 digest"):
        ReplayEnsemble({**manifest, "output_fingerprint": "invalid"})

    with pytest.raises(ValueError, match="manifest_version"):
        ReplayEnsemble({**manifest, "manifest_version": 2})

    with pytest.raises(ValueError, match="complete generation configuration"):
        ReplayEnsemble({**manifest, "configuration": {"seed": 0}})

    with pytest.raises(ValueError, match="complete string-valued environment"):
        ReplayEnsemble({**manifest, "environment": {"python": "3.13"}})


def test_EnsembleReplayRequiresExplicitEnvironmentOverride() -> None:
    """Allow portability verification only with exact result equality."""

    report = RunEnsemble(GenerationConfig(horizon=2), path_count=3)
    other_environment = dict(report.environment, platform="another platform")
    manifest = CreateEnsembleManifest(replace(report, environment=tuple(sorted(other_environment.items()))))

    with pytest.raises(ValueError, match="environment differs"):
        ReplayEnsemble(manifest)

    assert ReplayEnsemble(manifest, strict_environment=False) == report, "An explicit override must verify the result and record the current runtime"


@pytest.mark.parametrize("workers", [True, 2.0, 0, monte_carlo.MAX_ENSEMBLE_WORKERS + 1])
def test_EnsembleRejectsInvalidWorkerCounts(workers) -> None:
    """Validate the worker count before generating paths or allocating arrays."""

    with pytest.raises(ValueError, match="workers"):
        RunEnsemble(GenerationConfig(), path_count=2, workers=workers)
