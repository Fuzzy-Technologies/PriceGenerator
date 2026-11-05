"""Measure seeded CSV round-trips and chart rendering with repeatable inputs."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import tracemalloc

from benchmark_charts import Timed


def MeasureStages(rows, seed, source_root):
    """Yield wall time, traced peak and CSV fingerprint for one workload."""

    from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV
    from pricegenerator.rendering import api
    from pricegenerator.rendering.interactive import RenderInteractive
    from pricegenerator.rendering.static import RenderSVG

    if Path(api.__file__).resolve() != source_root / "pricegenerator/rendering/api.py":
        raise RuntimeError("Imported chart API does not match --source-root")

    frame = Generate(GenerationConfig(horizon=rows, seed=seed))
    spec = api.PrepareChart(frame, analysis=False)

    with TemporaryDirectory() as temporary:
        csv_path = Path(temporary) / "scenario.csv"
        stages = (
            ("csv_write", lambda: WriteCSV(frame, csv_path)),
            ("csv_read", lambda: ReadCSV(csv_path)),
            ("svg_render", lambda: RenderSVG(spec)),
            ("html_render", lambda: RenderInteractive(spec)),
        )

        for stage, operation in stages:
            value, seconds = Timed(operation)
            tracemalloc.start()

            try:
                measured = operation()
                peak = tracemalloc.get_traced_memory()[1]

            finally:
                tracemalloc.stop()

            if stage == "csv_read" and not (value.equals(frame) and measured.equals(frame)):
                raise RuntimeError("The CSV round-trip changed the source frame")

            if stage.endswith("_render") and value != measured:
                raise RuntimeError(f"Repeated {stage} calls produced different artifacts")

            yield {"rows": rows, "stage": stage, "elapsed_seconds": seconds, "traced_peak_bytes": peak}

        digest = sha256()

        with csv_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)

        yield {"rows": rows, "csv_sha256": digest.hexdigest(), "csv_bytes": csv_path.stat().st_size}


def Main():
    """Print JSON Lines from the selected source checkout and seed."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--sizes", type=int, nargs="+", default=(1_000, 10_000))
    parser.add_argument("--seed", type=int, default=0)
    arguments = parser.parse_args()
    source_root = arguments.source_root.resolve()
    sys.path.insert(0, str(source_root))

    for rows in arguments.sizes:
        for record in MeasureStages(rows, arguments.seed, source_root):
            print(json.dumps(record, allow_nan=False))


if __name__ == "__main__":
    Main()
