"""Verify explicit empirical and scripted model semantics and replay failures."""

from dataclasses import FrozenInstanceError, replace
import json
import math

import numpy as np
import pandas as pd
import pytest

from pricegenerator.extended_models import (
    Bootstrap, BootstrapConfig, CreateBootstrapManifest, CreateScriptedManifest,
    ReplayBootstrap, ReplayScripted, Scripted, ScriptedConfig, ScriptStep,
)
from pricegenerator.registry import GetModel, ListModels
from pricegenerator.scenario import Fingerprint


def _Reference() -> pd.DataFrame:
    """Create distinct joint geometry, volume and price-gap observations."""

    return Scripted(ScriptedConfig(count=12, drift=.01, steps=(
        ScriptStep(2, log_jump=.03, drift=-.02, volume=200),
        ScriptStep(5, log_jump=-.01, drift=.04, volume=300),
        ScriptStep(8, drift=-.01, volume=400),
    )))


def test_BootstrapJointGeometryReplayAndIsolation() -> None:
    """Preserve joint source candles and avoid mutation or global RNG state."""

    reference = _Reference()
    original = reference.copy(deep=True)
    config = BootstrapConfig(count=40, seed=0, block_length=3, initial_price=90)
    state = np.random.get_state()
    generated = Bootstrap(reference, config)
    following = np.random.get_state()
    manifest = CreateBootstrapManifest(reference, config, generated)
    pd.testing.assert_frame_equal(generated, ReplayBootstrap(json.loads(json.dumps(manifest)), reference))
    pd.testing.assert_frame_equal(reference, original)
    assert all(np.array_equal(left, right) for left, right in zip(state, following)), "Local bootstrap RNG must not consume global NumPy state"
    assert generated["datetime"].diff().iloc[1:].eq(pd.Timedelta(hours=1)).all(), "Bootstrap times must follow output cadence"

    for row in generated.itertuples(index=False):
        candidates = reference.iloc[1:]
        candidates = candidates[candidates["volume"] == row.volume]
        expected_bodies = np.log(candidates["close"] / candidates["open"])
        observed_body = math.log(row.close / row.open)
        assert np.isclose(expected_bodies, observed_body).any(), "Volume and body must originate in the same sampled source row"


def test_BootstrapFullBlockPreservesOrderedSourceGaps() -> None:
    """A full-length source block keeps exact geometry and previous-close gaps."""

    reference = _Reference()
    generated = Bootstrap(reference, BootstrapConfig(count=11, block_length=11, initial_price=float(reference["close"].iloc[0])))
    np.testing.assert_allclose(generated[["open", "high", "low", "close", "volume"]], reference.iloc[1:][["open", "high", "low", "close", "volume"]], rtol=2e-14)


def test_BootstrapRejectsReferenceGapAndOverlongBlock() -> None:
    """Make unsupported missing time observations and sample domains explicit."""

    reference = _Reference()

    with pytest.raises(ValueError, match="gaps"):
        Bootstrap(reference.drop(index=4).reset_index(drop=True))

    with pytest.raises(ValueError, match="block_length"):
        Bootstrap(reference, BootstrapConfig(block_length=len(reference)))

    with pytest.raises(ValueError, match="three"):
        Bootstrap(reference.iloc[:2])


@pytest.mark.parametrize("updates", [{"seed": True}, {"seed": -1}, {"count": 0}, {"count": 1.5},
                                    {"block_length": 0}, {"initial_price": 0}, {"initial_price": float("inf")},
                                    {"timeframe_seconds": 0}, {"start": "2024-01-01"}])
def test_BootstrapRejectsInvalidInputs(updates: dict) -> None:
    """Reject ambiguous and nonfinite sampling configuration inputs."""

    with pytest.raises(ValueError):
        BootstrapConfig(**updates)


