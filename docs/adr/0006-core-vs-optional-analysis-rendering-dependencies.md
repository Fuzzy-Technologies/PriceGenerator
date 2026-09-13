# ADR-0006: Core vs optional analysis/rendering dependencies

- **Status:** Accepted
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Feature:** #38
- **Related Tasks:** #69, #70, #71, #77

## Context

The current main module imports generation, statistical-analysis, technical-indicator and rendering dependencies together. Users who only need synthetic OHLCV generation therefore inherit Bokeh/Jinja/pandas-ta and other historical dependency weight.

Some declared runtime dependencies are not used by the production module, and some legacy dependencies are obsolete.

## Decision

PriceGenerator will distinguish:

- **core runtime** — required for canonical configuration, generation, market-data contract and essential I/O;
- **analysis** — statistical diagnostics not required to generate data;
- **indicators** — technical-analysis integrations;
- **render** — Bokeh/Jinja/browser-oriented visualization;
- **dev/test/docs/release** — non-runtime tooling.

Optional feature sets should be exposed through packaging extras when the architecture supports them.

The core package must be importable and usable for generation without optional rendering/indicator dependencies.

## Consequences

- smaller and safer generation-only installations;
- dependency failures are localized to requested optional features;
- CI must test core and selected extras separately;
- compatibility facade may lazily load optional integrations and provide actionable errors if missing.

## Additional constraints

The new analysis API should not mutate canonical OHLCV data merely to calculate indicators/statistics.

Importing the library must not redirect host-process stderr or execute browser/shell actions.
