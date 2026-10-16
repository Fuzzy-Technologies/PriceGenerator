"""Verify exact manifests, environmental scope, tamper failures and wire hashes."""

from copy import deepcopy
from dataclasses import replace
import json

import pandas as pd
import pytest

from pricegenerator import CreateManifest, Fingerprint, Generate, GenerationConfig, Replay


def test_ManifestContainsCompleteSerializableIdentity():
    """Seed zero, complete config, versioned engine and environment survive JSON."""

    config = GenerationConfig(seed=0, horizon=12)
    original = Generate(config)
    metadata = {"profile": {"source": "fixture", "sha256": "abc"}}
    manifest = CreateManifest(config, original, metadata=metadata)
    metadata["profile"]["source"] = "changed"
    serialized = json.loads(json.dumps(manifest, allow_nan=False))
    assert serialized["seed"] == 0, "Seed zero was treated as missing"
    assert serialized["configuration"] == config.ToDict(), "Manifest lost deterministic input fields"
    assert serialized["rng"] == "python.random.Random/MT19937", "Private RNG identity is ambiguous"
    assert {"python", "implementation", "platform", "pandas", "numpy"} == set(serialized["environment"]), "Environment provenance incomplete"
    assert serialized["metadata"]["profile"]["source"] == "fixture", "Caller mutation changed the manifest"
    pd.testing.assert_frame_equal(Replay(serialized), original)
    assert CreateManifest(config)["fingerprint"] == manifest["fingerprint"], "Manifest generation differs from supplied canonical data"


@pytest.mark.parametrize("field,value", [
    ("manifest_version", 2), ("model", "legacy_v1"), ("rng", "global-random"),
    ("library_version", "0.0"), ("seed", 1), ("fingerprint", "0" * 64),
    ("environment", {}),
])
def test_TamperedIdentityOrOutputFails(field, value):
    """Reject incompatible provenance and changed scenario output before returning data."""

    manifest = CreateManifest(GenerationConfig(horizon=3))
    manifest[field] = value

    with pytest.raises(ValueError):
        Replay(manifest)


def test_ManifestRejectsIncompleteUnknownAndChangedInputs():
    """Defaults cannot silently fill an archived manifest's missing deterministic state."""

    manifest = CreateManifest(GenerationConfig(horizon=3))
    incomplete = deepcopy(manifest)
    del incomplete["configuration"]["wick_scale"]

    with pytest.raises(ValueError, match="complete"):
        Replay(incomplete)

    unknown = dict(manifest, extra=1)

    with pytest.raises(ValueError, match="fields"):
        Replay(unknown)

    changed = deepcopy(manifest)
    changed["configuration"]["drift"] = 0.1

    with pytest.raises(ValueError, match="fingerprint"):
        Replay(changed)


def test_PortableReplayStillRequiresExactOutput(monkeypatch):
    """An explicit environment override verifies the hash instead of weakening replay."""

    manifest = CreateManifest(GenerationConfig(horizon=3))
    from pricegenerator import scenario

    runtime = dict(manifest["environment"], platform="other")
    monkeypatch.setattr(scenario, "Environment", lambda: runtime)
    assert Fingerprint(Replay(manifest, strict_environment=False)) == manifest["fingerprint"], "Portable verification changed output"
    manifest["fingerprint"] = "invalid"

    with pytest.raises(ValueError, match="fingerprint"):
        Replay(manifest, strict_environment=False)


def test_FingerprintStableAcrossIndexAndSensitiveToEveryField():
    """Wire identity ignores pandas index but preserves timestamps and binary64 data."""

    original = Generate(GenerationConfig(horizon=3))
    indexed = original.copy()
    indexed.index = [10, 11, 12]
    assert Fingerprint(indexed) == Fingerprint(original), "Incidental pandas index entered wire identity"

    for field in original:
        changed = original.copy()

        if field == "datetime":
            changed[field] += pd.Timedelta(nanoseconds=1)

        elif field == "low":
            changed.loc[0, field] -= 0.01

        elif field == "high":
            changed.loc[0, field] += 0.01

        elif field in ("open", "close"):
            changed.loc[0, field] = (original.low.iloc[0] + original.high.iloc[0]) / 2

        else:
            changed.loc[0, field] += 0.01

        assert Fingerprint(changed) != Fingerprint(original), f"Fingerprint ignored canonical field {field}"


