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


def RenderInteractive(spec: ChartSpec) -> str:
    """Return complete offline HTML without opening a browser or writing files."""

    if not isinstance(spec, ChartSpec):
        raise TypeError("spec must be a validated ChartSpec")

    _CheckPriceScale(spec)
    runtime, adapter, notices = _RuntimeAssets()
    theme = dict(THEMES[spec.theme])
    title = escape(spec.title)
    summary = "".join(f"<li>{escape(line)}</li>" for line in spec.summary)
    controls_hidden = "" if spec.show_controls else " hidden"
    summary_html = f'<section aria-label="Chart summary"><ul>{summary}</ul></section>' if summary else ""

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="{spec.theme}">
<title>{title}</title>
<style>
:root {{color-scheme:{spec.theme};font-family:system-ui,sans-serif;background:{theme["background"]};color:{theme["text"]}}}
* {{box-sizing:border-box}}
body {{margin:0;padding:20px}}
main {{max-width:{spec.width}px;margin:0 auto}}
h1 {{font-size:1.2rem}}
.sr-only {{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)}}
#chart {{width:100%;height:{spec.height}px;min-width:320px;border:1px solid {theme["grid"]};border-radius:16px;overflow:hidden}}
.controls {{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0}}
.controls[hidden] {{display:none}}
.groups {{display:contents}}
button {{border:1px solid {theme["grid"]};border-radius:8px;padding:8px 12px;background:{theme["panel"]};color:{theme["text"]};cursor:pointer;font:inherit}}
button:hover,button:focus-visible {{border-color:{theme["accent"]};outline:2px solid {theme["accent"]}55;outline-offset:2px}}
button[aria-pressed="true"] {{border-color:{theme["secondary"]};box-shadow:inset 0 -2px {theme["secondary"]}}}
.hint,footer {{color:{theme["muted"]};font-size:.82rem;line-height:1.6}}
section {{border-left:2px solid {theme["accent"]};padding:4px 12px;margin:16px 0;background:{theme["panel"]}}}
section ul {{padding-left:16px;line-height:1.65;overflow-wrap:anywhere}}
pre {{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.75rem}}
@media(max-width:600px) {{body {{padding:8px}} button {{padding:7px 9px;font-size:.85rem}}}}
@media(prefers-reduced-motion:reduce) {{* {{animation:none!important;transition:none!important}}}}
</style>
</head>
<body>
<main>
<h1 class="sr-only">{title}</h1>
<div id="chart" role="img" aria-label="OHLC and volume chart. Interactive controls follow."></div>
<div id="controls" class="controls"{controls_hidden}>
<button type="button" data-action="pan">Pan</button>
<button type="button" data-action="box" aria-pressed="false">Box zoom</button>
<button type="button" data-action="reset">Reset view</button>
<button type="button" data-action="full">Full range</button>
<button type="button" data-action="export">Export PNG</button>
<span data-groups class="groups"></span>
</div>
<p id="status" class="hint" role="status" aria-live="polite">Loading local chart assets…</p>
{summary_html}
<noscript>JavaScript is required for the interactive chart. Use the static SVG renderer for a script-free chart.</noscript>
<footer>PriceGenerator · Fuzzy Technologies · Offline chart
<details><summary>Open-source licenses and notices</summary><pre>{escape(notices)}</pre></details>
</footer>
</main>
<script id="chart-spec" type="application/json">{spec.ToJSON()}</script>
<script id="chart-theme" type="application/json">{_JSON(theme)}</script>
<script id="chart-branding" type="application/json">{_JSON(BrandingData())}</script>
<script>{runtime}</script>
<script>{adapter}</script>
<script>
"use strict";
const ReadJSON = (id) => JSON.parse(document.getElementById(id).textContent);
PriceGeneratorView.Mount(document.getElementById("chart"), ReadJSON("chart-spec"),
    ReadJSON("chart-theme"), ReadJSON("chart-branding"), document.getElementById("controls"),
    document.getElementById("status"), PriceGeneratorCharts, window).catch((error) => {{
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