def test_BootstrapManifestRejectsChangedSourceAndOutput() -> None:
    """Refuse replay when external empirical evidence or model identity changed."""

    reference = _Reference()
    config = BootstrapConfig(count=8)
    manifest = CreateBootstrapManifest(reference, config)
    changed = reference.copy()
    changed.loc[0, "volume"] += 1

    with pytest.raises(ValueError, match="reference"):
        ReplayBootstrap(manifest, changed)

    with pytest.raises(ValueError, match="fingerprint"):
        ReplayBootstrap({**manifest, "output_fingerprint": "bad"}, reference)

    with pytest.raises(ValueError, match="identity"):
        ReplayBootstrap({**manifest, "model": "legacy_v1"}, reference)

    with pytest.raises(ValueError, match="does not match"):
        CreateBootstrapManifest(reference, config, reference)


def test_MultiplicativeModelsRejectNonpositiveReferenceAndUnderflow() -> None:
    """Do not admit canonical signed prices into a multiplicative model domain."""

    reference = _Reference()
    reference[["open", "high", "low", "close"]] = 0

    with pytest.raises(ValueError, match="strictly positive"):
        Bootstrap(reference)

    with pytest.raises(ValueError, match="strictly positive"):
        Scripted(ScriptedConfig(count=2, drift=-1000))

    with pytest.raises(TypeError, match="BootstrapConfig"):
        Bootstrap(_Reference(), {})

    with pytest.raises(TypeError, match="ScriptedConfig"):
        Scripted({})


def test_ExtendedConfigRoundTripPreservesNanosecondStart() -> None:
    """Serialize imported timestamp precision without silent datetime rounding."""

    start = pd.Timestamp("2024-01-01T00:00:00.000000001Z")
    scripted = ScriptedConfig(count=3, start=start)
    bootstrap = BootstrapConfig(count=3, start=start)
    assert ScriptedConfig.FromDict(scripted.ToDict()) == scripted, "Scripted config roundtrip must preserve nanosecond start"
    assert BootstrapConfig.FromDict(bootstrap.ToDict()) == bootstrap, "Bootstrap config roundtrip must preserve nanosecond start"
    assert Scripted(scripted)["datetime"].iloc[0].value == start.value, "Output must retain exact explicit timestamp"

    for constructor in (BootstrapConfig.FromDict, ScriptedConfig.FromDict):
        with pytest.raises(ValueError, match="fields"):
            constructor({"hidden_state": 2})

    for constructor in (BootstrapConfig, ScriptedConfig):
        with pytest.raises(ValueError, match="start"):
            constructor(start="not-a-date")

        with pytest.raises(ValueError, match="million"):
            constructor(count=1_000_001)


def test_ScriptedStepShockRegimeSemanticsAndReplay() -> None:
    """Apply opening gaps once and retain explicit drift/volume regime changes."""

    config = ScriptedConfig(count=6, drift=0, wick_fraction=.02, steps=(
        ScriptStep(2, log_jump=math.log(2), drift=math.log(1.1), volume=0),
        ScriptStep(4, drift=-math.log(1.1), volume=30),
    ))
    data = Scripted(config)
    np.testing.assert_allclose(data["open"], [100, 100, 200, 220, 242, 220])
    np.testing.assert_allclose(data["close"], [100, 100, 220, 242, 220, 200])
    assert data["volume"].tolist() == [1000, 1000, 0, 0, 30, 30], "Step volume must persist until replaced"
    manifest = CreateScriptedManifest(config, data)
    pd.testing.assert_frame_equal(data, ReplayScripted(json.loads(json.dumps(manifest))))
    assert Fingerprint(data) != Fingerprint(Scripted(replace(config, drift=.01))), "Unforced paths must respond to earlier drift"


@pytest.mark.parametrize("updates", [{"steps": (ScriptStep(2), ScriptStep(1))},
                                    {"steps": (ScriptStep(1), ScriptStep(1))}, {"steps": (ScriptStep(5),)},
                                    {"steps": [ScriptStep(1)]}, {"wick_fraction": 1}, {"volume": -1},
                                    {"drift": float("nan")}, {"initial_price": 0}])
