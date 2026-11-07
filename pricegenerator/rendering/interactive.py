"""Generate self-contained, offline financial charts from validated snapshots."""

from functools import lru_cache
from html import escape
from importlib.resources import files
import json
import math
from pathlib import Path

from .spec import ChartSpec
from .theme import BrandingData, THEMES


_NOTICE_FILES = (
    "NOTICE.txt", "LICENSE-APACHE-2.0.txt", "LICENSE-ZRENDER-BSD-3.txt", "LICENSE-TSLIB-0BSD.txt",
)


@lru_cache(maxsize=1)
def _RuntimeAssets() -> tuple[str, str, str]:
    """Load only packaged resources, without optional Python or Node imports."""

    asset_root = files("pricegenerator.rendering").joinpath("assets")
    runtime = asset_root.joinpath("echarts", "echarts-financial.min.js").read_text(encoding="utf-8")
    adapter = asset_root.joinpath("interactive.js").read_text(encoding="utf-8")
    notices = "\n\n".join(asset_root.joinpath("echarts", name).read_text(encoding="utf-8") for name in _NOTICE_FILES)

    if "</script" in runtime.lower() or "</script" in adapter.lower():
        raise ValueError("packaged JavaScript contains an unsafe inline script terminator")

    return runtime, adapter, notices


def _JSON(value: object) -> str:
    """Serialize trusted configuration safely inside an inert script element."""

    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    return serialized.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _CheckPriceScale(spec: ChartSpec) -> None:
    """Reject mixed extreme scales which ECharts cannot display faithfully."""

    maximum = 0.0
    minimum = math.inf
    values = (value for candle in spec.candles for value in (candle.open, candle.high, candle.low, candle.close))
    overlays = (value for series in spec.series for value in series.values if value is not None)

    for collection in (values, overlays):
        for value in collection:
            magnitude = abs(value)
            maximum = max(maximum, magnitude)

            if magnitude > 0:
                minimum = min(minimum, magnitude)

    needs_scaling = maximum > 1e100 or 0 < maximum < 1e-100

    if needs_scaling and minimum / maximum < 1e-12:
        raise ValueError("Interactive charts cannot preserve this mixed numeric range; rescale prices/overlays or remove extreme outlier series")


def _Overview(spec: ChartSpec) -> str:
    """Present a few chart-wide figures independently of the technical report."""

    first, last = spec.candles[0].close, spec.candles[-1].close
    percent = (last / first - 1) * 100 if first > 0 else math.nan
    change = last - first

    if math.isfinite(percent):
        change_text = f"{percent:+.2f}%" if abs(percent) < 1e6 else f"{percent:+.3g}%"

    else:
        change_text = f"{change:+.6g}" if math.isfinite(change) else "—"

    return f'''<section class="overview" aria-label="Chart overview">
<dl class="metrics">
<div><dt>Candles</dt><dd>{len(spec.candles):,}</dd></div>
<div><dt>First close</dt><dd>{first:.6g}</dd></div>
<div><dt>Last close</dt><dd>{last:.6g}</dd></div>
<div title="Change from the first close to the last close. Percentages use a positive starting price.">
<dt>Close change</dt><dd>{change_text}</dd></div>
</dl>
</section>'''


