# Reproducible generation benchmarks

The diagnostic command measures the **actual legacy PriceGenerator package**.
It does not replace dependencies with stubs, render charts, calculate indicators,
or enforce speed or memory thresholds in the PR gate.

Run from a checkout using its supported legacy dependency environment:

```bash
python tools/benchmark.py --sizes 100 1000 10000 --seed 0 --repeat 3 --output benchmark.json
```

The default size sequence is **100, 1,000, 10,000, 100,000 and 1,000,000 rows**.
Each observation uses a fresh subprocess with a 120-second timeout. For a full
diagnostic run on a suitable machine:

```bash
python tools/benchmark.py --seed 0 --timeout 300 --output benchmark-full.json
```

Start with small sizes when investigating an unfamiliar environment. A timed-out
case is recorded as a failure and the next case is attempted. `--sizes` accepts
any integer of at least 5; smaller requests are rejected because the legacy
generator silently expands them. `--repeat` defaults to 1. Omit `--output` to
emit one JSON document to stdout. The output directory must already exist.

Exit code 0 means every requested observation completed and its output passed
the benchmark's count, schema and fingerprint checks. Exit code 1 means a worker
or output write failed; JSON describes the failure. An output-write failure
returns the report on stdout. Exit code 2 means invalid CLI arguments. No exit
code depends on achieving a speed or memory target. These checks do not replace
the structural and statistical validation planned in ADR-0005.

## Deterministic recipe

Every case records its complete generation configuration, including its row
count, precision, bounds, probabilities, candle body/tail sizes, volume limit,
initial close, trend settings, schema, fixed start time and one-minute interval.
The recipe uses `legacy_v1` (ADR-0004) and seed 0 unless explicitly changed.
Python's `random` is seeded **before constructing** `PriceGenerator`; the
historical constructor consumes random values even though the benchmark then
replaces its random defaults with explicit values. Changing that order changes
the generated scenario.

Workers force `TZ=UTC` before importing the package. The fixed first timestamp
is `2020-01-01T00:00:00+00:00`; the benchmark checks that output timestamps carry
a zero UTC offset. On platforms without `time.tzset`, the host must already use
UTC with no daylight saving. Otherwise the case fails with an explicit error.
This contains the historical `tzlocal()` behavior without changing production
generation semantics.

The wrapper saves and restores the process-global RNG, timezone setting,
stderr redirection and temporary logging suppression, including on failure.
The command's process isolation is important: the internal legacy wrapper is
not a thread-safe library API.

Scenario identity consists of the recorded model, RNG recipe, seed,
configuration, declared source version, source-file SHA-256 hashes and runtime
versions. The source version is read from `pricegenerator/_version.py`, falling
back to the historical `setup.py` literal, without executing packaging code;
the Git commit and hashes identify the exact checkout rather than an unrelated
installed package with the same distribution name. The benchmark recipe itself
is also hashed, along with package Python sources and present `setup.py` or
`pyproject.toml` metadata. `git_commit` is null when Git metadata is unavailable. Dependency
versions are null when their distribution metadata is unavailable; missing
runtime dependencies cause the real worker import to fail explicitly.

## Evidence format

The JSON `schema_version` is 1. Its top-level fields are:

| Field | Meaning |
| --- | --- |
| `benchmark` | Versioned measurement recipe, `legacy-generation-v1` |
| `created_at` | UTC observation time; not part of deterministic scenario identity |
| `source` | Declared source version, Git commit and source/recipe SHA-256 hashes |
| `environment` | Python, platform, architecture, CPU count and dependency versions |
| `measurement` | Explicit timing/memory scope, fingerprint format and per-case timeout |
| `cases` | Ordered observations, retaining successful and failed cases |
| `status` | `ok` only if all observations and evidence writing succeed |
| `output_error` | Present only if the requested JSON file could not be written |

Each case retains `model`, `rng`, `seed`, `configuration`, `requested_rows`,
`repetition` and its `status`. Its measured fields are:

| Field | Meaning |
| --- | --- |
| `generated_rows` | Actual DataFrame length; null if generation did not return |
| `row_sha256` | Ordered canonical row fingerprint; null on invalid/incomplete output |
| `elapsed_seconds` | Constructor, explicit configuration and `Generate()` wall time |
| `tracemalloc_peak_bytes` | Peak traced allocations during that measured interval |
| `process_peak_rss_bytes` | Process lifetime peak resident memory through generation |
| `error` | Null on success, otherwise a serializable error type and message |

Timing excludes package imports, subprocess startup, source/environment
inspection, hashing and report writing. It **includes tracemalloc overhead** and
the legacy method's internal DataFrame preview formatting even though logging
output is disabled. Compare observations produced by the same recipe and
dependency/runtime environment; these timings are not bare-generator speed.

Tracemalloc does not promise to measure all native allocations. Peak RSS adds
process-level evidence, but includes imported modules and runtime startup; it
is not an incremental generation-memory figure. It is null where Python's
`resource` module is unavailable. Each fresh process prevents earlier sizes
from inflating later peak RSS. Allocation peaks, RSS and elapsed time are
observations and are not expected to replay bit-for-bit.

The row fingerprint hashes UTF-8 compact JSON arrays, one per row, each followed
by LF. Column order is `datetime, open, high, low, close, volume`; timestamps use
ISO-8601, OHLC values use JSON floating-point numbers, and volume uses a JSON
integer. Non-finite prices and non-UTC timestamps are rejected. A fingerprint
checks scenario replay and is not a statistical realism claim.

Use repeated observations and compare distributions before drawing performance
conclusions. Record machine/load details separately when hardware comparisons
matter. The initial benchmark is diagnostic evidence for subsequent work,
including dependency separation (ADR-0006), not a performance regression gate.

## Initial observed baseline

The [2026-10-15 machine-readable evidence](benchmarks/legacy-baseline-2026-10-15.json)
contains the commands and two unmodified reports from the same source hashes:
CPython 3.11.17, pandas 1.5.3, NumPy 1.24.4 and the real pandas-ta 0.3.14b0 on
Linux x86-64. Every requested size completed, including one million rows. These
are single observations on a shared execution host, with tracing enabled; they
are not hardware-independent targets or performance guarantees.

The million-row observation took 38.156 seconds, with a traced allocation peak
of 434,467,955 bytes and process peak RSS of 1,185,656,832 bytes. Its output
contained exactly 1,000,000 rows and had the SHA-256 fingerprint
`78619ec8c45cf885efda3ac7128d6b94f2affba7da1f64cc157991f5b71374b9`.

The million-row run started before the implementation commit was created, so
its recorded Git revision is the initial checkout revision. Both reports retain
the exact package and benchmark source hashes; those hashes match each other.
The smaller-size report records implementation commit `6d61e18`. Reproduce the
recipe in the corresponding legacy dependency environment; later dependency or
model migrations need their own observations.
