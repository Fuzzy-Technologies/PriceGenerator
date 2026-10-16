# ADR-0010: Modern-only public API and restrained chart branding

- **Status:** Accepted
- **Date:** 2026-10-16
- **Decision authority:** Explicit user instruction for the v2 implementation and release wave
- **Supersedes in part:** ADR-0001, ADR-0003, ADR-0004, ADR-0006, ADR-0007, ADR-0009
- **Preserves:** Canonical OHLCV, explicit RNG/model identity, independent diagnostics, release review

## Context

Earlier ADRs allowed compatibility helpers, unseeded historical usage, a named
legacy stochastic model, Bokeh/Jinja/TA extras and repeated corporate wordmarks.
The user has explicitly chosen a modern-only v2 runtime, a small root API and a
single restrained price-panel wordmark. Historical source must remain available
as provenance without shipping another executable compatibility implementation.

## Decision

1. The supported generator is `regime_v2` through immutable `GenerationConfig`
   and `Generate(config)`. Configuration has an explicit seed (including zero),
   fixed UTC defaults and private RNG ownership. There is no runtime legacy
   model, mutable legacy class, logger adapter or old command alias.
2. Root convenience APIs cover generation, canonical validation/CSV, manifests,
   exact replay/fingerprints, `Analyze`, `Indicators`, `Chart`, `DisplayChart` and
   compact chunked generation/CSV adapters. Calibration, comparison, bootstrap,
   scripted models and registry research helpers remain module-qualified and
   experimental; their presence is not an empirical realism guarantee.
3. Core dependencies are NumPy, pandas and python-dateutil. Modern diagnostics
   and indicator formulas use this stack. SVG and offline interactive HTML need
   no Bokeh, Jinja, pandas-ta, browser automation or Node at user runtime. The
   optional `export` extra supplies pinned resvg-py/Pillow for PNG/JPEG; notebook
   host and developer tools retain separate extras.
4. `Chart(data)` defaults to interactive HTML and browser viewing. Batch callers
   use `view=False`; static formats require explicit output paths. `DisplayChart`
   embeds HTML by default in a notebook. Rendering does not calculate statistics
   or indicators unless `analysis=True` is explicitly requested.
5. Both chart engines show exactly one translucent corporate wordmark in the
   price panel, none in volume. Preserve the separate main emblem and logo
   geometry; remove the repeated watermark strip. Generated files remain offline
   and retain third-party notices.
6. Historical baseline JSON and its dependency lock are archival documentation,
   outside active tests and runtime requirements. The immutable
   [pre-migration source](https://github.com/Fuzzy-Technologies/PriceGenerator/tree/88f6d52a5ff142bbadbef38430cd30324125f33e)
   retains removed implementations. Do not duplicate old source/templates as
   `.py.txt` or `.j2.txt` pseudo-archives inside modern distributions.

## Consequences

The 1.x→2.x migration is intentionally breaking and documented at the entrypoint
and in the chart guide. No compatibility extra can reinstall retired engines.
Future changes to a released model's draw order or output require a deliberate
model/version decision. A manifest's environmental identity and exact output
fingerprint delimit replay claims; structural and finite-sample tests do not
establish fitness for forecasting or any untested real market.

Earlier ADR text remains historical context. This record overrides only its
conflicting compatibility, dependency and branding provisions; other accepted
invariants and the explicit release approval requirement remain in effect.