def RenderInteractive(spec: ChartSpec) -> str:
    """Return complete offline HTML without opening a browser or writing files."""

    if not isinstance(spec, ChartSpec):
        raise TypeError("spec must be a validated ChartSpec")

    _CheckPriceScale(spec)
    runtime, adapter, notices = _RuntimeAssets()
    themes = {name: dict(colors) for name, colors in THEMES.items()}
    palette_rules = "\n".join(
        f':root[data-theme="{name}"] {{color-scheme:{name};'
        + "".join(f"--{key}:{value};" for key, value in colors.items()) + "}"
        for name, colors in themes.items()
    )
    title = escape(spec.title)
    summary = "".join(f"<li>{escape(line)}</li>" for line in spec.summary)
    controls_hidden = "" if spec.show_controls else " hidden"
    indicators_hidden = "" if any(series.group is not None for series in spec.series) else " hidden"
    theme_label = "Light theme" if spec.theme == "dark" else "Dark theme"
    report = ""

    if summary:
        report = f'''{_Overview(spec)}
<details class="report" aria-label="Detailed statistics">
<summary>Detailed statistics</summary>
<p class="hint">Advanced diagnostics for the full series.</p>
<ul>{summary}</ul>
</details>'''

    return f'''<!doctype html>
<html lang="en" data-theme="{spec.theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="{spec.theme}">
<title>{title}</title>
<style>
:root {{font-family:system-ui,sans-serif;background:var(--background);color:var(--text)}}
{palette_rules}
* {{box-sizing:border-box}}
body {{margin:0;padding:20px}}
main {{max-width:{spec.width}px;margin:0 auto}}
.sr-only {{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)}}
#chart {{width:100%;height:{spec.height}px;border:1px solid var(--grid);border-radius:12px;overflow:hidden}}
.controls {{margin-bottom:12px}}
.control-row {{display:flex;flex-wrap:wrap;align-items:center;gap:6px}}
.indicator-controls {{margin-top:10px}}
.indicator-label {{margin:0 0 6px;color:var(--muted);font-size:.82rem;line-height:1.4}}
.indicator-label strong {{color:var(--text);margin-right:6px}}
button {{max-width:100%;overflow-wrap:anywhere;border:1px solid var(--grid);border-radius:7px;padding:6px 10px;
  background:var(--panel);color:var(--text);cursor:pointer;font:inherit;font-size:.86rem;line-height:1.35}}
button:hover {{border-color:var(--accent)}}
button:focus-visible,summary:focus-visible {{outline:2px solid var(--accent);outline-offset:2px}}
button[aria-pressed="true"] {{border-color:var(--secondary);box-shadow:inset 0 -2px var(--secondary)}}
.hint,footer {{margin:8px 0;color:var(--muted);font-size:.82rem;line-height:1.5}}
summary {{width:fit-content;max-width:100%;cursor:pointer;font-size:.86rem;font-weight:600}}
.series-list {{margin-top:8px;color:var(--muted)}}
.series-list .control-row {{margin-top:8px}}
.overview,.report {{margin:10px 0;padding:10px 12px;border:1px solid var(--grid);
  border-radius:8px;background:var(--panel)}}
.metrics {{display:flex;flex-wrap:wrap;gap:10px 30px;margin:0}}
.metrics dt {{font-size:.8rem;color:var(--muted)}}
.metrics dd {{margin:2px 0 0;font-size:.97rem;font-weight:600;font-variant-numeric:tabular-nums}}
.report ul {{margin:6px 0 0;padding-left:20px;line-height:1.55;font-size:.87rem;overflow-wrap:anywhere}}
@media(max-width:600px) {{body {{padding:8px}} .metrics {{gap:8px 16px}}}}
@media(prefers-reduced-motion:reduce) {{* {{animation:none!important;transition:none!important}}}}
</style>
</head>
<body>
<main>
<h1 class="sr-only">{title}</h1>
<div id="controls" class="controls"{controls_hidden}>
<div class="control-row" role="group" aria-label="Chart navigation and display">
<button type="button" data-action="pan" title="Drag the chart to move along the time axis.">Pan</button>
<button type="button" data-action="box" title="Drag a rectangle to zoom in on a time range." aria-pressed="false">Box zoom</button>
<button type="button" data-action="previous" title="Return to the previous time range.">Previous zoom</button>
<button type="button" data-action="reset" title="Restore the starting range and indicator selection.">Reset view</button>
<button type="button" data-action="full" title="Show all candles in this series.">Full range</button>
<button type="button" data-action="export" title="Save the current price and volume view as an image.">Export PNG</button>
<button type="button" data-action="theme" title="Switch the chart and controls between dark and light.">{theme_label}</button>
</div>
<div class="indicator-controls" data-indicators{indicators_hidden}>
<p class="indicator-label"><strong>Indicators</strong> Choose a group to show or hide its overlays.</p>
<div class="control-row" data-groups role="group" aria-label="Indicator groups"></div>
</div>
<details class="series-list">
<summary>Individual series</summary>
<div class="control-row" data-series role="group" aria-label="Individual series"></div>
</details>
</div>
<div id="chart" role="img" aria-label="Candlestick price and volume chart"></div>
<p id="status" class="hint" role="status" aria-live="polite">Loading local chart assets…</p>
{report}
<noscript>JavaScript is required for the interactive chart. Use the static SVG renderer for a script-free chart.</noscript>
<footer>PriceGenerator · Fuzzy Technologies · Offline chart</footer>
</main>
<template id="third-party-notices">{escape(notices)}</template>
<script id="chart-spec" type="application/json">{spec.ToJSON()}</script>
<script id="chart-theme" type="application/json">{_JSON(themes[spec.theme])}</script>
<script id="chart-themes" type="application/json">{_JSON(themes)}</script>
<script id="chart-branding" type="application/json">{_JSON(BrandingData())}</script>
<script>{runtime}</script>
<script>{adapter}</script>
<script>
"use strict";
const ReadJSON = (id) => JSON.parse(document.getElementById(id).textContent);
PriceGeneratorView.Mount(document.getElementById("chart"), ReadJSON("chart-spec"),
    ReadJSON("chart-theme"), ReadJSON("chart-branding"), document.getElementById("controls"),
    document.getElementById("status"), PriceGeneratorCharts, window, ReadJSON("chart-themes")).catch((error) => {{
        document.getElementById("status").textContent = "Chart could not start: " + error.message;
    }});
</script>
</body>
</html>
'''


def SaveInteractive(spec: ChartSpec, path: str | Path) -> Path:
    """Write an explicit UTF-8 HTML path and return it without browser actions."""

    output_path = Path(path)
    output_path.write_text(RenderInteractive(spec), encoding="utf-8")

    return output_path