def test_InvalidManifestConstructionFailsClearly():
    """Reject wrong input objects and nonstandard metadata values."""

    with pytest.raises(TypeError, match="GenerationConfig"):
        CreateManifest({})

    with pytest.raises(ValueError):
        CreateManifest(GenerationConfig(horizon=1), metadata={"nan": float("nan")})


@pytest.mark.parametrize("field,value", [("metadata", {"nan": float("nan")}), ("metadata", []), ("environment", []), ("environment", {}), ("manifest_version", True)])
def test_ManifestSchemaRemainsStrictDuringPortableReplay(field, value):
    """Environment portability cannot bypass provenance or standard JSON validation."""

    manifest = CreateManifest(GenerationConfig(horizon=1))
    manifest[field] = value

    with pytest.raises(ValueError):
        Replay(manifest, strict_environment=False)


def test_IdentityDiffersForIdenticalFlatOutputs():
    """Different deterministic inputs retain distinct identity when output is flat."""

    config = GenerationConfig(horizon=8, volatility=0, volume_sigma=0)
    manifests = [CreateManifest(settings) for settings in (config, replace(config, seed=1), replace(config, shock_probability=1))]
    assert len({manifest["fingerprint"] for manifest in manifests}) == 1, "Flat fixture outputs unexpectedly differ"
    assert len({manifest["scenario_fingerprint"] for manifest in manifests}) == 3, "Scenario identity collapsed distinct seeds/configuration"

    changed = deepcopy(manifests[0])
    changed["seed"] = changed["configuration"]["seed"] = 1

    with pytest.raises(ValueError, match="identity fingerprint"):
        Replay(changed)

    changed = deepcopy(manifests[0])
    changed["configuration"]["shock_probability"] = 1

    with pytest.raises(ValueError, match="identity fingerprint"):
        Replay(changed)


def test_IdentityIncludesProfileReferenceAndSurvivesJSONOrder():
    """Record fitted profile identity without treating free-form notes as RNG inputs."""

    config = GenerationConfig(horizon=2)
    first = CreateManifest(config, metadata={"profile_reference": "a" * 64, "note": "original"})
    second = CreateManifest(config, metadata={"profile_reference": "b" * 64, "note": "original"})
    notes = CreateManifest(config, metadata={"profile_reference": "a" * 64, "note": "edited"})
    assert first["fingerprint"] == second["fingerprint"], "Profile provenance changed generated data"
    assert first["scenario_fingerprint"] != second["scenario_fingerprint"], "Fitted profile identity was excluded"
    assert first["scenario_fingerprint"] == notes["scenario_fingerprint"], "Free-form notes entered deterministic input identity"
    reordered = json.loads(json.dumps(first, sort_keys=True))
    pd.testing.assert_frame_equal(Replay(reordered), Generate(config))
    first["metadata"]["profile_reference"] = "b" * 64

    with pytest.raises(ValueError, match="identity fingerprint"):
        Replay(first)


@pytest.mark.parametrize("profile_reference", [None, "invalid", 1, float("nan")])
def test_IdentityRejectsInvalidProfileReferences(profile_reference):
    """Require a concrete profile digest when profile provenance is supplied."""

    with pytest.raises(ValueError):
        CreateManifest(GenerationConfig(horizon=1), metadata={"profile_reference": profile_reference})


def test_IdentityProtectsRecordedEnvironmentDuringPortableVerification():
    """Allow a new execution environment without allowing recorded identity edits."""

    manifest = CreateManifest(GenerationConfig(horizon=2))
    manifest["environment"]["platform"] = "altered"

    with pytest.raises(ValueError, match="identity fingerprint"):
        Replay(manifest, strict_environment=False)

    manifest = CreateManifest(GenerationConfig(horizon=2))
    manifest["scenario_fingerprint"] = "0" * 64

    with pytest.raises(ValueError, match="identity fingerprint"):
        Replay(manifest)
