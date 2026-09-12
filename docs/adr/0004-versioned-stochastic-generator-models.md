# ADR-0004: Versioned stochastic generator models

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #35, #36, #43

## Context

The current published generator has specific stochastic semantics for direction, bounded candle bodies, upper/lower wick outliers, serial volume and endpoint-enforced trend segments.

Changing those formulas in place would make old scenarios irreproducible and could silently alter tests or user expectations. At the same time, some current semantics are not suitable as the long-term scientifically validated model.

## Decision

Stochastic generation semantics are **versioned explicitly**.

The current published behavior will be characterized and preserved as a named legacy model (working name: `legacy_v1`).

Future models may change trend, outlier, volume or boundary behavior only under a distinct model identifier/version.

Model identity must be included in deterministic scenario manifests and validation reports.

A default-model change is a compatibility decision, not an implementation detail.

## Consequences

- bug fixes that change stochastic output require classification: compatibility fix, legacy behavior preservation, or new-model behavior;
- old scenarios can remain reproducible;
- new model families can be validated independently;
- documentation can state suitability/limitations per model rather than making one global realism claim.

## Model admission rule

A new model must have:

1. a concrete testing/R&D use case;
2. explicit stochastic parameter semantics;
3. reproducibility semantics;
4. invariant tests;
5. statistical validation metrics selected before declaring the model stable.

Familiar financial models are not automatically accepted merely because they are standard names.
