# Chart rendering contract and migration evidence

The historical audit below characterizes the 1.x implementation at `a97e848`;
its source and tests are archival evidence for [Feature #90](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/90),
not available runtime APIs. Current behavior follows
[ADR-0010](adr/0010-modern-only-public-api.md), which supersedes the compatibility,
branding and export limits in [ADR-0009](adr/0009-modern-chart-rendering.md).
Use `Chart(data)` and `DisplayChart(data)` as the public entry points;
[the migration guide](chart-migration.md) documents defaults and command syntax.

## Historical capabilities

| Capability | Actual 1.x behavior | Modern replacement |
| --- | --- | --- |
| Static output | Google method writes JavaScript-dependent HTML with online loaders; no native SVG/PNG API | Offline SVG, optional native PNG/JPEG, and standalone interactive HTML |
| Candlesticks | OHLC wick/body; direction colors; doji uses rising style | Preserve OHLC geometry and readable direction at the configured precision |
| Volume | Bokeh lower panel, matching direction colors and shared datetime range | Linked volume panel; zero volumes and a single candle are valid |
| Time axis | Bokeh uses elapsed datetime; Google uses category strings | Explicit UTC timestamps; preserve gaps on the default time axis |
| Hover | Candle index, date, time, OHLC, volume; volume hover separately | Interactive cursor/report exposes original values, including after display scaling |
| Navigation | Pan, wheel zoom, box zoom, reset, toolbar save | Functional equivalents with synchronized price/volume ranges |
| Controls | Grouped legend click-to-hide; independent `showControlsOnChart` | Explicit group visibility; optional controls without losing supplied series |
| Close limits/trends | Max/min close with labels; full-horizon and split-segment trends | Aligned close-limit and elapsed-time trend overlays; calculations are explicit and renderers consume supplied values |
| Average | High/low midpoint line and points, hidden by default | Aligned line and point overlays; documented default visibility |
| SMA | 5/20 and 50/200 groups, hidden by default | All four results available through the analysis adapter |
| HMA | 5/20 group, hidden by default | Both unshifted HMA results, independent of Alligator |
| VWMA | 5/20 group, hidden by default | Both results, including explicit zero-volume behavior |
| Bollinger | Lower/mid/upper **lines**; no area shading in legacy code | Three aligned lines with gaps and group controls; filled bands are an optional later addition |
| PSAR | Long/short point series, hidden by default | Separate point overlays, gaps and visibility preserved |
| Alligator | Shifted HMA13/8/5 at offsets 8/5/3, not a standard SMMA implementation | Deliberately replaced by median-price SMMA at periods13/8/5 and shifts8/5/3; documented in the indicator migration |
| Zig-Zag | Percentage filter produces sparse connected time/value points | Analysis adapter supplies the sparse line with a deliberate interpolation/alignment policy |
| Custom markers | Arbitrary text above high, at midpoint, below low; old fixed ±0.5 offsets | Plain text in all three relative positions with stable screen spacing |
| Custom lines | Named user DataFrame series over time | Validated named aligned line/point overlays; input data is not mutated |
| Statistics | Candle count/timeframe/precision; first/last/min/max close; close range/trend; up/down counts/percentages and longest runs; range extrema/std/99/95/80 percentiles; total volume | Explicit analysis report, displayed and exportable as Markdown |
| Title/size/theme | Custom or generated title, width/height, dark/light Bokeh option | Dark default, light option, bounded dimensions, readable narrow reports |
| Notebook | Bokeh inline resources and display handle | Explicit HTML/SVG display adapter, covered during task #94 |
| Template customization | Google accepts arbitrary Jinja template/model, path or string | Replace with documented data/presentation options or trusted outer HTML composition; raw templates are not part of ChartSpec |
| Side effects | Rendering can mutate DataFrame, run indicators, open paths through `os.system`, and swallow some save errors | Pure low-level renderers; Chart explicitly writes/views HTML by default, view=False suppresses UI; analysis is opt-in and I/O errors propagate |

The old tests mostly checked that HTML and Markdown files existed. They did not establish visual correctness, safe escaping, interaction behavior, or offline operation. The current tests add evidence for those properties.

`GetStatistics` first computes unshifted HMA5 and later overwrites it with the Alligator lips result shifted by three candles. Both the HMA and Alligator chart groups then read the shifted column. v2 deliberately removes that overwrite and the historical calculation mode. HMA is always unshifted, while Alligator uses its separate SMMA implementation; see [the exact formula mapping](indicator-migration.md).

## Shared specification

Import from `pricegenerator.rendering` or `pricegenerator.rendering.spec`. All dataclasses are frozen and snapshot caller sequences as tuples.

| Type | Fields |
| --- | --- |
| `ChartCandle` | `datetime`, `open`, `high`, `low`, `close`, `volume` |
| `ChartSeries` | `key`, `label`, `values`, `color=None`, `kind="line"`, `visible=True`, `group=None`, `width=1.8`, `dashed=False` |
| `ChartMarker` | `candle_index`, `text`, `position="above"`, `color=None` |
| `ChartSpec` | `candles`, `title="PriceGenerator"`, `series=()`, `markers=()`, `summary=()`, `theme="dark"`, `width=1280`, `height=760`, `price_precision=2`, `show_controls=True` |

`ChartSpec.ToDict()` and `ToJSON()` include `schema_version=1`. `FromDict()` restores the same validated contract and rejects unknown fields/versions. JSON serialization escapes script delimiters without changing the text after decoding.

Timestamp strings require an explicit offset and normalize to UTC with millisecond precision. Precision finer than milliseconds is rejected instead of silently collapsing distinct timestamps in JavaScript. Timestamps are strictly increasing and unique. Candles must satisfy finite OHLC, low ≤ open/close ≤ high, and nonnegative finite volume. No realistic-price or positive-price claim is inferred.

Every series has one number or `None` per candle. `None` creates a gap; renderers do not invent interpolation. Kinds are `line` and `points`. For a trend or sparse Zig-Zag polyline, the analysis adapter explicitly supplies interpolated values if continuity is intended. Keys are stable identifiers; colors are six-digit hex values. Markers refer to valid candle indices and positions `above`, `center`, or `below`.

## Static API

```python
from pricegenerator import Chart
from pricegenerator.rendering import ChartCandle, ChartSeries, ChartSpec

chart = ChartSpec(
    candles=(
        ChartCandle("2026-10-15T00:00:00Z", 10, 12, 9, 11, 100),
        ChartCandle("2026-10-15T01:00:00Z", 11, 13, 10, 12, 120),
    ),
    title="Synthetic scenario",
    series=(ChartSeries("reference", "Reference", (11, 11), dashed=True),),
    summary=("Illustrative data; no realism claim.",),
)
Chart(chart, "scenario.svg", view=False)
```

`RenderSVG(spec)` returns the same standalone string that `SaveSVG(spec, path)` writes. SVG includes visible overlays only; hidden interactive overlays cannot be toggled in a static image. The requested height is the chart region: long titles, overlay labels, and report lines extend the exported canvas to avoid clipping. Marker labels display at most three wrapped lines with an ellipsis; each retains its complete original text in an SVG title. Supplied report/indicator data is displayed, not computed. Native PNG/JPEG exports rasterize the same SVG, including its full report.
Install `pricegenerator[export]` for resvg-py/Pillow; SVG and HTML require no
raster dependencies. `RenderPNG`/`RenderJPEG` return bytes, and
`SavePNG`/`SaveJPEG` write explicit paths. JPEG uses an opaque themed RGB
background and integer quality from 1 through 95. PDF is not a supported format.

Both supplied corporate images are embedded once per SVG. One definition is referenced exactly once for the translucent wordmark at the lower left inside the price panel, at 28% opacity. The volume panel has no watermark and there is no repeated strip. A tint filter uses the theme text color without replacing the supplied silhouette. The main emblem is clipped to its original circular design. No font, image, or script needs a network request. Glyphs retain a minimum 0.75-pixel width when intervals become subpixel, while their true timestamp positions remain unchanged; this is a display-density policy, not time compression.

## Asset provenance

The user supplied both source images during the 2026-10-15 UTC session. Original files are not regenerated. The emblem's source filename says `2048`, but its actual dimensions are 1254×1254.

| Asset | Actual dimensions | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `FuzzyTechnologies-Logo-transp.png` (unchanged runtime wordmark) | 1000×180 | 3,708 | `d359c5ec7a949f6133508aab59dac97dfea77872ed43b6c6df3c4a10def46103` |
| `rendering-assets/source/FTech-corporate-mark-circular-dark-2048.png` (source) | 1254×1254 | 2,255,851 | `6175ff9bd7649f7a1e8e8766149b3b09e1553f2e4b7a83506c61c92329b4a08f` |
| `ftech-emblem-192.png` (runtime derivative) | 192×192 | 54,223 | `b0f03918847db13a6b7d3cdcd53b739362478f370a2f795a93b2996ab7720a28` |

The derivative was produced using Pillow 12.3.0, `image.resize((192, 192), Image.Resampling.LANCZOS).save(path, format="PNG", optimize=True)`. No crop, recolor, synthetic detail, or design change was made. SVG/HTML load the packaged assets without Pillow. Pillow is also used at runtime by the optional JPEG export. Runtime package data consists of the two files under `pricegenerator/rendering/assets/branding/`; the large original stays in documentation sources.

## Historical candidate bundle measurements

The ADR byte counts used Node.js 24.19.0, npm 11.9.0, esbuild 0.25.12, and gzip level 9. Install exact versions in a temporary directory with lifecycle scripts disabled:

```bash
npm install --ignore-scripts --no-audit --no-fund --save-exact echarts@6.1.0 lightweight-charts@5.2.1 uplot@1.6.32 esbuild@0.25.12
```

Build the following entry as a minified IIFE with esbuild (`--bundle --minify --format=iife --global-name=PriceGeneratorCharts`). This is a comparison profile; the production adapter must report its actual final bundle independently.

```javascript
import * as echarts from 'echarts/core';
import { CandlestickChart, BarChart, LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent,
  ToolboxComponent, GraphicComponent, MarkLineComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
echarts.use([CandlestickChart, BarChart, LineChart, ScatterChart, GridComponent,
  TooltipComponent, LegendComponent, DataZoomComponent, ToolboxComponent,
  GraphicComponent, MarkLineComponent, TitleComponent, CanvasRenderer]);
export const init = echarts.init;
```

Measure each file's bytes and `gzipSync(bytes, {level: 9})` length. The official comparison files are `echarts/dist/echarts.min.js`, `lightweight-charts/dist/lightweight-charts.standalone.production.js`, and `uplot/dist/uPlot.iife.min.js`. Their SHA-256 values, in that order, are:

```text
b66b25aeb4df84e33199dc21694014d336d222cbd9deb0e5a7c14bd6aa0d0fd0
e21cc5caa0226ef30bd8549c50b9ef926615f2a4ee6b4e486353477a55f598cf
19c8d4c6ad88929a79f4ae49d6f7161566dfd0ba3d15cc495e974f787eb78f1f
```

The custom comparison bundle SHA-256 is `9fa1dd7561b5d086a07281ba9a8faa95c7932c3572529ef4338beda96f544676`.

## Historical replacement plan

| Task | Deliverable and gate |
| --- | --- |
| [#91](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/91) | Source-based parity audit, license/size comparison, ADR and bounded architecture |
| [#92](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/92) | Immutable validated specification; offline branded SVG; finite/flat/gapped data, text safety, package resources and no-heavy-import tests |
| [#93](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/93) | Pinned minimal ECharts runtime; linked financial views; tested controls, arbitrary annotations, offline HTML, PNG export, licenses and final bundle footprint |
| [#94](https://github.com/Fuzzy-Technologies/PriceGenerator/issues/94) | Indicator/report adapter, CLI/notebook/migration docs, matching workload benchmark and evidence for every retained capability before legacy retirement |

## Integrated replacement evidence

The [migration guide](chart-migration.md) maps each historical indicator and
public workflow to its explicit replacement. The implementation evidence is:

| Contract | Executable evidence |
| --- | --- |
| Immutable snapshots, UTC precision, invalid input and safe JSON | `tests/test_chart_spec.py` |
| Exact candle geometry, gaps, static labels, reports and one price-panel wordmark | `tests/test_static_charts.py` and the reproducible SVG examples |
| Offline HTML, embedded assets, escaping and propagated output failures | `tests/test_interactive_charts.py` |
| Actual linked axes, visibility, navigation, reset and uneven time intervals | `tests/javascript/test_interactive_charts.cjs` |
| Actual PNG pixels, complete initial frame, bounded annotations and logos | `tests/javascript/test_interactive_canvas.cjs` |
| Modern hand-reference formulas, undefined reasons, reports, custom data and notebook | `tests/test_analysis.py`, `tests/test_indicators.py`, `tests/test_chart_migration.py` |
| Unified output/view defaults, native PNG/JPEG decoding and logo pixels | `tests/test_chart_api.py`, `tests/test_chart_exports.py` |
| Wheel/sdist resources and installed core-only API/CLI operation | `tests/test_packaging.py`, run outside the checkout with Python isolated mode |
| Current modern 1k export/Canvas evidence and archived larger comparisons | [Performance commands, scopes and recorded results](chart-performance.md) |

The historical `RenderGoogle`, `RenderBokeh`, mutable generator class, template
hooks and old CLI flags are absent from the v2 runtime. Trusted outer-report
composition replaces arbitrary Jinja template execution. Analytics use the
modern NumPy/pandas implementation without TA-backend fallbacks or an HMA5
compatibility switch.

SVG, native Python PNG/JPEG, full HTML and Markdown retain the supplied report.
The interactive **Export PNG** action contains the current chart viewport,
visible overlays, header emblem and exactly one lower-left price-panel
wordmark, excluding the separate HTML report and controls. Both paths keep
volume free of watermarks. This is an explicit export-scope distinction.

Interactive snapshots above 5,000 rows initially display the latest 1,000 while
retaining every source row; Full range explicitly displays all data. When an
extreme numeric domain needs normalization (maximum magnitude above `1e100` or
nonzero maximum below `1e-100`), mixed nonzero price/overlay scales spanning more
than 12 orders are rejected with an actionable error instead of
silently losing visible data. This renderer-specific limit includes hidden
outlier overlays and does not restrict static SVG's shared specification.

The maintained Python code is linted in the supported-runtime matrix. A separate
mandatory Canvas workflow rebuilds the pinned runtime and executes real engine
and raster tests. The performance observations do not claim browser FPS or
universal superiority for every workload.

The static implementation is covered by targeted specification/SVG tests, including immutable snapshots, UTC duplicates, invalid candles, gaps, script delimiters, logo reuse, I/O failures, and extreme finite price ranges. Local SVG visual inspection covers 1280×760 and 480×360 chart regions with two overlays, three marker positions, and report text. This is static-layout evidence, not a browser interaction test.

Current and archived timing observations, their exact workloads and source
identities are retained in [chart performance](chart-performance.md). They are
not browser FPS measurements or performance thresholds.
