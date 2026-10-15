# Development and validation

The [F-Tech development protocol](../DEVELOPMENT_PROTOCOL.md),
[Python code style](../PYTHON_CODE_STYLE.md) and
[accepted ADRs](adr/README.md) apply to this repository. Implementation branches
start at `develop`, and their PRs target `develop` with complete native Task and
PR metadata. Release review and PyPI publication are separate operations.

## Reproduce the bootstrap gate

The initial CI runtime is CPython 3.11 on Ubuntu 24.04. This is a verified legacy
compatibility environment, not a promise that historical dependencies support
every newer Python version. The modern package contract has separately verified
CPython 3.10, 3.11, 3.12 and 3.13 core/extras installation and behavior; CI
automatically selects that matrix when `pyproject.toml` is present.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/ci.txt -r requirements/ci-legacy.txt
python -m compileall -q pricegenerator tools tests
python -m ruff check --select E4,E7,E9,F,D --ignore D202,D203,D213 tools/pr_merge_links.py tests/test_pr_merge_links.py
python -m pytest -q tests/test_pr_merge_links.py --cov=tools.pr_merge_links --cov-branch --cov-fail-under=95 --cov-report=term-missing
python -m build --no-isolation
```

The bootstrap pins contain actual legacy generation/rendering dependencies and
an immutable source revision of pandas-ta 0.3.14b0, which is no longer available
from PyPI. They intentionally do not install unused historical notebook and
bkcharts packages. The separate baseline lock records the complete historical
environment; this small CI lock exists so the CI bootstrap can be reviewed and
merged independently of baseline capture.

The workflow creates a second environment, installs the built wheel, imports it
with Python isolated mode outside the checkout, and generates five candles.
This prevents source-tree imports from masking missing wheel files. It then
seeds the legacy RNG with zero and runs **every** project test, including new
benchmark, rendering and baseline-invariant tests as they land. The historical
tests' disposable CSV/HTML outputs are ignored by Git. The separate baseline
wrapper runs installed-package characterization in a temporary directory when
reproducing archival evidence; CI does not replace the full suite with that subset.

After modern packaging is present, CI installs the wheel with constraints from
`requirements/modern.txt`, checks core-only operation, installs render/indicator
extras, checks their actual behavior, runs `pip check`, and executes the modern
test suite. Modern builds use the exact isolated backend pins in `pyproject.toml`;
the legacy build uses the bootstrap tooling environment. The suite includes
baseline invariants: a dependency migration must account
for any changed output explicitly instead of silently skipping evidence. The
selected matrix is CPython 3.10 through 3.13. Additional supported runtimes need
installation and behavioral evidence before extending that contract. CI stores
sdist/wheel artifacts and JUnit reports for
14 days. Artifact hashes and installed versions appear in the build logs.

CI has only `contents: read`, does not retain checkout credentials, and has no
publishing credentials or publication command. New automation receives lint and
docstring checks without rewriting unrelated legacy formatting. No automatic
`ruff format` step is used. Branch/ruleset protection must require the
`quality (3.11)` check to make failures block merge; a workflow alone cannot
change repository merge policy.

## Linked Task completion

Write an explicit completion instruction on its own PR-body line:

```text
Closes #123, #124
Fixes #125
Resolves #126
Implements #127
```

Keywords are case-insensitive and accept normal singular/past inflections.
Lists and same-repository qualified references are supported. Plain mentions,
other repositories, pull request URLs, block quotes, code blocks, inline code,
HTML comments and invalid numbers never authorize completion. Keep completion
instructions outside examples and prose paragraphs.

For a merged same-repository PR into `develop` or `master`, the separate closed
event workflow checks out the trusted integration branch. Its stdlib-only
script reads the event JSON as data, verifies each referenced object is an open
Issue with native type `Task`, posts a completion comment, closes it with
`state_reason=completed`, and reads back the result. Labels cannot substitute
for native issue type. Features, PRs, already-closed Tasks and absent issues are
skipped. A failed read, comment, close or verification stops cleanup.

Only after successful Task processing may cleanup delete the same-repository
head branch. It skips `master`, `main`, `develop`, the current base/default
branch, protected branches, and branches whose head moved since the merge.
Already-deleted branches and deletion failures do not undo Task completion.
The workflow has only the `contents: write` and `issues: write` permissions
needed for these operations, and runs neither PR-head code nor dependencies.

Fork PR tokens are read-only, so their automatic completion is deliberately
skipped. After reviewing a merged fork PR, a maintainer must comment and close
its native Tasks as completed. Fork branches are never deleted. A future
`pull_request_target` version can remove this manual fallback once the reviewed
workflow is available on the default branch; it must retain the trusted-checkout
boundary. This bootstrap does not change `master` just to activate automation.

Use the read-only parser locally when preparing a PR body:

```bash
PR_BODY='Closes #123, #124' python tools/pr_merge_links.py
```

The first automation PR may require manual Task completion if GitHub evaluated
the merge event before the workflow existed on its base branch. Read back Task
state and branch cleanup after every merge; do not infer success from a merge
response alone.
