"""Serialize deterministic input provenance and verify exact canonical replay."""

import hashlib
from importlib.metadata import version
import json
import platform
import re
from typing import Any, Mapping

import pandas as pd

from pricegenerator._version import __version__
from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.models import MODEL_ID, RNG_ID


MANIFEST_VERSION = 1


def Environment() -> dict[str, str]:
    """Identify the implementation environment in which exact replay was recorded."""

    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pandas": version("pandas"),
        "numpy": version("numpy"),
    }


def Fingerprint(data: pd.DataFrame) -> str:
    """Hash canonical UTC nanoseconds and exact binary64 OHLCV values.

    The versioned wire representation uses one compact JSON array per row and
    a trailing newline. Integers encode UTC nanoseconds; float.hex avoids locale,
    decimal-rounding, and pandas serialization dependencies.
    """

    from pricegenerator.market_data import ValidateOHLCV

    canonical = ValidateOHLCV(data)
    digest = hashlib.sha256(b"pricegenerator-ohlcv-fingerprint-v1\n")

    for row in canonical.itertuples(index=False, name=None):
        serialized = [int(row[0].value), *(float(value).hex() for value in row[1:])]
        digest.update(json.dumps(serialized, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        digest.update(b"\n")

    return digest.hexdigest()


def _ScenarioFingerprint(manifest: Mapping[str, Any]) -> str:
    """Hash full deterministic inputs separately from potentially identical output."""

    metadata = manifest["metadata"]
    profile_reference = metadata.get("profile_reference")

    if "profile_reference" in metadata and (not isinstance(profile_reference, str) or re.fullmatch(r"[0-9a-f]{64}", profile_reference) is None):
        raise ValueError("manifest profile_reference must be a SHA-256 digest")

    identity = {name: manifest[name] for name in (
        "manifest_version", "model", "rng", "library_version", "seed", "configuration", "environment",
    )}
    identity["profile_reference"] = profile_reference
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)

    return hashlib.sha256(b"pricegenerator-scenario-fingerprint-v1\n" + serialized.encode("ascii")).hexdigest()


def CreateManifest(config: GenerationConfig, data: pd.DataFrame | None = None, *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Record complete deterministic identity and a separate canonical output hash."""

    if not isinstance(config, GenerationConfig):
        raise TypeError("CreateManifest requires a GenerationConfig")

    if metadata is not None and not isinstance(metadata, Mapping):
        raise ValueError("manifest metadata must be a JSON object")

    provenance = json.loads(json.dumps(dict(metadata or {}), allow_nan=False))
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "model": MODEL_ID,
        "rng": RNG_ID,
        "library_version": __version__,
        "seed": config.seed,
        "configuration": config.ToDict(),
        "environment": Environment(),
        "metadata": provenance,
    }
    manifest["scenario_fingerprint"] = _ScenarioFingerprint(manifest)
    generated = Generate(config) if data is None else data
    manifest["fingerprint"] = Fingerprint(generated)

    return manifest


def Replay(manifest: Mapping[str, Any], *, strict_environment: bool = True) -> pd.DataFrame:
    """Reconstruct a recorded scenario and reject changed identity or output.

    Environment equality is required by default. Disabling that precondition is
    explicit portability verification: the output fingerprint must still match.
    """

    required = {"manifest_version", "model", "rng", "library_version", "seed", "configuration", "environment", "fingerprint", "scenario_fingerprint", "metadata"}

    if not isinstance(manifest, Mapping) or set(manifest) != required:
        raise ValueError("manifest fields are incomplete or unsupported")

    if type(manifest["manifest_version"]) is not int or type(manifest["seed"]) is not int:
        raise ValueError("manifest version and seed must be integers")

    for name, expected in (("manifest_version", MANIFEST_VERSION), ("model", MODEL_ID), ("rng", RNG_ID), ("library_version", __version__)):
        if manifest[name] != expected:
            raise ValueError(f"manifest {name} is incompatible with this runtime")

    if not isinstance(manifest["metadata"], Mapping):
        raise ValueError("manifest metadata must be a JSON object")

    try:
        json.dumps(manifest, allow_nan=False)

    except (TypeError, ValueError) as error:
        raise ValueError("manifest must contain standard JSON values") from error

    environment = manifest["environment"]

    if not isinstance(environment, Mapping) or set(environment) != set(Environment()) or not all(isinstance(value, str) for value in environment.values()):
        raise ValueError("manifest environment must contain the complete string-valued runtime identity")

    configuration = manifest["configuration"]

    if not isinstance(configuration, Mapping) or set(configuration) != set(GenerationConfig().ToDict()):
        raise ValueError("manifest must contain the complete generation configuration")

    config = GenerationConfig.FromDict(configuration)

    if manifest["seed"] != config.seed:
        raise ValueError("manifest seed does not match its configuration")

    if manifest["scenario_fingerprint"] != _ScenarioFingerprint(manifest):
        raise ValueError("scenario identity fingerprint does not match the manifest")

    if strict_environment and manifest["environment"] != Environment():
        raise ValueError("manifest environment differs; use strict_environment=False to verify portable replay")

    data = Generate(config)

    if Fingerprint(data) != manifest["fingerprint"]:
        raise ValueError("replayed data fingerprint does not match the manifest")

    return data
