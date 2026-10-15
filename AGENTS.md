# Engineering instructions

Read [DEVELOPMENT_PROTOCOL.md](DEVELOPMENT_PROTOCOL.md),
[PYTHON_CODE_STYLE.md](PYTHON_CODE_STYLE.md), the applicable accepted
[ADRs](docs/adr/README.md), and [development commands](docs/development.md)
before changing code.

- Start coherent implementation branches from `develop`; use a PR back to
  `develop`. Never directly change `master` or publish a package as part of a PR.
- Native GitHub Tasks, Features, hierarchy, milestone, Priority and Effort are
  authoritative. Link implemented Tasks explicitly in the PR body.
- Keep independent streams in isolated branches. Avoid simultaneous ownership
  of shared metadata or workflow files.
- Follow the Python contract for new and modified code. Preserve legacy public
  names where compatibility requires them; do not reformat unrelated legacy code.
- Run focused tests during implementation and the shared CI gate for integration.
  Test failure, authorization and cleanup paths with fakes, never production APIs.
- Use real dependency implementations for baseline evidence. Never replace a
  missing dependency with a stub while claiming legacy compatibility.
- Keep generated scratch output out of commits. Commit purposeful, reproducible
  scientific evidence and its generating commands when relevant.
- Record actual validation commands and outcomes in the Task/PR timeline. A
  passing local run is not a claim that hosted CI passed.
- Merge and release authorization follows the current user instruction and
  development protocol; PyPI publication always needs explicit authorization.
