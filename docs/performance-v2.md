# Reproducible v2 performance and streaming

The [final committed-source evidence](performance-v2-final.md) is the current
reproducible measurement: a clean modern-only snapshot, a durable public source
commit, and exact matching full/chunked output across 100 through 1,000,000
rows. Earlier observations below remain archival records with their provenance
limits; use the final report when checking the release implementation.

The maintained benchmark runs actual `regime_v2` package code. Historical 1.x
measurements remain archival evidence; the removed runtime is not executed by
the current command. These diagnostics impose no wall-clock CI threshold.

```bash
python tools/benchmark.py --sizes 100 1000 10000 100000 1000000 --seed 0 --timeout 300 --output full.json
python tools/benchmark.py --sizes 100 1000 10000 100000 1000000 --seed 0 --mode chunked --chunk-size 10000 --timeout 300 --output chunked.json
python tools/benchmark.py --sizes 10000 100000 --seed 0 --repeat 3 --output repeated.json
python -m cProfile -o profile.pstats tools/benchmark.py --worker 10000
python -m pstats profile.pstats
```

Each case uses a new process and records full immutable configuration, seed,
model/RNG identity, requested and actual row counts, exact output fingerprint,
Python/platform/dependency versions, Git revision, and SHA-256 hashes of actual
package sources and the benchmark recipe. Import resolution is checked against
the checkout. The source inventory hashes files present in the working directory; it is not
an executed-module trace or a guarantee that every inventoried file belongs to
the release. A hash can identify a snapshot without making it reconstructible
from the recorded Git revision. Compare both committed provenance and source
hashes when assessing reproduction. Error records preserve worker failures and bounded stderr;
a failed case does not discard later observations. Timeouts terminate workers.

Both modes time generation, canonical validation, and exact row fingerprinting,
including allocation tracer overhead. Imports and configuration validation are
excluded. Full mode retains the complete DataFrame; chunked mode consumes each
chunk and updates the same hash incrementally. The hash recipe is identical to
`pricegenerator.scenario.Fingerprint`: a versioned prefix, UTC nanosecond
integers and `float.hex` JSON rows. Equal fingerprints verify exact timestamps
and every float64 value. `tracemalloc_peak_bytes` measures traced Python and
registered NumPy allocations during this scope. Process peak RSS is the
worker's lifetime peak, including imports; it is not an incremental memory
measurement and may be unavailable on some platforms.

# Stateful bounded-memory generation

```python
from pricegenerator import GenerationConfig
from pricegenerator.streaming import GenerateChunks, WriteCSVChunks

config = GenerationConfig(horizon=100000, seed=0)
WriteCSVChunks(
    GenerateChunks(config, chunk_size=10000),
    "scenario.csv",
    timeframe_seconds=config.timeframe_seconds,
    allow_gaps=False,
)
```

`GenerateChunks(config, *, chunk_size=10000)` returns an iterator of detached
canonical OHLCV DataFrames. Chunk size must be a positive Python integer;
booleans are rejected. Validation begins on first iteration. Full generation
and chunks share an absolute UTC nanosecond timestamp builder, so accepted
multi-century scenarios retain the same timestamps even when their total span
cannot fit a signed nanosecond duration. At most one
chunk's rows are requested from the model before yielding. One invocation owns
one private RNG and one stateful model iterator, preserving previous close,
regime, persistent volume noise, cached Gaussian RNG state and the timestamp
offset. Concatenating any partition yields exactly `Generate(config)`, including
a non-UTC configured start and a final partial chunk. The configuration's
supported horizon and timestamp bounds still apply. Chunks have local
RangeIndexes; concatenate with `ignore_index=True` for a complete frame.

`WriteCSVChunks(chunks, destination, *, timeframe_seconds=None,
allow_gaps=True)` accepts a path and an iterable of canonical DataFrames. It
validates every chunk and the timestamp boundary between nonempty chunks.
Timeframe and gap semantics match `ValidateOHLCV`; no interval is inferred.
Empty chunks and empty iterators emit a canonical header. The output contains
one header and exact round-trippable UTC/float64 values.

The writer streams into a temporary file in the destination directory, flushes
and fsyncs the file, then atomically replaces the destination. The parent
folder must exist. Producer, validation, serialization, flush, and replacement
failures leave an existing destination intact and remove the temporary file.
This is process-failure protection, not a promise of filesystem durability
across power loss. Memory is proportional to chunk size, rather than horizon;
CSV disk space remains proportional to the complete output.

# Archived profile-guided continuity optimization

A 10,000-row profile of the initial v2 boundary, with cProfile and tracemalloc
both enabled, observed 1.860 seconds in `Generate`, including 1.625 seconds in
`GenerateRows` and 0.196 seconds in `ValidateOHLCV`. The boundary spent 0.139
seconds in its own Python timestamp-spacing loop. Row fingerprinting took
0.604 seconds outside `Generate`. These profiler timings diagnose hotspots;
they are not directly comparable to unprofiled benchmark timings.

