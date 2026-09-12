# ADR-0001: Product boundary and v2 public API

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #37, #38

## Context

PriceGenerator 1.x combines stochastic generation, mutable configuration, OHLCV storage, CSV I/O, statistical analysis, technical indicators, chart rendering, CLI parsing and process-level logging behavior in one public class/module.

The project is being modernized into a long-lived synthetic market-data component for Fuzzy Technologies trading-system testing and quantitative R&D.

The new 2.x line is intentionally allowed to break the historical 1.x public API. Preserving legacy import paths, mutable attributes and method names must not distort the target architecture.

## Decision

The product boundary is:

> A reproducible synthetic OHLCV scenario generator and market-data validation toolkit for trading-system testing and quantitative R&D.

PriceGenerator 2.x will expose an intentional public API organized around:

- explicit generation configuration;
- deterministic, versioned generator models;
- canonical OHLCV validation;
- statistical diagnostics and validation;
- I/O and scenario manifests;
- optional rendering/indicator integrations;
- CLI adapters.

Historical 1.x behavior remains valuable as characterization evidence, migration reference and, where useful, a named legacy stochastic model. It is not a mandatory API-compatibility surface.

A compatibility adapter may be retained only when it has a concrete migration benefit and does not constrain the v2 design.

Visualization and technical-indicator presentation remain optional integrations rather than core stochastic responsibilities.

## Consequences

### Positive

- v2 can correct awkward 1.x API and state semantics;
- deterministic generation can be isolated from rendering and process side effects;
- core installation can become smaller;
- generator-model compatibility can be versioned independently from Python API compatibility;
- migration decisions are explicit rather than accidental.

### Negative

- some 1.x callers will require migration;
- release notes and migration guidance become mandatory for intentional breaks;
- characterization tests are still required to distinguish deliberate redesign from accidental loss of useful behavior.

## Non-decisions

This ADR does not choose final module names, a plugin framework, or a specific future default stochastic model.

## Implementation constraint

Before replacing a 1.x behavior, characterize it well enough to state whether v2 intentionally preserves, replaces or removes it.
