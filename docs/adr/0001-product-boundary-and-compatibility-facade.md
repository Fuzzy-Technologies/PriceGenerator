# ADR-0001: Product boundary and compatibility facade

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #37, #38

## Context

PriceGenerator historically combines stochastic generation, OHLCV storage, CSV I/O, statistical analysis, technical indicators, chart rendering, CLI parsing and process-level logging behavior in one public class/module.

The project is now expected to serve as a long-lived synthetic market-data component for Fuzzy Technologies trading-system testing and quantitative R&D. A rewrite would risk losing published behavior and breaking existing users, while keeping the current monolith as the only architecture would make reproducibility, validation and optional dependencies unnecessarily difficult.

## Decision

PriceGenerator will evolve behind a **stable compatibility facade**.

The existing public import path and `PriceGenerator` class remain the compatibility entry point during modernization. New internal boundaries may be introduced incrementally:

- generation core;
- explicit generation configuration;
- market-data validation;
- statistical analysis;
- I/O;
- optional rendering/indicator integrations;
- CLI adapter.

The compatibility facade may translate legacy mutable attributes and public methods into the new internals.

The product boundary is:

> A reproducible synthetic OHLCV scenario generator and market-data validation toolkit for trading-system testing and quantitative R&D.

Visualization and technical-indicator presentation are useful integrations, but they are not the product's core stochastic responsibility.

## Consequences

### Positive

- published API can remain usable while internals improve;
- deterministic generation can be isolated from rendering and file-system side effects;
- core installation can become smaller;
- new generator models can coexist with legacy behavior.

### Negative

- some adapters and duplicate paths will exist during migration;
- legacy stateful semantics may need explicit compatibility tests;
- modernization will be incremental rather than a single cleanup.

## Non-decisions

This ADR does not choose module names, a plugin framework, a new default generator model, or a major-version schedule.

## Implementation constraint

No production responsibility should be moved until characterization tests protect the relevant public behavior.