The maintained boundary computes interval differences with NumPy when the
monotonic timestamp span fits signed int64. A Python-integer fallback retains
correct subtraction for rare series spanning more than about 292 years. This
changes no random draws or model state and preserves exact gap semantics.

The [before](performance-v2-before-2026-10-16.json) and
[after](performance-v2-after-2026-10-16.json) reports each contain three isolated
observations per size, with identical complete configuration and output hashes.
Only `market_data.py` differs among package source hashes. Under the shared
Linux CPython 3.12.14 / pandas 2.2.3 / NumPy 2.2.6 environment:

| Rows | Before median | After median | Observed reduction |
| ---: | ---: | ---: | ---: |
| 10,000 | 1.07465 s | 1.01074 s | 5.95% |
| 100,000 | 11.54514 s | 10.20701 s | 11.59% |

These observations include tracemalloc and fingerprinting, are sensitive to
machine load, and support this narrow boundary optimization only. They do not
establish superiority over the different historical 1.x stochastic model or a
production throughput guarantee. These are archival, formative observations
from before the final configuration/manifest hardening. Their recorded Git
revision predates uncommitted source snapshots, and the exact measured
`config.py` and `scenario.py` versions were not retained as commits. The hashes
therefore identify those snapshots but do not permit an exact checkout-based
reproduction. The commands above run new diagnostics on the current source;
they do not reconstruct the earlier measured snapshot. No old runtime source
is retained to recreate it.

# Archived formative full-range memory evidence

The [full-frame](performance-v2-full-2026-10-16.json) and
[10,000-row chunk](performance-v2-chunked-2026-10-16.json) runs cover every default
size through one million rows. Both reports completed successfully, recorded
identical complete source hashes, and produced identical output fingerprints
at every size. Timings below include generation, validation, fingerprinting
and allocation instrumentation; one observation per mode/size is diagnostic,
not a throughput comparison. These reports also predate the later safe
timestamp-range correction and final hardening, and are observations of their
recorded snapshots rather than certified timings for the final release tree.

All four reports inventory unused, untracked historical `PriceGenerator.py`
and `UniLogger.py` files that the workspace had rehydrated during implementation.
The source inventory should not be read as an execution trace: the benchmark
loads and checks the actual modern `generation.py` module, and its measured
path uses `GenerationConfig`, `Generate`/`GenerateChunks`, the v2 model and
canonical validation. Those historical files were not imported for these
measurements and are absent from the maintained tracked runtime. Equal source
inventories across reports establish equal inventoried snapshots; they do not
establish identity with the final release's file inventory.

| Rows | Full time | Chunked time | Full traced peak | Chunked traced peak |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 0.028 s | 0.030 s | 90,123 B | 102,926 B |
| 1,000 | 0.125 s | 0.108 s | 391,555 B | 487,965 B |
| 10,000 | 1.045 s | 0.964 s | 2,993,661 B | 4,317,272 B |
| 100,000 | 10.739 s | 10.843 s | 29,809,469 B | 4,974,775 B |
| 1,000,000 | 102.641 s | 103.038 s | 298,457,213 B | 4,975,865 B |

At one million rows the traced peak was about 298.5 MB for a complete frame
versus 5.0 MB for chunked traversal. Worker lifetime peak RSS was 920,076,288 B
versus 92,217,344 B, respectively. Chunked traced memory stayed near 5 MB as the
horizon grew from 100,000 to 1,000,000 rows. Small datasets can use more traced
memory when chunked because of iterator and chunk bookkeeping. These figures
measure traversal and hashing; CSV serialization is covered by correctness and
atomic-failure tests, rather than a disk throughput benchmark.

Validation commands used for this implementation:

```bash
python -m pytest -q tests/test_market_data.py tests/test_ohlcv_io.py tests/test_streaming.py tests/test_benchmark.py
python -m pytest -q tests/test_generation_v2.py tests/test_scenario_v2.py
python -m ruff check --select E4,E7,E9,F,D --ignore D202,D203,D213 pricegenerator/market_data.py pricegenerator/io.py pricegenerator/streaming.py tools/benchmark.py tests/test_market_data.py tests/test_ohlcv_io.py tests/test_streaming.py tests/test_benchmark.py
```

The focused data/stream/benchmark suite passed 120 cases; the complementary
core generation/scenario suite passed 59. Tests cover exact chunk partitions,
subsecond and offset start timestamps, lazy consumption, invalid chunk sizes,
producer failures, cross-chunk ordering/grid failures, serialization/flush/
replace failures and temporary-file cleanup. No external service is used.
