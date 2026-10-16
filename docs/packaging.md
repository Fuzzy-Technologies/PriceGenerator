# Modern package contract

`pyproject.toml` defines metadata, the build backend, dependencies, extras and
`pricegenerator.cli:Main`. `_version.py` provides one deterministic literal for
runtime, wheel and sdist versions. Builds never depend on Travis variables or
the current date. This release candidate uses canonical version `2.0.0`;
publication is a separate reviewed operation. Subsequent development versions
use an explicit `.devN` suffix and are not published by the release workflow.

The supported runtime is CPython **3.10–3.13** (`>=3.10,<3.14`). CI checks modern
APIs from clean installed wheel and sdist environments on each version. An
additional Python version needs installation and behavioral evidence before
metadata can promise support.

| Installation | Purpose | Direct dependencies |
| --- | --- | --- |
| `pricegenerator` | Generation, replay, CSV, analysis, indicators, SVG and offline HTML | NumPy, pandas, python-dateutil |
| `pricegenerator[export]` | Optional PNG/JPEG export | resvg-py 0.5.0, Pillow 12.0.0 |
| `pricegenerator[notebook]` | Notebook host tooling | IPython, ipykernel |
| `pricegenerator[test]` | Tests and metadata parsing | pytest, tomli on Python 3.10 |
| `pricegenerator[docs]` | API documentation | pdoc |
| `pricegenerator[release]` | Build and metadata validation | build, twine |
| `pricegenerator[dev]` | Tests, release tools, coverage and lint | test/release tools, pytest-cov, Ruff |

Bokeh, Jinja2, pandas-ta and pandas-ta-classic are absent from all modern
runtime extras. Indicator formulas use NumPy/pandas directly. Renderer assets,
license files and third-party notices ship in the distributions; retired Jinja
templates do not. The console command and `python -m pricegenerator` share the
modern command interface.

## Reproducible dependencies and verification

`requirements/modern.txt` is the universal exact constraint set for core, export
and development dependencies, including transitive markers. Constraints do not
install optional dependencies into a core environment. Notebook hosts and docs
have separate optional dependencies outside this snapshot. The build backend
is pinned exactly in `pyproject.toml`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/test_packaging.py tests/test_release_contract.py
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*
.venv/bin/python tools/release_verify.py --artifacts dist
.venv/bin/python tools/release_install.py dist
```

Regenerate reviewed constraints deliberately:

```bash
uv pip compile pyproject.toml --extra dev --extra export \
  --universal --python-version 3.10 --output-file requirements/modern.txt
```

The dependency lock under `docs/baseline/archive` describes historical characterization only and never
participate in modern installation or CI. See [release instructions](releasing.md)
for the manual, protected Trusted Publishing workflow and external setup.
