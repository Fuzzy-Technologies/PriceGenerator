# PriceGenerator 2.1 performance baseline

This first measurement for [Task #134](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/134)
uses the runtime and benchmark sources from `develop` at `cfd8db6da83235afd04b7bda8ed71e0eb126c2fc`.
The source declared version `2.0.0`. The host ran Linux x86-64 on an
Intel Xeon Platinum 8573C with an eight-CPU container quota. The Python
environment used CPython 3.12.14, pandas 2.2.3, NumPy 2.2.6, python-dateutil
2.9.0.post0, resvg-py 0.5.0 and Pillow 12.0.0. Each measurement is a single
observation on a shared host. Repeated results on the same runtime provide
evidence about output identity. Timing and memory can vary with host and load.

## Full generation and chunk traversal

The generation measurements use the [existing benchmark](benchmarks.md).
Both modes include generation, canonical validation, exact row fingerprinting
and tracemalloc overhead. RSS is the worker lifetime peak including imports.
Chunk traversal uses 10,000-row chunks.

| Rows | Mode | Wall time (s) | Traced peak (bytes) | Peak RSS (bytes) |
| ---: | --- | ---: | ---: | ---: |
| 10,000 | Full frame | 6.768 | 2,993,558 | 75,530,240 |
| 10,000 | Chunk traversal | 2.716 | 4,331,836 | 79,196,160 |
| 100,000 | Full frame | 33.993 | 29,809,469 | 146,259,968 |
| 100,000 | Chunk traversal | 37.173 | 4,989,697 | 85,680,128 |

At 100,000 rows, chunk traversal reduced the traced peak by 83% in this run.
The full and chunked row fingerprints match exactly at both sizes and agree
with the matching workloads in the
[committed v2 evidence](performance-v2-final.md).

| Rows | Row fingerprint (SHA-256) |
| ---: | --- |
| 10,000 | `2c7cd9e645bd50888f138d46d5305ee79f376100b4ed66c0dfa5c11329f1910f` |
| 100,000 | `43099b4606b77e0084cb3d456f03bbb52c5a9354c8709f023dace7ac7d682b54` |

```bash
evidence_dir=$(mktemp -d)
python tools/benchmark.py --sizes 10000 100000 --seed 0 --output "$evidence_dir/full.json"
python tools/benchmark.py --sizes 10000 100000 --seed 0 --mode chunked --chunk-size 10000 --output "$evidence_dir/chunked.json"
```

## CSV and chart artifact stages

Generate a `regime_v2` frame at seed 0 and prepare a chart with automatic
statistics disabled before measurement. CSV write and read include canonical
validation and buffered local file I/O. SVG and offline HTML rendering use the
prepared chart spec and return strings in memory. Report wall time from a
first call without tracing. Report the peak traced Python allocations from a
second call. The traced peak excludes the prebuilt frame/spec and native
allocations. The HTML stage measures artifact creation. Canvas rendering has
its own [runtime benchmark](chart-performance.md).

| Rows | Stage | Wall time (s) | Traced peak (bytes) |
| ---: | --- | ---: | ---: |
| 1,000 | Write CSV | 0.017 | 344,600 |
| 1,000 | Read CSV | 0.017 | 615,560 |
| 1,000 | Render SVG | 0.038 | 1,501,341 |
| 1,000 | Render offline HTML | 0.016 | 2,158,057 |
| 10,000 | Write CSV | 0.137 | 1,928,120 |
| 10,000 | Read CSV | 0.144 | 5,866,473 |
| 10,000 | Render SVG | 0.198 | 12,816,051 |
| 10,000 | Render offline HTML | 0.084 | 6,720,493 |

Both CSV reads reproduced the source frame exactly and both render calls
returned identical strings per format. CSV SHA-256 values were:

| Rows | CSV bytes | SHA-256 |
| ---: | ---: | --- |
| 1,000 | 123,329 | `7430949a23e685581027f3cdd6f77616a38faafdebfe910d441cd298ab9aa4bf` |
| 10,000 | 1,230,141 | `ac006f4302e95c8b8ff01b6ec83cfb56958225144665953a9f57077b83373550` |

## Reproduce CSV and chart artifact measurements

From the measured checkout with the locked development environment installed,
run the following POSIX shell command. The temporary directory contains
only the CSV fixture and is removed automatically.

```bash
python - <<'PY'
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import json
import tracemalloc

from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV
from pricegenerator.rendering.api import PrepareChart
from pricegenerator.rendering.interactive import RenderInteractive
from pricegenerator.rendering.static import RenderSVG

for rows in (1_000, 10_000):
    frame = Generate(GenerationConfig(horizon=rows, seed=0))
    with TemporaryDirectory() as temporary:
        csv_path = Path(temporary) / "scenario.csv"
        spec = PrepareChart(frame, analysis=False)
        stages = (
            ("csv_write", lambda: WriteCSV(frame, csv_path)),
            ("csv_read", lambda: ReadCSV(csv_path)),
            ("svg_render", lambda: RenderSVG(spec)),
            ("html_render", lambda: RenderInteractive(spec)),
        )
        for stage, operation in stages:
            start = perf_counter()
            value = operation()
            seconds = perf_counter() - start
            tracemalloc.start()
            try:
                measured = operation()
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            if stage == "csv_read":
                assert value.equals(frame) and measured.equals(frame)
            if stage.endswith("_render"):
                assert value == measured
            print(json.dumps(dict(rows=rows, stage=stage, elapsed_seconds=seconds, traced_peak_bytes=peak)))
        with csv_path.open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()
        print(json.dumps(dict(rows=rows, csv_sha256=digest, csv_bytes=csv_path.stat().st_size)))
PY
```
