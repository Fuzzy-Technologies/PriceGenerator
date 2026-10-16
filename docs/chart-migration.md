# Modern chart and API migration

v2 intentionally replaces the mutable 1.x class and its chart commands. Use
explicit `GenerationConfig`, `Generate`, canonical CSV and the `Chart` adapter.
The old API is absent from the runtime; its behavior remains historical
[evidence](baseline/README.md). [ADR-0010](adr/0010-modern-only-public-api.md)
records this decision.

## Generate once, choose an output

```python
from pricegenerator import Chart, Generate, GenerationConfig

prices = Generate(GenerationConfig(seed=0, horizon=240))
html_path = Chart(prices, "prices.html", view=False)
svg_path = Chart(prices, "prices.svg", view=False)
```

HTML is the default: `Chart(prices)` saves an interactive HTML file to a temporary
path and asks the browser to open it. `Chart(prices, "prices.html")` saves to the
specified path and also opens it. In automation, explicitly use `view=False`.
The returned `Path` identifies the saved artifact. Static formats require an
explicit output path and default to no browser launch; `view=True` explicitly
requests opening their file URI.

The HTML embeds its reviewed ECharts runtime, data, logo and license notices;
SVG is standalone. Neither needs a CDN or Node at user runtime. Dark/light themes
use the same semantics. Each chart has exactly **one translucent corporate
wordmark in the price panel**; there is no watermark in the volume panel and no
repeated branding strip. The main corporate emblem is distinct from that wordmark.

## PNG/JPEG and explicit analysis

Install `python -m pip install '.[export]'` from the source checkout, or the
matching released package with its `export` extra, for Python raster output:

```python
png_path = Chart(prices, "prices.png", view=False)
jpeg_path = Chart(prices, "prices.jpeg", quality=90, view=False)
report_path = Chart(
    prices, "report.html", analysis=True, view=False,
    markdown_report="report.md", title="Synthetic scenario",
)
```

SVG/HTML work in a core installation. PNG uses resvg-py; JPEG additionally uses
Pillow and an opaque themed background. JPEG `quality` is an integer from 1 to 95.
The format can be explicit (`format="jpeg"`), but it must agree with the output
suffix. Missing export dependencies report how to install the extra. File output
and rendering failures propagate; a failed save never triggers browser viewing.

Analysis is opt-in. `analysis=True` adds modern statistical summaries and indicator
overlays from canonical data without modifying the source frame. A prepared
`ChartSpec` already owns its presentation data and cannot request automatic
analysis. HMA is unshifted and separate from Alligator; indicator warmup and
undefined values remain missing rather than being filled with fabricated prices.
Use `Analyze(prices)` and `Indicators(prices)` when results are needed separately.

## Notebook and command line

```python
from pricegenerator import DisplayChart

DisplayChart(prices)                       # Interactive HTML in an isolated iframe.
DisplayChart(prices, format="svg")         # Inline static SVG.
DisplayChart(prices, analysis=True)        # Explicit modern overlays and report.
```

Notebook display uses the host's IPython tools; install `.[notebook]` when needed.
It does not ask an external browser to open the chart. Host frontend policies may
still constrain JavaScript. Python code must use English comments/identifiers as
specified in the [style contract](../PYTHON_CODE_STYLE.md).

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv
pricegenerator chart prices.csv --output chart.html --no-view --analysis --report chart.md
pricegenerator chart prices.csv --output chart.svg --no-view
pricegenerator chart prices.csv --output chart.png --no-view
pricegenerator chart prices.csv --output chart.jpeg --quality 90 --no-view
```

The CLI also supports theme, title, dimensions, aligned external line/marker
inputs and plain-text summaries. `python -m pricegenerator chart --help` is the
current option reference. Explicit input/output paths, including hardlink aliases,
cannot overwrite each other. CSV input must use the strict six-column canonical
header and explicit timezone policy; no historical header guessing occurs.

Low-level adapters under `pricegenerator.rendering` remain available for validated
`ChartSpec`, SVG/HTML serialization, aligned overlays and explicit saves. Chart
adapters reject invalid OHLCV, misaligned series and unsafe specification fields.
See [the capability matrix](rendering-capabilities.md),
[interactive charts](charts/interactive.md) and [examples](examples/modern-market.md)
for the more detailed presentation contract.
