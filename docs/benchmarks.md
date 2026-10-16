# Reproducible generation benchmarks

`tools/benchmark.py` measures the actual modern `regime_v2` implementation with
its installed dependencies. It supports complete DataFrames and bounded-memory
chunk traversal. Chart rendering and indicators are outside this measurement.
There is no speed or memory threshold in the PR gate.

Run from the checkout using its supported modern dependency environment:

```bash
python tools/benchmark.py --sizes 100 1000 10000 --seed 0 --repeat 3 --output benchmark.json
python tools/benchmark.py --seed 0 --timeout 300 --output benchmark-full.json
python tools/benchmark.py --seed 0 --mode chunked --chunk-size 10000 --timeout 300 --output benchmark-chunked.json
```

The default sizes are 100, 1,000, 10,000, 100,000 and 1,000,000 rows. Each
observation runs in a fresh subprocess with a default 300-second timeout.
`--sizes` accepts integers from 1 through 1,000,000. `--repeat` defaults to 1;
`--mode` defaults to `full`; chunk size defaults to 10,000. Repetition count and
chunk size must be positive integers, and timeout must be finite and positive.
Seed zero is valid. Omit `--output` to emit JSON on stdout; the output directory
must already exist. A failed or timed-out case remains in the report and later
cases are still attempted.

Exit code 0 means all cases completed and their evidence passed the benchmark's
checks. Exit code 1 means a worker or output write failed; JSON describes the
failure. An output-write failure also returns the report on stdout. Invalid
CLI arguments use exit code 2. None of these codes depends on throughput.

## Deterministic recipe and provenance

Each case records the complete `GenerationConfig`, including model, private
RNG identity, seed, horizon, aware UTC start, timeframe, price bounds, return,
regime, shock, wick and persistent volume settings. The current default starts
at `2000-01-01T00:00:00+00:00` with a one-hour interval. No wall-clock default,
host timezone change or process-global RNG seeding is used. Full generation and
chunk traversal share the same stateful row model and timestamp construction.
Their exact output fingerprints must match for equivalent configurations.

The report records the declared package version, Git revision, Python/platform
and installed dependency versions, and SHA-256 inventories of package Python
files, benchmark code and present packaging metadata. The generator import is
checked against the checkout path to prevent silently measuring an unrelated
installed package. Unavailable Git or dependency metadata is recorded as null;
missing runtime dependencies cause an explicit failed case.

The source inventory describes files present in the working directory. It is
not an executed-module trace. Untracked files can appear in it, and a hash of an
uncommitted snapshot does not make that snapshot reconstructible from the
recorded Git revision. Preserve the relevant committed sources when preparing
new reproducible evidence. The provenance limits of formative observations are
explicitly documented in [v2 performance evidence](performance-v2.md).

## Evidence format and measurement scope

Current reports use `schema_version: 2` and benchmark recipe
`regime-v2-generation-and-fingerprint-v1`.

| Field | Meaning |
| --- | --- |
| `source` | Package version, Git revision and source inventories |
| `environment` | Python, platform, CPU count and dependency versions |
| `measurement` | Timing/allocation/RSS scopes, hash recipe and timeout |
| `cases` | Ordered successful and failed observations, including repetitions |
| `status` | Aggregate `ok` or `error` |
| `output_error` | Present when the requested report cannot be written |

Each case records its configuration, model, RNG, seed, mode, chunk size where
applicable, requested/generated row counts, output hash, elapsed seconds,
traced peak bytes, lifetime process peak RSS bytes and a nullable error.
Timing includes `Generate` or complete `GenerateChunks` traversal, canonical
validation and exact row fingerprinting, with tracemalloc overhead. It excludes
imports, configuration validation, subprocess startup, source/environment
inspection and report writing. Full mode retains the complete frame; chunked
mode hashes chunks incrementally. CSV disk throughput is not measured.

The output hash uses the package's versioned OHLCV fingerprint recipe: a fixed
prefix followed by compact JSON rows and LF, containing UTC nanosecond integers
and exact `float.hex` values in canonical column order. The fingerprint checks
exact output identity; it does not establish statistical realism.

Tracemalloc does not capture every native allocation. Process peak RSS includes
imports and runtime startup and is not incremental generation memory; it is
null where the resource counter is unavailable. Fresh workers prevent previous
cases from inflating subsequent RSS measurements. Timing and memory observations
do not replay bit for bit. Use repeated measurements with matching scope,
configuration, sources and environment before making performance comparisons.
See [final committed-source evidence](performance-v2-final.md) for the clean
100-to-1,000,000-row measurements, durable public source mapping and exact
full/chunked hash checks. See [v2 performance and streaming](performance-v2.md)
for commands, the measured
continuity optimization, full/chunked observations and their limitations.

## Archived 1.x baseline

The [2026-10-15 historical report](benchmarks/legacy-baseline-2026-10-15.json)
retains observations and recorded commands from the removed 1.x runtime. It is
archival evidence, not output from the current benchmark command and not a
supported recipe in the v2 runtime. Its legacy model, fingerprint format,
dependencies and timing scope differ from the current v2 benchmark.

That historical environment used CPython 3.11.17, pandas 1.5.3, NumPy 1.24.4 and
pandas-ta 0.3.14b0 on Linux x86-64. Its one-million-row observation took 38.156
seconds, with a 434,467,955-byte traced peak and 1,185,656,832-byte lifetime RSS
peak. These single shared-host observations are retained for historical
characterization. They do not establish a speed comparison with `regime_v2`,
and the current command does not expose a legacy model or compatibility mode.
