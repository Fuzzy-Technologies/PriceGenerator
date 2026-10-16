# ADR-0005: Statistical validation and realism claims

- **Status:** Accepted
- **Date:** 2026-09-12
- **Roadmap:** #28
- **Related Features:** #33, #34
- **Related Tasks:** #54, #55, #56, #57, #58, #59

## Context

PriceGenerator historically describes generated prices as similar or close to real market prices. Visual similarity is not sufficient evidence for that claim.

Synthetic market-data quality is multidimensional: structural validity, marginal distributions, temporal dependence, cross-variable dependence and market mechanics are different properties and should not be collapsed into one word.

## Decision

Public claims about realism or similarity must be tied to explicit, reproducible statistical evidence.

Validation is organized into levels:

1. **Structural realism** — OHLC/schema/timestamp validity and configured continuity.
2. **Marginal statistical realism** — returns, candle body/wick/range, volume and extreme-event distributions.
3. **Temporal realism** — serial dependence, volatility clustering, regimes and drawdown behavior.
4. **Cross-variable realism** — relationships such as volume/activity vs volatility/returns.
5. **Market-mechanics realism** — sessions, gaps, spread/slippage, liquidity, order book, latency and microstructure.

A model may claim only the levels and metrics it has actually validated.

Finite-sample probabilistic parameters are assessed with explicit statistical tolerance/confidence rules rather than exact equality.

## Consequences

- README/metadata wording becomes evidence-backed;
- model suitability can be stated per testing use case;
- “looks realistic” is not an acceptance criterion;
- validation reports become first-class engineering artifacts.

## Non-goals

This ADR does not require PriceGenerator to simulate every market mechanic. It requires the project to be honest and measurable about what each model does and does not reproduce.
