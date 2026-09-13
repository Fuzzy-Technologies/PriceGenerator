# ADR-0002: Canonical OHLCV market-data contract

- **Status:** Accepted
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Feature:** #32
- **Related Tasks:** #52, #53, #26, #27

## Context

PriceGenerator 2.x needs one market-data contract that works for deterministic generation, CSV exchange, statistical analysis, Python workflows and MQL5 test pipelines.

The 1.x implementation exposes `datetime, open, high, low, close, volume`, but datetime/timezone behavior and validation are not defined as a durable contract.

Because v2 is allowed to break 1.x, the canonical representation should be selected from target-system requirements rather than legacy compatibility pressure.

## Decision

The canonical language-neutral v2 OHLCV table contains explicit fields/columns:

`datetime, open, high, low, close, volume`.

The explicit `datetime` field is retained because it serializes cleanly and keeps the schema portable across pandas, CSV and MQL5. It is not retained merely to preserve the 1.x Python API.

Canonical generated series must satisfy:

- timestamps are valid and follow the declared timezone policy;
- timestamps are monotonic ascending and unique;
- OHLC values are finite numeric values;
- `high >= max(open, close)`;
- `low <= min(open, close)`;
- `high >= low`;
- generated volume satisfies the model's declared domain;
- continuity/gap rules are explicit model or scenario properties.

A pandas DatetimeIndex may be exposed as an explicit helper/view. Index state is not part of the language-neutral wire/CSV schema.

Deterministic scenarios must not depend implicitly on the host machine's local timezone.

## Consequences

- generators and loaders share one validation vocabulary;
- CSV/Python/MQL5 interchange uses the same explicit fields;
- pandas-native indexed workflows remain available without defining the cross-language format;
- CSV datetime parsing fixes cannot silently redefine the market-data contract;
- migration from 1.x can be documented independently from the v2 schema decision.

## Open questions to resolve in implementation

- default deterministic timezone;
- handling of timezone-naive imported data;
- exact volume dtype policy for third-party datasets;
- policy for gaps/session calendars in non-continuous markets.
