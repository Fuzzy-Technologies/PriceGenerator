"""Create and verify a portable synthetic PriceGenerator experiment."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pricegenerator import CreateManifest, Generate, GenerationConfig, Replay, WriteCSV
from pricegenerator.config import COUNT_MODEL_ID
from pricegenerator.evaluation import Compare
from pricegenerator.monte_carlo import ChartEnsemble, CreateEnsembleManifest, ReplayEnsemble, RunEnsemble


CHECKSUM_FILE = "SHA256SUMS"
BUNDLE_FILES = (
    "comparison.json",
    "ensemble-manifest.json",
    "ensemble.json",
    "quantiles.html",
    "reference-manifest.json",
    "reference.csv",
    "scenario-manifest.json",
    "scenario.csv",
)


def _JSONBytes(payload: dict[str, Any]) -> bytes:
    """Serialize evidence with stable UTF-8 bytes and standard JSON numbers."""

    return (json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _WriteFixture(directory: Path, stem: str, config: GenerationConfig) -> pd.DataFrame:
    """Write one synthetic fixture and check byte-identical replay from its saved manifest."""

    candles = Generate(config)
    csv_path = directory / f"{stem}.csv"
    manifest_path = directory / f"{stem}-manifest.json"
    csv_options = {"timeframe_seconds": config.timeframe_seconds, "allow_gaps": False,
                   "volume_as_count": config.model == COUNT_MODEL_ID}
    WriteCSV(candles, csv_path, **csv_options)
    manifest_path.write_bytes(_JSONBytes(CreateManifest(config, candles, metadata={"origin": "synthetic", "fixture": stem})))

    replay = StringIO(newline="")
    WriteCSV(Replay(json.loads(manifest_path.read_bytes())), replay, **csv_options)

    if replay.getvalue().encode("utf-8") != csv_path.read_bytes():
        raise ValueError(f"Replay changed the canonical bytes of {csv_path.name}")

    return candles


def _Checksums(directory: Path) -> bytes:
    """Hash exactly the declared payload files in canonical order."""

    lines = []

    for name in BUNDLE_FILES:
        path = directory / name

        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing regular bundle file {name}")

        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n")

    return "".join(lines).encode("ascii")


def CreateBundle(directory: Path) -> None:
    """Generate into a new directory and mark completion after replay checks."""

    directory.mkdir()
    config = GenerationConfig(seed=42, horizon=120, start=datetime(2025, 1, 6, tzinfo=timezone.utc))
    scenario = _WriteFixture(directory, "scenario", config)
    reference = _WriteFixture(directory, "reference", replace(config, seed=43, volatility=0.005))

    report = RunEnsemble(config, path_count=32, workers=2)
    report_path = directory / "ensemble.json"
    manifest_path = directory / "ensemble-manifest.json"
    report_path.write_bytes(_JSONBytes(report.ToDict()))
    manifest_path.write_bytes(_JSONBytes(CreateEnsembleManifest(report)))
    replayed = ReplayEnsemble(json.loads(manifest_path.read_bytes()), workers=1)

    if _JSONBytes(replayed.ToDict()) != report_path.read_bytes():
        raise ValueError("One-worker replay changed the two-worker ensemble report")

    ChartEnsemble(report, directory / "quantiles.html")
    comparison = {
        "inputs": {
            "reference": {"origin": "synthetic", "csv": "reference.csv", "manifest": "reference-manifest.json"},
            "synthetic": {"origin": "synthetic", "csv": "scenario.csv", "manifest": "scenario-manifest.json"},
        },
        "comparison": Compare(reference, scenario).ToDict(),
    }
    (directory / "comparison.json").write_bytes(_JSONBytes(comparison))

    checksums = _Checksums(directory)

    with (directory / CHECKSUM_FILE).open("xb") as stream:
        stream.write(checksums)


def VerifyBundle(directory: Path) -> None:
    """Require a complete checksum list and verify the saved payload bytes."""

    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Bundle path must be a directory")

    checksum_path = directory / CHECKSUM_FILE

    if checksum_path.is_symlink() or not checksum_path.is_file():
        raise ValueError(f"Incomplete bundle: {CHECKSUM_FILE} is missing or not a regular file")

    if checksum_path.read_bytes() != _Checksums(directory):
        raise ValueError(f"Bundle files do not match {CHECKSUM_FILE}")


def Main() -> None:
    """Run a generation or integrity check from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()

    try:
        if arguments.action == "create":
            CreateBundle(arguments.directory)

        VerifyBundle(arguments.directory)

    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")

    print(f"Verified experiment bundle at {arguments.directory}")


if __name__ == "__main__":
    Main()
