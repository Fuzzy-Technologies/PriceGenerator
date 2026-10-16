# Development and validation

Start at [AGENTS.md](../AGENTS.md), then read the
[development protocol](../DEVELOPMENT_PROTOCOL.md),
[Python style contract](../PYTHON_CODE_STYLE.md) and [accepted ADRs](adr/README.md).
Use an isolated branch from `develop` and a PR back to `develop`; preserve native
GitHub Task links, milestone, priority/effort and review evidence. Publication is
a separate release operation.

## Locked modern environment

CPython 3.10–3.13 is the supported package window. Create one environment per
runtime when verifying support; installing on one version does not certify the
others. From the repository:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m compileall -q pricegenerator tools tests
```

`requirements.txt` installs the editable modern package with development/export
extras under `requirements/modern.txt` constraints. Modern generation, analysis,
indicators, SVG and offline HTML use no Bokeh, Jinja or TA backend. PNG/JPEG tests
need the real `[export]` dependencies. Historical dependency locks and fixtures
are evidence under [the baseline archive](baseline/README.md), outside the active
runtime and modern test contract.

## Focused checks and shared gate

Run tests relevant to each change during development. For example:

```bash
python -m pytest -q tests/test_generation_v2.py tests/test_scenario_v2.py tests/test_cli_v2.py
python -m pytest -q tests/test_packaging.py tests/test_release_contract.py
python -m ruff check --select E4,E7,E9,F,D --ignore D202,D203,D213 pricegenerator tools/release_verify.py tools/release_install.py
```

The repository's naming/docstring/vertical-spacing rules apply to maintained
code and tests. `ruff format` is not the canonical formatter. Do not rewrite
unrelated files or replace real dependency evidence with stubs.

Before integration, run the complete gate:

```bash
python -m pytest -q tests
python -m build
python -m twine check --strict dist/*
python tools/release_verify.py --artifacts dist
python tools/release_install.py dist
```

Build produces an sdist and builds its wheel from that sdist. Artifact verification
installs each archive into a separate clean environment, runs public APIs and CLI
from outside the checkout, checks core dependency absence, then checks actual
PNG/JPEG exports. Preserve commands/results and artifact hashes in the Task/PR.
Local results do not establish that hosted CI passed.

The PR quality workflow checks all supported Python versions, the full suite,
maintained-module lint, isolated artifacts and metadata. It also exercises
Task-lifecycle failure paths. Require the relevant hosted quality checks and
chart runtime check in branch protection/rulesets; committing a workflow does
not configure those repository settings.

## Chart runtime gate

Node is developer tooling for rebuilding/testing the vendored ECharts bundle;
it is unnecessary when users generate HTML or SVG. Reproduce the JS gate with:

```bash
npm ci --ignore-scripts --no-audit --no-fund --prefix tools/chart_runtime
npm run build --prefix tools/chart_runtime
git diff --exit-code -- pricegenerator/rendering/assets/echarts
node --test tests/javascript/test_interactive_charts.cjs tests/javascript/test_interactive_canvas.cjs
```

The gate checks actual ECharts/Canvas behavior, offline assets, export and
branding. A parseable HTML file is insufficient evidence of interaction.
[Chart performance](chart-performance.md) records workload and measurement
boundaries; a Canvas timing is not a browser FPS claim.

## Task lifecycle and release

Use explicit closing instructions such as `Closes #123` on their own PR-body
line. The linked-Task workflow only completes native Tasks after a successful
merge and verifies state before branch cleanup; plain mentions do not authorize
completion. Fork PRs retain their documented manual completion path. Read back
Task and branch state after merge.

See [release instructions](releasing.md) for exact tagged-master verification,
reviewed artifacts, PyPI Trusted Publishing and the protected `pypi` environment.
Ordinary CI and tag pushes never publish a package. Do not invoke old release
branch/Travis commands.
