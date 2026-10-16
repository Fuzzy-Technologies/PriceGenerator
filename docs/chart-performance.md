# Chart performance evidence

`tools/benchmark_charts.py` records real Python exports and native Canvas
initialization, PNG export and data-view actions for 1,000, 10,000 and 100,000
input candles. It is a diagnostic command, without speed or memory thresholds.
The checked-in report is an observation, not a universal performance guarantee.

## Current 1,000-candle verification

[The modern schema-v2 report](chart-performance-2026-10-16-modern.json) records
one actual 1,000-candle run against commit `1a01113`, including unchanged source
and recipe hashes. SVG row counts, decoded Python PNG/JPEG dimensions, and real
Canvas row counts passed. This is a functional diagnostic observation, with no
speed threshold or claim about other sizes. Reproduce the recorded small run:

```bash
python tools/benchmark_charts.py --sizes 1000 --timeout 60 --output chart-performance.json
```

## Archived pre-v2 observation

[The final JSON report](chart-performance-2026-10-15-final.json) records one
observation per size on 2026-10-15 UTC, using measured integration commit
`e61bb9f4d1c42db99510302d0210e77616b1cc1c`. Source and benchmark recipe hashes
were unchanged before and after the run. The invocation is retained in the JSON;
the Canvas module was resolved from another checkout's identical locked
installation. This revision includes the timestamp reuse optimization and final
interactive visual fixes. The report identifies the exact implementation measured.

The environment was Linux x86-64, an AMD EPYC 9V74 host exposing 9 CPUs,
Python 3.11.17, pandas 2.2.3, NumPy 2.2.6, Bokeh 3.6.3, Node 24.19.0,
ECharts 6.1.0 and native Canvas 0.1.100. Each case used fresh Python and Node
processes, without warmup or repeated-run aggregation.

| Input candles | Initial visible candles | Canvas Mount, ms | PNG export, ms | Full-range drawing, ms | Node peak RSS, MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 1,000 | 166.1 | 257.8 | 43.1 | 256.7 |
| 10,000 | 1,000 | 259.9 | 215.7 | 320.3 | 382.7 |
| 100,000 | 1,000 | 798.1 | 267.0 | 1,824.6 | 1,133.5 |

Node RSS covers its complete workflow, including PNG decoding, array copies and
full-range rendering; it is not the memory cost of the initial 1,000-candle view.
The report also records zoom, pan, reset and update timings with verified counts.

| Input candles | New HTML pipeline, s | Bokeh HTML pipeline, s | New HTML, bytes | Bokeh INLINE HTML, bytes | SVG, bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0.029 | 0.181 | 907,629 | 1,298,884 | 488,899 |
| 10,000 | 0.216 | 0.450 | 2,086,964 | 2,939,907 | 4,167,292 |
| 100,000 | 2.190 | 3.093 | 13,879,248 | 19,529,930 | 41,125,531 |

New HTML pipeline means adapter + HTML renderer + write; Bokeh means model +
INLINE serialization + write. Separate diagnostic snapshot serialization is
excluded from these sums because the new HTML renderer serializes its own
snapshot. At 100,000 rows, new HTML gzip size was 1,126,434 bytes versus
2,897,229 bytes for Bokeh. These are observed costs of this fixture, not a speed
guarantee. Full-range drawing and large exact-data SVGs remain concrete
optimization targets.

## Profile-guided adapter change

[The original report](chart-performance-2026-10-15.json) is preserved unchanged
from integration `10a4c18391f15c8e0297f1efdac926279da2c814`. On that run,
the 100,000-row adapter took 2.955 seconds and the new HTML pipeline took
3.731 seconds, versus Bokeh's 3.504 seconds. Profiling the same fixture showed
300,000 timestamp normalizations and 300,006 repeated pandas import lookups.
Under cProfile, timestamp normalization accounted for 2.432 cumulative seconds,
pandas lookup for 0.800, and DataFrame copying for only 0.006; profiler overhead
means these figures are diagnostic, not wall-time replacements.

The adapter now binds pandas once per batch and reuses the validated candle
alignment only for matching typed datetime columns. Sparse, reordered,
differently typed and object columns retain scalar validation. Snapshot copying
and numeric validation remain intact.

| Input candles | Adapter before, s | Adapter after, s |
| ---: | ---: | ---: |
| 1,000 | 0.032 | 0.017 |
| 10,000 | 0.228 | 0.118 |
| 100,000 | 2.955 | 1.337 |

Both runs use identical benchmark recipes and ChartSpec fingerprints for all
three sizes; their SVG bytes and digests also match. Final interactive visual
fixes change HTML and PNG bytes, so those digests deliberately differ. Each
report is a single observation; concurrent load and runtime noise still apply.

## Current modern-only reproduction

