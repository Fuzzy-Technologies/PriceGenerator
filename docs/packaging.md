# Packaging and optional dependencies

## Historical version provenance

Before this migration, `setup.py` hard-coded the base version `1.4` and
interpreted Travis environment variables at build time:

| Build context | Historical generated version |
| --- | --- |
| `TRAVIS_BUILD_NUMBER=93`, branch `release-*` or `master` | `1.4.93` |
| `TRAVIS_BUILD_NUMBER=93`, other branch | `1.4.dev93` |
| Missing either Travis variable | `1.4.dev0` |

The version therefore described the CI job, not only the checked-out source.
The historical `v1.4.93` tag contains this same build logic. Earlier repository
tags are `1.0.19`, `1.1.30`, `1.2.46`, `1.2.58`, and `1.3.81`. They are preserved
as historical provenance; this work does not rebuild or publish those releases.
The historical `.travis.yml` used Python 3.9 and published non-PR `release-*`
branch builds directly. The v2 workflow must never use that publication trigger.

## Deterministic development version

`pricegenerator/_version.py` is the sole version source. Setuptools reads its
literal `__version__` value without importing generation or optional modules.
The package exposes the same value as `pricegenerator.__version__`.
Wheel and sdist versions do not depend on Travis variables, checkout location,
wall-clock time, or the currently installed package version.

`2.0.0.dev0` identifies unreleased v2 development. It does not assert that the
new v2 API or migration is complete. A release version and publication still
require their separate release review under ADR-0008.

## Runtime and dependency boundary

The supported modern runtime is **CPython 3.10–3.13** (`>=3.10,<3.14`).
Clean installed-wheel core and legacy-extra smokes were verified on Linux with
3.10.22, 3.11.17, 3.12.14, and 3.13.16. Each runtime also passed all 16 packaging,
optional-dependency, and process-safety tests. The CI matrix repeats the same
checks; consult its exact run before treating a later revision as verified.
Python 3.9 remains part of historical characterization, not the modern support
promise. Python 3.14+ and alternative interpreters require additional evidence.

| Installation | Purpose | Direct dependency boundary |
| --- | --- | --- |
| `pricegenerator` | Generation and CSV I/O | NumPy, pandas, python-dateutil |
| `pricegenerator[render]` | Legacy `RenderBokeh` / `RenderGoogle` | Bokeh, Jinja2 |
| `pricegenerator[indicators]` | Legacy `GetStatistics`, including TA series | pandas-ta-classic |
| `pricegenerator[notebook]` | Inline Bokeh notebook integration | IPython, ipykernel |
| `pricegenerator[test]` | Tests and metadata parsing | pytest, tomli on Python 3.10 |
| `pricegenerator[docs]` | API documentation | pdoc |
| `pricegenerator[release]` | Local artifact build and validation | build, twine |
| `pricegenerator[dev]` | Test/build tools and static checks | test/release tools, Ruff |

The `render` extra specifically preserves the legacy integrations. The new
renderer modules and their vendored assets are packaged independently of Bokeh
and Jinja2; they do not need this extra. `bkcharts`, matplotlib, requests, and
Jupyter's full `notebook` server are no longer mandatory runtime dependencies.
Some tools may still depend on requests transitively, for example twine in the
release environment. That does not affect a core-only installation.

For the historical rendering methods with statistics enabled, install both:

```bash
python -m pip install '.[render,indicators]'
```

`RenderBokeh(showStatOnChart=False)` needs only `render`. `RenderGoogle` always
calculates the legacy summary and needs `indicators` as well. Inline output
additionally needs `notebook`; missing notebook support is tested without
launching a real host. No claim is made about every Jupyter/frontend combination.
`GetStatistics` retains its historical in-place data enrichment. The planned
non-mutating analysis API is a separate task; packaging does not silently
redefine this legacy method.

Imports are lazy and failures identify the requested extra. Internal import
failures from an installed backend retain their original traceback. Importing
PriceGenerator preserves host stdout/stderr and root logging handlers. Explicit
browser requests use an absolute `file:` URI through `webbrowser.open`, never
a shell command. Failed Bokeh saves do not launch a browser.

## Indicator compatibility evidence

The legacy optional adapter uses **pandas-ta-classic 0.3.78** (MIT), an explicit
replacement for the unavailable historical pandas-ta distribution. Its 19
indicator vectors match the real pandas-ta 0.3.14b0 baseline on the fixed
240-candle input in `tests/legacy_indicators.json`, with `rtol=atol=1e-10` and
identical NaN positions. The test covers SMA, HMA, VWMA, Bollinger Bands, and all
four PSAR vectors. It preserves the historical overwritten `hma5` Alligator
series rather than silently correcting the old API in a packaging change.

Version 0.8.32 was evaluated and rejected for this adapter: all four PSAR vectors
differed from the characterized legacy output. A future backend update must
pass this regression or receive a documented new indicator contract. A finite
fixture establishes this measured compatibility boundary; it is not a claim of
equivalence for every input. Package metadata and upstream provenance:

- [pandas-ta-classic 0.3.78](https://pypi.org/project/pandas-ta-classic/0.3.78/)
- [Upstream repository](https://github.com/xgboosted/pandas-ta-classic)
- [Historical fixture provenance](../tests/legacy_indicators.json)

## Reproducible development and artifact verification

`pyproject.toml` is the dependency declaration. `requirements/modern.txt` is the
exact, reviewed universal constraint set for core, legacy render/indicators,
and development tools, including Python-version-specific transitive pins.
Constraints restrict the selected features; installing them with `-c` does not
install every listed tool into a core environment. Docs and notebook hosts have
separate optional dependencies and are not covered by this constraint snapshot.
The build backend itself is pinned in `[build-system]`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

Update constraints deliberately, then rerun the supported matrix:

```bash
uv pip compile pyproject.toml --extra dev --extra render --extra indicators \
  --universal --python-version 3.10 --output-file requirements/modern.txt
```

The runtime range deliberately stays within NumPy 2.0–2.2 and pandas 2.2 while
legacy behavior is characterized. Bokeh stays within 3.6 because newer series
remove legacy glyph APIs. These bounds can expand after compatibility tests.

Test the actual artifact from outside the repository. For example, with `$repo`
set to the absolute checkout path and `$wheel` to the built wheel's full path:

```bash
python -m venv /tmp/pricegenerator-core
/tmp/pricegenerator-core/bin/python -m pip install \
  -c "$repo/requirements/modern.txt" "$wheel"
cd /tmp
/tmp/pricegenerator-core/bin/python -I "$repo/tests/test_packaging.py" core
/tmp/pricegenerator-core/bin/python -m pip install \
  -c "$repo/requirements/modern.txt" "$wheel[render,indicators]"
/tmp/pricegenerator-core/bin/python -I "$repo/tests/test_packaging.py" extras
```

The smoke checks installed origin, metadata/runtime version agreement, template
and renderer resource inclusion, console/module entry points, generation, CSV
output, absence of optional packages in the core environment, and both legacy
renderers with real indicators in the extra environment. Build wheel from sdist
with `python -m build` so source-distribution omissions cannot hide behind the
checkout. Hash the reviewed artifacts in CI; these checks never upload to PyPI.
