# ADR-0007: v2 breaking-change and migration policy

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #35, #37
- **Related Tasks:** #60, #62, #66, #68

## Context

PriceGenerator has a published 1.x Python API, CLI surface, DataFrame conventions and stochastic behavior.

The 2.x modernization is intended to establish a cleaner deterministic platform. Requiring source-level backward compatibility with 1.x would preserve implementation accidents and constrain the new architecture.

At the same time, stochastic reproducibility and migration clarity are important for research and trading-system test assets.

## Decision

### 1.x to 2.x

PriceGenerator v2.0 is an intentionally breaking product line. The project does **not** promise source-level or schema-level backward compatibility with 1.x.

Breaking changes must be deliberate and documented. For each changed public behavior, the project should state one of:

- preserved;
- replaced, with migration guidance;
- removed, with rationale;
- retained only as a named legacy model or compatibility helper.

Historical 1.x behavior is evidence for characterization and regression analysis, not a mandatory public contract.

### Stability inside 2.x

Once a v2 public contract is documented and released, subsequent 2.x releases should preserve it by default unless a later architecture/release decision explicitly authorizes another break.

### Stochastic-model compatibility

Generator model identity is separate from Python API compatibility.

If a model/version promises exact seeded reproducibility, changing its random-number consumption or output sequence is compatibility-significant even when the surrounding Python API is unchanged.

A behaviorally different stochastic model must receive a distinct model identifier/version.

### Deprecation

For established v2 public contracts, prefer documented deprecation and migration before removal when practical. Security, correctness or clearly experimental APIs may justify faster change.

## Consequences

- v2 architecture is not forced to mirror the 1.x class design;
- migration notes become part of release quality;
- historical stochastic behavior can still be reproduced where scientifically useful;
- API versioning and stochastic-model versioning are treated as separate concerns.