The historical tables and JSON above retain their original implementation and
environment identity. Current code no longer imports or measures Bokeh; reproduce
those old comparisons from their recorded historical revisions only. The current
command measures native SVG, PNG, JPEG and offline HTML plus real Canvas actions.
Install the export extra and locked developer-only Canvas harness; chart users
do not need Node.js or that native package:

```bash
python -m pip install -e ".[export]" -c requirements/modern.txt
npm ci --prefix tools/chart_runtime --ignore-scripts --no-audit --no-fund
python tools/benchmark_charts.py --sizes 1000 10000 100000 --timeout 60 --output chart-performance.json
```

`--source-root` selects another local checkout for integration checks, while
the report fingerprints that checkout and both benchmark scripts separately.
Changes to those sources during a run invalidate its overall success status.
`--canvas-module` accepts an explicit installed Canvas module directory when the
locked package is installed elsewhere. `--node` selects the Node executable.
No browser launches, network requests or package installations occur during a
benchmark run. The default worker timeout is 60 seconds. The parent owns
temporary exports and cleans them even when a worker fails. On POSIX, timeout
cleanup terminates the worker's process group, including its native Canvas child.

Exit code 0 means all requested cases completed and their row counts and actual
PNG outputs passed the command's checks. Exit code 1 preserves failed stages or
worker failures in JSON. Exit code 2 indicates invalid arguments. If writing the
report fails, the report and output error are returned on stdout. A missing
runtime or unsupported fixture is never replaced with simulated performance.

## Current workload and timing contract

The deterministic `arithmetic-ohlcv-v1` fixture starts at
`2020-01-01T00:00:00Z`, has a one-minute interval, alternating rising/falling
candles, varying volume, one custom overlay with 19 leading gaps and one
above-candle annotation. Fixture construction uses a canonical DataFrame; no
legacy model, legacy indicators or stochastic generation participates.

`PrepareChart(analysis=False)`, strict snapshot serialization, each real renderer,
and file writing are separate measured stages. Static SVG contains all source
rows. PNG renders that complete SVG through `resvg-py`; JPEG adds Pillow RGB
encoding at quality90. The PNG/JPEG rendering stages include their native SVG
serialization, not just binary encoding. A real Pillow decoder verifies each
raster's format and complete SVG dimensions outside the measured render/write
stages. Interactive HTML embeds the real ECharts runtime and official assets.

Fixture construction, imports, compression, hashes and decoder verification are
excluded from stage timings. Python uses `perf_counter_ns`; Canvas uses Node's
`performance.now`. Each artifact records its encoded size, reproducible gzip
size and SHA-256. Binary gzip sizes are diagnostic values, without a claim that
already-compressed PNG/JPEG benefit from further compression. The schema-v2
report contains no current-engine speed comparison against archived engines.

## Native Canvas scope

The Node worker reuses `tools/chart_runtime/canvas_environment.cjs`, the actual
vendored ECharts engine and the locked `@napi-rs/canvas` raster implementation.
The shared harness uses SSR mode and suppresses animation timers. The benchmark
requires every series to disable progressive rendering and animation, then
explicitly flushes Canvas after each action. DOM control/lifecycle objects are
small shims; they do not emulate browser layout or input delivery.

Measured observations include:

- parsing the embedded snapshot/theme/branding JSON;
- `Mount`, including image decoding/tinting, ECharts initialization, initial
  drawing, control binding and raster flush;
- immediate real PNG export at pixel ratio 2, with decoded dimensions verified;
- zoom to 250 candles (or half the input for smaller requested cases), pan one
  window backward, and reset to the renderer's initial view;
- replacement of the full candle data array after increasing the final high by
  0.01, while retaining the current viewport; preparation of that array is excluded;
- full-range dispatch and drawing of every input candle;
- price and volume counts after every action and the native process's peak RSS.

For inputs above 5,000 candles, the current renderer initially displays the last
1,000 and retains every original row. Counts in the report distinguish total
input from visible data. Full-range timing exposes the cost of requesting all
rows. Static SVG currently renders the entire snapshot, so a 100,000-row SVG is
a large exact-data artifact rather than a sampled overview.

These are **headless Canvas measurements**, not browser startup, pointer latency,
screen refresh rates or FPS. Font selection, browser layout, GPU compositing,
hardware and concurrent load can change real user experience. The scopes differ
between Python HTML generation and Canvas drawing; the report does not turn
them into a single speed ratio or claim that every workload is faster.

## Reading the report

The versioned JSON contains source/recipe hashes, Python and dependency versions,
and one case per requested input size. Each successful Canvas case records its
Node, ECharts and native Canvas versions, operating system/CPU information,
timing scopes and visible counts. Failures retain the requested size and a
serializable error instead of invented timing values. `performance_gate` is
false; compare repeated observations in a controlled environment before setting
regression budgets.
