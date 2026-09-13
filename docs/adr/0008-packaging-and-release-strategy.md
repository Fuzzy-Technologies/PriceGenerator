# ADR-0008: Packaging and release strategy

- **Status:** Accepted
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #40, #41
- **Related Tasks:** #75, #76, #77, #78, #79, #80

## Context

The historical package uses `setup.py`, Travis-specific build numbers and direct PyPI upload from release branches. Local builds and CI builds derive versions differently, supported Python versions are not expressed as a modern package contract, and active metadata still references historical personal-account URLs.

A new release must be reproducible and must not be published merely because a branch build ran.

## Decision

Packaging and release will be modernized only after historical release/version semantics are captured.

Target state:

- `pyproject.toml` based build;
- one canonical deterministic version source;
- explicit supported Python versions;
- core/optional dependency separation;
- GitHub Actions PR gate;
- separate release workflow;
- sdist/wheel build plus clean-environment install verification;
- artifact hashes and metadata verification;
- explicit human approval before PyPI publication;
- PyPI Trusted Publishing evaluated/preferred when practical;
- active project metadata points to Fuzzy Technologies while historical provenance remains intact.

## Consequences

- release automation becomes auditable;
- package artifacts, not the mutable source checkout, become the release evidence;
- supported Python/dependency combinations are test-driven;
- old Travis configuration can be retired only after replacement CI/release gates are proven.

## Non-goal

This ADR does not choose a release cadence or force an immediate new public version.
