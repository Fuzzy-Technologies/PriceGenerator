# ADR-0003: RNG ownership and reproducibility contract

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Feature:** #31
- **Related Tasks:** #49, #50, #51

## Context

Current generation uses Python's module-global `random`, consumes randomness during object construction and defaults `timeStart` from wall-clock/local timezone state. External callers can call `random.seed()`, but that is process-global behavior rather than a library contract.

Trading-system regression tests require scenarios that can be replayed exactly and independently.

## Decision

The deterministic generation path owns its RNG explicitly.

Scenario identity includes at least:

- generator model identifier/version;
- RNG identifier;
- explicit seed;
- complete generation configuration;
- time/timezone configuration;
- PriceGenerator library version.

The target invariant is:

> Same supported model version + RNG + configuration + seed + library version produces the same scenario.

The first deterministic implementation should prefer the lowest-risk RNG transition that can preserve legacy algorithm semantics. A dedicated `random.Random(seed)` instance is therefore the preferred initial candidate for legacy-compatible deterministic generation; switching to NumPy RNG is a separate model/compatibility decision.

A scenario manifest must be serializable and sufficient to reconstruct deterministic input state.

## Consequences

- generator instances no longer interfere through global RNG state;
- `seed=0` is a valid seed and must work in CLI/API;
- benchmarks and statistical tests become reproducible;
- algorithm changes that alter random-number consumption may be compatibility-significant for a model that promises exact seeded sequences.

## Compatibility

Unseeded legacy usage remains supported. This ADR does not promise that accidental historical workflows based on external global `random.seed()` remain a permanent public contract.