def test_ScriptedRejectsInvalidEvents(updates: dict) -> None:
    """Reject mutable, ambiguous and out-of-horizon stress-path inputs."""

    with pytest.raises(ValueError):
        ScriptedConfig(count=5, **updates)


@pytest.mark.parametrize("updates", [{"index": -1}, {"index": True}, {"index": 2, "log_jump": float("inf")},
                                    {"index": 2, "drift": float("nan")}, {"index": 2, "volume": -1}])
def test_ScriptedRejectsInvalidStepDomain(updates: dict) -> None:
    """Reject invalid event fields at construction rather than during execution."""

    with pytest.raises(ValueError):
        ScriptStep(**updates)


def test_ScriptedRejectsOverflowAndManifestTampering() -> None:
    """Fail finite-path and exact-identity requirements explicitly."""

    with pytest.raises(ValueError, match="overflow"):
        Scripted(ScriptedConfig(count=3, drift=1000))

    manifest = CreateScriptedManifest(ScriptedConfig(count=3))

    with pytest.raises(ValueError, match="fingerprint"):
        ReplayScripted({**manifest, "output_fingerprint": "bad"})

    with pytest.raises(ValueError, match="identity"):
        ReplayScripted({**manifest, "model_version": 2})

    with pytest.raises(ValueError, match="does not match"):
        CreateScriptedManifest(ScriptedConfig(count=3), _Reference())


def test_ExtendedReplayRejectsIncompleteAndNonJsonManifests() -> None:
    """Require complete serialization and integral version identity on replay."""

    reference = _Reference()

    def ReplayEmpirical(manifest: dict) -> pd.DataFrame:
        """Bind the explicit reference for the shared manifest rejection checks."""

        return ReplayBootstrap(manifest, reference)

    manifests = [(CreateScriptedManifest(ScriptedConfig(count=3)), ReplayScripted),
                 (CreateBootstrapManifest(reference, BootstrapConfig(count=3)),
                  ReplayEmpirical)]

    for manifest, replay in manifests:
        for field in ("manifest_version", "model_version"):
            with pytest.raises(ValueError, match="identity"):
                replay({**manifest, field: True})

        with pytest.raises(ValueError, match="fields"):
            replay({**manifest, "extra": float("nan")})

        with pytest.raises(ValueError, match="JSON"):
            replay({**manifest, "config": {**manifest["config"], "initial_price": float("nan")}})

        missing = dict(manifest["config"])
        del missing["initial_price"]

        with pytest.raises(ValueError, match="fields"):
            replay({**manifest, "config": missing})

    bootstrap_manifest = manifests[1][0]

    with pytest.raises(ValueError, match="identity"):
        ReplayBootstrap({**bootstrap_manifest, "source_semantics": "different sampling"}, reference)

    event_manifest = CreateScriptedManifest(ScriptedConfig(count=3, steps=(ScriptStep(1),)))
    del event_manifest["config"]["steps"][0]["log_jump"]

    with pytest.raises(ValueError, match="event schema"):
        ReplayScripted(event_manifest)


def test_ModelRegistryIsExplicitAndImmutable() -> None:
    """Do not admit archived runtimes or imply universal market suitability."""

    assert [model.model for model in ListModels()] == ["regime_v2", "bootstrap_v1", "scripted_v1"], "Only declared modern models may be selectable"
    assert all(model.status == "experimental" and model.limitations for model in ListModels()), "Insufficient evidence must remain experimental"
    assert all(json.loads(json.dumps(model.ToDict()))["model"] == model.model for model in ListModels()), "Registry entries must be independently serializable"

    with pytest.raises(ValueError, match="evidence only"):
        GetModel("legacy_v1")

    with pytest.raises(FrozenInstanceError):
        GetModel("regime_v2").status = "validated"
