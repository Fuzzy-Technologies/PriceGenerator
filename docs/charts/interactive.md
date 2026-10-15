# Offline interactive charts

`pricegenerator.rendering.interactive` renders a validated `ChartSpec` as a
self-contained HTML document. Python uses only its standard library. Node,
network access, Bokeh, Google Charts, Jinja2, pandas, and NumPy are unnecessary
for this API. The historical `PriceGenerator` facade is a separate migration
surface; its old methods are not changed by this renderer.

```python
"""Write an offline financial chart from explicit, validated market data."""

from pricegenerator.rendering.spec import ChartCandle, ChartSeries, ChartSpec
from pricegenerator.rendering.interactive import SaveInteractive

chart = ChartSpec(
    candles=(
        ChartCandle("2026-10-01T00:00:00Z", 100, 104, 98, 103, 1200),
        ChartCandle("2026-10-01T01:00:00Z", 103, 106, 101, 102, 900),
        ChartCandle("2026-10-01T03:00:00Z", 102, 108, 100, 107, 1500),
    ),
    title="Synthetic market · Fuzzy Technologies",
    series=(ChartSeries("mean", "Moving average", (None, 102.5, 104.5), group="Trend"),),
    summary=("Three synthetic candles; not a market forecast.",),
)
SaveInteractive(chart, "chart.html")
```

`RenderInteractive(chart)` returns the complete HTML string without writing a
file. `SaveInteractive(chart, path)` writes UTF-8 and returns a `Path`; it does
not open a browser or create missing parent directories. Identical snapshots
produce identical document bytes.

## Interaction and data semantics

| Capability | Behavior |
| --- | --- |
| OHLC and volume | Two synchronized panels; candle order is explicitly encoded as open, close, low, high for ECharts. |
| Time axis | UTC elapsed time, including gaps. Both panels share the same domain and zoom range. No implicit session compression. |
| Hover | Linked crosshair and plain-text Canvas tooltip with original OHLCV and visible aligned overlays. |
| Navigation | Wheel zoom, drag pan, overview slider, box zoom, previous-zoom toolbox icon, Reset view, Full range. |
| Overlays | Aligned line or point series, explicit `None` gaps, color/width/dash settings, independent initial visibility. |
| Groups | Named group buttons toggle related overlays; legend entries toggle individual series without label collisions. |
| Bands | Upper/middle/lower lines preserve historical Bokeh Bollinger-band behavior. A filled-band primitive is not part of schema 1. |
| Markers | Text anchored above, below, or at the candle-body midpoint. Arbitrary user strings remain text. |
| Statistics | `ChartSpec.summary` appears as an HTML text block. This renderer does not calculate indicators or statistics. |
| Image export | PNG at 2× pixel density, containing the current viewport, selected series, official header logo, and both panels' watermarks. The separate HTML summary/control block is not part of the PNG. |
| Responsive layout | ResizeObserver updates panels and graphics while preserving zoom and legend state; window resize is the fallback. |
| Motion | No continuous animation or price transitions. Reduced-motion CSS is explicit. |

Charts with at most 5,000 candles initially show their complete range. Larger
snapshots initially show the latest 1,000 candles. All original rows remain in
the document and the ECharts model; **Full range** shows them all. **Reset view**
restores the original viewport and visibility settings. This is a documented
renderer policy, not downsampling or a claim that 100,000 candles are all
readable at once. Schema 1 has no caller-configurable viewport field.

The adapter disables progressive drawing as well as animation so an enabled
export contains a complete synchronous frame. Branding images decode before
the chart reports ready. Selecting the full range of a very large dataset
requires more work; browser frame rates are not established by headless tests.

The schema rejects malformed/non-finite OHLCV and misaligned overlay arrays.
Extreme finite numeric domains are normalized internally before ECharts
computes ranges; axes, crosshairs, and tooltips format the original units.
Small nonzero values use scientific notation when decimal precision would
otherwise turn them into zero. This does not add precision beyond the
validated IEEE-754 input values.

## Theme, branding, and safety

Both dark and light corporate palettes come from the shared `theme.py`.
The default uses restrained cyan, violet, and magenta accents. The official
circular emblem appears in the header. Repeated wordmark silhouettes sit near
each panel's X axis at 16% opacity; their shape is derived from the exact
source image, tinted during rendering for readable contrast. PNG export uses
the same Canvas graphics, so branding is retained after zoom or resize.

The document embeds its runtime, source data, and image data URIs exactly
once. It loads no CDN scripts, remote images, fonts, or telemetry. Titles,
groups, summaries, markers, and labels are never interpolated into executable
JavaScript or raw HTML. `ChartSpec.ToJSON()` escapes script terminators;
tooltips use Canvas rich text and group buttons use `textContent`. Arbitrary
JavaScript callbacks or raw ECharts option dictionaries are not accepted.

The JavaScript bundle contains selected Apache ECharts 6.1.0 modules with its
Apache-2.0 license and NOTICE. Permissive transitive dependencies ZRender
(BSD-3-Clause) and tslib (0BSD) are disclosed and their full licenses are
embedded in every HTML export. See
[`THIRD_PARTY_NOTICES.md`](../../pricegenerator/rendering/assets/echarts/THIRD_PARTY_NOTICES.md).
The bundled runtime is 645,924 bytes uncompressed and 219,528 bytes gzip at
level 9. These are runtime-bundle sizes, not the total HTML size or an estimate
of render speed. HTML size also includes data and branding.

## Reproducible verification

```sh
python -m pytest -q tests/test_interactive_charts.py
npm ci --ignore-scripts --no-audit --no-fund --prefix tools/chart_runtime
node --test tests/javascript/test_interactive_charts.cjs tests/javascript/test_interactive_canvas.cjs
```

The first JavaScript suite executes the actual vendored ECharts model using a
deterministic drawing stub. It verifies OHLC ordering, exact time-gap ratios,
pixel alignment across panels after zoom, hidden overlays, group controls,
resize state, full-range/reset actions, 100,000-row retention, and extreme
finite geometry. It does not simulate physical mouse-wheel events or prove
browser FPS.

The second suite uses the separately locked test dependency
`@napi-rs/canvas==0.1.100` without conditional skips. It executes real image
decoding, chart creation, and immediate PNG export, and verifies differing
pixels in the emblem, header wordmark, and every watermark region. It also
mounts a 100,000-row snapshot and checks the initial 1,000-row visible window.
Native Canvas is test tooling; it is not shipped inside the Python runtime
or generated HTML. No browser is needed for either suite.

For a local raster preview of a generated document:

```sh
node tools/chart_runtime/render_preview.cjs \
  ./tools/chart_runtime/node_modules/@napi-rs/canvas chart.html preview.png
```

Rebuild the vendored runtime with `npm run build --prefix tools/chart_runtime`.
The checked-in lockfile pins official source integrities, and
`assets/echarts/build.json` records the output SHA-256 and byte sizes. Rebuilds
are a maintainer action; installation and normal Python rendering never run
Node.
