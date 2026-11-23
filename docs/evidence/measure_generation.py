"""Time in-memory candle generation and a local CSV write with the installed package."""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
from time import perf_counter

from pricegenerator import Generate, GenerationConfig, WriteCSV


def Measure(rows):
    """Measure two successive operations, then count and fingerprint the written rows."""

    config = GenerationConfig(horizon=rows, seed=42, timeframe_seconds=60)

    with TemporaryDirectory(dir=Path.cwd()) as directory:
        destination = Path(directory) / "candles.csv"
        warmup = Generate(GenerationConfig(horizon=16, seed=42, timeframe_seconds=60))
        WriteCSV(warmup, Path(directory) / "warmup.csv", volume_as_count=True)
        started = perf_counter()
        candles = Generate(config)
        generated = perf_counter()
        WriteCSV(candles, destination, volume_as_count=True)
        written = perf_counter()
        digest = hashlib.sha256()
        lines = 0

        with destination.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
                lines += block.count(b"\n")

        if len(candles) != rows or lines != rows + 1:
            raise RuntimeError("The generated or exported row count differs from the requested size")

        return {
            "configuration": config.ToDict(),
            "generate_seconds": generated - started,
            "write_csv_seconds": written - generated,
            "generate_and_write_seconds": written - started,
            "csv_bytes": destination.stat().st_size,
            "csv_sha256": digest.hexdigest(),
            "pricegenerator": version("pricegenerator"),
            "python": platform.python_version(),
            "pandas": version("pandas"),
            "numpy": version("numpy"),
            "platform": f"{platform.system()} {platform.machine()}",
        }


def Main():
    """Print one observation as JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=int)
    args = parser.parse_args()
    print(json.dumps(Measure(args.rows), allow_nan=False))


if __name__ == "__main__":
    Main()
