# Published 1.x engineering baseline (archival evidence)

This document records historical observations, not the modern runtime contract.
The old source and characterization tools remain in immutable Git revision
[`88f6d52`](https://github.com/Fuzzy-Technologies/PriceGenerator/tree/88f6d52a5ff142bbadbef38430cd30324125f33e).
Modern installs/tests do not load the historical model or its dependencies.
[ADR-0010](../adr/0010-modern-only-public-api.md) governs current behavior.

Tasks: [#44](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/44),
[#45](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/45),
[#46](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/46),
[#47](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/47).
Architecture: ADR-0003, ADR-0004, ADR-0007 and ADR-0008.

## Source and transfer continuity

The machine-readable [snapshot](repository-snapshot.json) records repository ID
`326965391`, public visibility, organization ownership, the default `master`
branch, branch heads, all six Git tags/releases, and all 28 PyPI version records
with artifact URLs, sizes, timestamps and hashes as observed on 2026-10-15 UTC.

| Reference | Commit |
| --- | --- |
| `master` | `23c44d1f6eef822770f672e645a451a00c11d02c` |
| `develop` / characterization source | `a97e84829ebee121c411a273845cba871ce07890` |
| `v1.4.93` / latest published release | `0ace3635910d08cf0b1b8f07f95be20f9a8e0636` |

At capture, `develop` was 26 commits ahead and zero behind `master`. The historical
`Tim55667757/PriceGenerator` API URL returned `Moved Permanently` to repository
ID `326965391`, matching the organization repository. Historical release bodies,
author credit and PyPI project URLs are preserved in the snapshot.

The production package, setup file, requirements and historical test file have
an empty diff between `v1.4.93` and the characterization source. All five package
files from the downloaded PyPI wheel are byte-identical to the checkout,
including the Jinja template. Their individual SHA-256 values are recorded.

| Published artifact | Verified SHA-256 |
| --- | --- |
| `pricegenerator-1.4.93-py3-none-any.whl` | `44c1e43db96265d01d184d8260fd873c21e6bd9b16e89379a921f1e6b74e686b` |
| `pricegenerator-1.4.93.tar.gz` | `1ecb572b0d387bda44f33394bdf4ceb99244c7b6c5a91888c4fdba9b81c5e95c` |

Local source builds produce `1.4.dev0`; the historical Travis branch/build-number
environment produced release versions such as `1.4.93`. These are distinct
package identities even though the verified runtime files match. No PyPI upload
or production source modification is part of this baseline.

## Verified environment and installation matrix

The reconstructed environment uses CPython 3.11.17 on Linux x86_64, NumPy 1.24.4,
pandas 1.5.3, Bokeh 3.0.3 and real pandas-ta 0.3.14b0. All direct and transitive
packages, including the historical notebook/bkcharts dependencies, are pinned in
[`archive/baseline-py311.txt`](archive/baseline-py311.txt).

The old pandas-ta release is absent from current PyPI metadata. The baseline
therefore installs the MIT-licensed historical source from
[`ovuncdinc/Pandas-ta@2a24fdc1b69110332db39eda9723a628f75eaf7a`](https://github.com/ovuncdinc/Pandas-ta/tree/2a24fdc1b69110332db39eda9723a628f75eaf7a).
Its package metadata identifies version `0.3.14b0`. This is a pinned public mirror;
the original upstream repository is unavailable. No technical-analysis stubs or
replacement indicator formulas are used. The original deleted PyPI artifact was
not available for a byte-for-byte comparison with this mirror.

| Installation | Import / dependency check | Historical tests | New characterization |
| --- | --- | --- | --- |
| Source at `a97e848`, local version `1.4.dev0`, pinned environment | Pass | 23 passed | 15 passed, 2 strict xfails |
| Hash-verified PyPI wheel `1.4.93`, fresh pinned environment | Pass | 23 passed | 15 passed, 2 strict xfails |
| Unconstrained `pricegenerator==1.4.93` on Python 3.11.17 today | Dependency resolution fails: available pandas-ta releases require Python >=3.12 | Not run | Not run |
| Python 3.9, 3.10, 3.12+, other OSes, latest dependency combinations | Not certified by this baseline | Not run | Not run |

Both successful rows ran from disposable working directories against installed
packages. See [source evidence](source-test-results.json) and
[published-wheel evidence](published-test-results.json) for versions, module paths,
individual test outcomes, warnings and commands. Three upstream deprecation
warnings remain visible. The two expected failures are known model defects,
not installation failures. The unpinned resolver observation is recorded in
[the installation matrix](install-matrix.json).

Historical reproduction is isolated from the modern checkout (Git and `uv` required).
Use the original characterization tools from their immutable revision:

```bash
git worktree add --detach ../PriceGenerator-baseline-tools 88f6d52a5ff142bbadbef38430cd30324125f33e
git worktree add --detach ../PriceGenerator-legacy-source a97e84829ebee121c411a273845cba871ce07890
uv venv --python 3.11.17 .venv-legacy
uv pip install --python .venv-legacy/bin/python -r docs/baseline/archive/baseline-py311.txt
uv pip install --python .venv-legacy/bin/python --no-deps --no-build-isolation ../PriceGenerator-legacy-source
uv pip check --python .venv-legacy/bin/python
.venv-legacy/bin/python ../PriceGenerator-baseline-tools/tools/baseline_tests.py --report /tmp/pricegenerator-source-results.json
```

For the published-wheel row, create another empty virtual environment, install
the same lock, then install the wheel URL from `repository-snapshot.json` with
`--no-deps`, verifying the SHA-256 above. Run the same wrapper with that
environment's interpreter. Its isolated `-I` import smoke rejects imports from
the repository. The wrapper seeds the unmodified historical tests with zero,
copies their CSV/template inputs, and removes generated CSV/HTML/Markdown outputs
when the test process finishes. No browser is opened.

## Characterization contract

[Historical `tests/legacy_harness.py`](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/88f6d52a5ff142bbadbef38430cd30324125f33e/tests/legacy_harness.py) seeds Python's global
MT19937 **before construction**, retaining the three constructor random draws.
It restores caller RNG, stderr and logger state even after generation fails.
A test-only `tzlocal()` override pins UTC because the old generator otherwise
forces the host timezone. Explicit generation inputs and a fixed start time are
stored with every scenario. This helper is serial test machinery; it is not a
thread-safe API and does not define the future per-instance RNG interface.

[`archive/legacy_cases.json`](archive/legacy_cases.json) holds full golden rows
for default-equivalent settings, bounded five-decimal prices and a three-part
up/down/no-trend scenario. The default case explicitly records the constructor
bounds and volume selected by seed zero, while leaving documented derived values
as `null`. Fingerprints use compact UTF-8 JSON arrays with ISO timestamps,
fixed-precision decimal OHLC strings and integer volumes. They avoid pandas'
internal serialization formats. Expected rows are checked in and never regenerated
by tests.

Nine additional deterministic runs check column order, finite numbers, OHLC
ordering, close and volume bounds, integer volume, first-open identity, exact
open/previous-close continuity, horizon, monotonic unique timestamps and timeframe.
Unsplit body bounds include one price tick for floating-point rounding. These
are measured properties of the specified configurations, not universal realism
claims or a promise that every legacy parameter combination is valid.

[`archive/legacy_indicators.json`](archive/legacy_indicators.json) captures 240
input candles and 19 real indicator vectors for migration comparisons. It includes
the historical overwrite of `hma5` by the Alligator Lips calculation. The baseline
test compares all vectors, NaN positions included, with `rtol=atol=1e-12`.

## Known defects remain explicit

| Reproduction | Observed result | Repair work |
| --- | --- | --- |
| Seed 0, five candles, close bounds 1–2, initial close 1, outlier limit 5, outlier probability 1 | Lows include `-1.62` and `-3.62` | [#64](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/64) |
| Seed 0, ten candles, forced up trend, close bounds 10–110, initial close 50, body limit 0.1 | Final body is 17.39 (`open=50.07`, `close=67.46`) | [#63](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/63) |

Both assertions are `xfail(strict=True, raises=AssertionError)` and link to the
corresponding repair work. Unexpected success fails the gate and requires an
explicit model/compatibility decision. No retry, broad exception swallowing or
production correction hides these defects.
