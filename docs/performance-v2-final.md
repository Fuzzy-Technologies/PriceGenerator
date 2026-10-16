# Final committed-source v2 performance evidence

The [full-frame report](performance-v2-final-full-2026-10-16.json) and
[10,000-row chunk report](performance-v2-final-chunked-2026-10-16.json) record
successful isolated measurements at 100, 1,000, 10,000, 100,000 and 1,000,000
rows. Every corresponding output fingerprint matches exactly. These supersede
the earlier formative reports as reproducible committed-source evidence; the
older raw observations remain archived with their stated provenance limits.

Both modes measured the same clean committed source:
`06b6b4e5d7629afc0a7839287ad0dc3a2c578654`, based on integration commit
`3c3785c`. The fresh isolated worktree had no untracked historical runtime.
Before measurement and after each mode, `git status --porcelain
--untracked-files=all` was empty. All 28 source/recipe inventory paths were
verified against `git ls-files`, and their SHA-256 values remained identical
across both reports. The inventory contains only committed modern package
Python sources, `pyproject.toml`, and `tools/benchmark.py`.

The durable public source is [commit `a6965b1`](https://github.com/Fuzzy-Technologies/PriceGenerator/commit/a6965b1ef17963ed8919f17ce3189b20a65ee9d3).
Its complete set of 28 inventoried package/recipe file hashes was independently
verified against the local committed publication snapshot and matches the
measured commit exactly. The public commit can therefore reproduce the
measured runtime and recipe without access to the local branch. Other
unmeasured documentation/release files may differ. The raw JSON retains its
original local Git SHA; it has not been relabeled as a measurement performed
on the public commit. Later formatting changes do not alter which exact
snapshot these reports describe.

The environment was Linux x86-64, CPython 3.12.14, pandas 2.2.3, NumPy 2.2.6
and python-dateutil 2.9.0.post0; the declared package version was
`2.0.0.dev0`. Full immutable generation configuration and seed zero are in
every case. Workers had a 300-second timeout. Reports were written outside
the measured worktree and copied into this evidence commit afterward.

| Rows | Full elapsed | Chunked elapsed | Full traced peak | Chunked traced peak |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 0.028 s | 0.032 s | 94,383 B | 117,661 B |
| 1,000 | 0.113 s | 0.127 s | 405,641 B | 502,504 B |
| 10,000 | 1.045 s | 1.016 s | 2,993,661 B | 4,332,121 B |
| 100,000 | 10.522 s | 10.364 s | 29,809,469 B | 4,990,026 B |
| 1,000,000 | 103.897 s | 105.178 s | 298,457,213 B | 4,990,439 B |

At one million rows, full generation used 298,457,213 B of peak traced memory
and chunk traversal used 4,990,439 B. Worker lifetime peak RSS was 922,312,704 B
and 89,915,392 B respectively. Chunked traced memory stayed near 5 MB between
100,000 and 1,000,000 rows; small cases include additional chunk bookkeeping.

Both elapsed scopes include generation, canonical validation and exact row
fingerprinting, plus tracemalloc overhead. Imports, configuration validation,
subprocess startup and report writing are excluded. RSS includes startup and
imports and is not incremental memory use. These are single observations on
a shared host, with no timing threshold or performance guarantee. They measure
generation/traversal and hashing, rather than CSV disk throughput. They do not
establish a speed comparison with the removed 1.x model. See the
[benchmark guide](benchmarks.md) for the complete measurement contract.

# Reproduction

Use the public committed source mapped above in an isolated checkout and the
recorded supported environment. Run both commands without editing source files
between cases; write reports outside the checkout to keep it clean:

```bash
python tools/benchmark.py --sizes 100 1000 10000 100000 1000000 --seed 0 --timeout 300 --output /tmp/full.json
python tools/benchmark.py --sizes 100 1000 10000 100000 1000000 --seed 0 --mode chunked --chunk-size 10000 --timeout 300 --output /tmp/chunked.json
```

Compare all source SHA-256 values and complete case configurations before
comparing output hashes. Expected exact hashes are in the raw reports. A new
run on the mapped public commit will record that commit's SHA rather than the
local measurement SHA; the source/recipe hashes are the cross-commit mapping.
Timing and memory values vary with the machine and load. The benchmark tool's
36 focused tests and scoped Ruff checks passed before measurement; no full
pytest run was repeated during the measurement.
