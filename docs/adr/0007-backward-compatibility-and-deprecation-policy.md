# ADR-0007: Backward compatibility and deprecation policy

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #35, #37
- **Related Tasks:** #60, #62, #66, #68

## Context

PriceGenerator has published Python APIs, CLI flags, CSV behavior and DataFrame conventions dating back several releases. Modernization must avoid turning internal cleanup into accidental user-facing breakage.

At the same time, preserving every implementation accident forever would prevent a coherent deterministic platform.

## Decision

Compatibility is handled explicitly.

### Preserve by default

- `pricegenerator.PriceGenerator.PriceGenerator` compatibility import path;
- existing core public methods during the modernization window;
- legacy DataFrame column names in the compatibility facade;
- existing CLI flags, with additive options preferred;
- published stochastic semantics through a named legacy model.

### Deprecation rule

A public behavior intended for removal or breaking change should normally:

1. be documented as deprecated;
2. have a replacement/migration path;
3. remain available for at least one planned minor release unless security/correctness requires otherwise;
4. be removed only in a version whose compatibility policy permits it.

### Major-version candidates

A major-version decision is required for changes such as:

- removing the legacy public facade;
- changing canonical public columns by default;
- replacing the default stochastic model in a behaviorally incompatible way;
- changing promised seeded-result semantics;
- removing established CLI/API surface without a compatibility adapter.

## Consequences

- refactors require characterization evidence;
- deterministic model semantics become part of compatibility reasoning;
- “internal” changes that alter random-number consumption may be user-visible;
- deprecations become planned work rather than surprise cleanup.
