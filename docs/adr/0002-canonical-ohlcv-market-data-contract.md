# ADR-0002: Canonical OHLCV market-data contract

- **Status:** Proposed
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Feature:** #32
- **Related Tasks:** #52, #53, #26, #27

## Context

Generated and loaded data currently share the columns `datetime, open, high, low, close, volume`, but datetime/timezone behavior and validation are not defined as a durable contract.

A historical open issue proposed making `datetime` the DataFrame index. Existing code, renderers and examples access `prices.datetime`, so silently removing that column would be a compatibility break.

## Decision

The legacy-compatible canonical OHLCV table requires the columns:

`datetime, open, high, low, close, volume`.

For the compatibility facade:

- `datetime` remains a column;
- timestamps must be valid, monotonic ascending and unique for canonical generated series;
- OHLC values must be finite numeric values;
- `high >= max(open, close)`;
- `low <= min(open, close)`;
- `high >= low`;
- generated volume must satisfy the model's declared non-negative/positive domain;
- generated continuity rules are model/configuration properties and must be validated where applicable.

Timezone and timeframe semantics must be explicit. Deterministic scenarios must not depend implicitly on the host machine's local timezone.

A DatetimeIndex may be provided as an explicit view/helper, but not as a silent replacement for the public `datetime` column in the legacy compatibility path.

## Consequences

- loaders and generators use the same validation vocabulary;
- CSV parsing fixes cannot redefine the schema merely to silence deprecation warnings;
- downstream Python and MQL5 adapters have a stable column contract;
- a future major version may choose a different canonical representation only through a separate ADR/migration plan.

## Open questions to resolve in implementation

- default timezone for deterministic scenarios;
- whether loaded timezone-naive data is rejected, localized by explicit option, or retained with declared metadata;
- exact volume dtype policy for imported third-party datasets;
- policy for gaps/session calendars in non-continuous markets.
