# ADR-0009: Modern static and interactive chart rendering

- **Status:** Accepted
- **Date:** 2026-10-16
- **Related Feature:** [Modernize chart rendering](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/90)
- **Related Tasks:** [Architecture and parity](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/91), [Static rendering](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/92), [Interactive rendering](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/93), [Migration and performance](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/94)
- **Builds on:** ADR-0001, ADR-0002, ADR-0006, ADR-0007

## Context

The 1.x module imports Bokeh, Jinja, and indicator dependencies even when callers only need generation. `RenderGoogle` writes an HTML page that downloads Google Charts, jQuery, and a preloader image; it does not create a standalone static image. `RenderBokeh` supplies useful financial overlays and interaction that cannot be removed merely to reduce bundle size.

The user requests fast, open-source rendering, the existing capabilities or better, restrained corporate neon colors, repeated translucent Fuzzy Technologies wordmarks along the X-axis backdrop, and the main corporate emblem. Existing 2.x ADRs permit deliberate API changes while requiring behavior characterization and an independent core.

## Decision

Use one immutable, validated `ChartSpec` and two optional rendering adapters:

1. A project-owned, standard-library-only SVG renderer for genuine static, offline exports.
2. A custom Apache ECharts 6.1.0 Canvas bundle for interactive HTML. Import only the chart types and components used by the financial report; vendor the pinned runtime and its notices. Generated files work offline without CDN access, npm, or Node.js at user runtime.

`ChartSpec` contains canonical candles, explicitly aligned line/point overlays, plain-text markers, a report, and presentation options. It owns neither generation nor statistical/indicator calculations. Both adapters consume the same JSON-compatible schema. Missing overlay values are `None`/JSON `null`, not nonstandard `NaN`. Timestamps require explicit offsets, normalize to UTC, and cannot exceed millisecond precision. Empty candles, duplicates, disorder, invalid OHLCV, unsupported fields, and misaligned overlays fail before rendering.

The [capability matrix](../rendering-capabilities.md) is the migration checklist. Shipping a renderer that accepts overlays does not prove that legacy indicator calculations and CLI paths have migrated. Task #94 remains the integration and replacement gate.

## Why this combination

Measured distribution sizes on 2026-10-16:

| Candidate | Raw bytes | Gzip bytes | Assessment |
| --- | ---: | ---: | --- |
| ECharts 6.1.0, full distribution | 1,121,883 | 369,080 | Unnecessary chart types; do not ship this default |
| ECharts 6.1.0, selected financial components | 663,962 | 225,182 | Native candle/line/scatter/bar rendering, shared axes, legend, zoom, toolbox, and graphic primitives |
| Lightweight Charts 5.2.1, standalone production | 197,922 | 62,165 | Smaller financial engine; extra work for the old box zoom and report controls; public attribution requirement |
| uPlot 1.6.32, minified IIFE | 51,081 | 22,080 | Smallest candidate; panning and the financial presentation need more custom adapter work |

These are actual installed npm artifact measurements, including a locally built ECharts profile, not browser performance rankings. Smaller download size alone does not establish feature parity or frame latency. The initial interactive runtime budget is 700 KiB raw / 240 KiB gzip including the adapter, excluding candle data and the separately measured branding payload. Changes to that budget require recorded evidence.

ECharts is Apache-2.0; its pinned rendering dependencies include zrender under BSD-3-Clause and tslib under 0BSD. Preserve all applicable notices. The choice satisfies the requested permissive engine licensing without adding a copyleft rendering engine. The project-owned static renderer remains under the repository's Apache-2.0 license. Do not introduce CairoSVG or a browser runtime as a mandatory Python dependency.

Using ECharts SVG SSR for every static export would share the JS renderer but require Node.js execution or a JS bridge in Python workflows. The small native SVG adapter avoids that runtime cost. An optional export service can be evaluated later; there is no plugin framework or service requirement in this decision.

## Presentation and artifact contract

- Dark theme is the default. Cyan, violet, and restrained pink accents share tokens with the light theme. Hollow/filled candle bodies also distinguish direction without relying only on color.
- The supplied logo geometry is preserved. The 1254×1254 original emblem is retained as a source asset; a documented 192×192 PNG derivative is embedded at display size. The filename containing `2048` is not treated as a dimension claim.
- Each SVG embeds each image once in definitions and repeats references along both the price and volume panels' X-axis backdrops. No remote image/font/script is required.
- Text is plain data, escaped by the relevant serializer. Do not accept executable callbacks, HTML snippets, raw CSS, or JavaScript in the portable specification.
- Rendering never mutates source data, launches a browser, invokes a shell, downloads resources, or computes indicators as an implicit side effect.
- Optional interactive shimmer must respect reduced-motion preferences and must not animate price data. Static exports contain no animation.
- SVG is the initial native static format. Browser PNG export belongs to the interactive adapter. No unimplemented Python PNG/PDF API is implied.

## Consequences and completion gates

The static rendering implementation and its imports require neither pandas nor NumPy, Bokeh, Jinja, or pandas-ta; the full package's core dependency metadata may still require libraries used by generation. Interactive output carries a larger runtime than the two smallest candidates, in exchange for less custom interaction machinery and a wider existing feature surface.

The two adapters must be tested against shared data fixtures. Validation includes gap alignment, negative/flat/extreme finite values, hidden overlays, missing data, unsafe text, deterministic serialization, asset provenance, offline resources, and small layouts. Interactive controls need JavaScript behavior tests; a parseable HTML file alone is not sufficient evidence.

Before retiring legacy modules, task #94 must demonstrate the complete capability matrix, compare matched workloads, exercise API/CLI/notebook migration, inspect installed wheel assets, and document intentional behavior changes. Acceptance of this architecture is not a claim that those gates have already passed.

## Primary sources

- [ECharts repository and Apache license](https://github.com/apache/echarts)
- [ECharts package metadata](https://github.com/apache/echarts/blob/master/package.json)
- [Official component imports and CanvasRenderer](https://echarts.apache.org/handbook/en/basics/import/)
- [Official SVG SSR and its runtime model](https://echarts.apache.org/handbook/en/how-to/cross-platform/server/)
- [Lightweight Charts license and attribution](https://tradingview.github.io/lightweight-charts/docs)
- [Lightweight Charts panes](https://tradingview.github.io/lightweight-charts/tutorials/how_to/panes)
- [uPlot license, features, and explicit panning non-goal](https://github.com/leeoniya/uPlot)
