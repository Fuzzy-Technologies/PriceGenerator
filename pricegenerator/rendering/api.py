"""Provide explicit chart preparation, file output and optional viewing."""

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import webbrowser

from .spec import ChartSpec


def PrepareChart(data, *, analysis: bool = False, **options) -> ChartSpec:
    """Snapshot OHLCV data, optionally adding modern analytics and indicators."""

    if not isinstance(analysis, bool):
        raise TypeError("analysis must be a boolean")

    if isinstance(data, ChartSpec):
        if analysis:
            raise ValueError("analysis requires OHLCV data rather than a prepared ChartSpec")

        return replace(data, **options) if options else data

    from .adapters import FromDataFrame

    if analysis:
        from pricegenerator.analysis import Analyze
        from pricegenerator.market_data import ValidateOHLCV
        from .adapters import MarketOverlays

        data = ValidateOHLCV(data, assume_timezone=options.get("assume_timezone"))
        options["series"] = MarketOverlays(data) + tuple(options.get("series", ()))
        options["summary"] = Analyze(data).Summary() + tuple(options.get("summary", ()))

    return FromDataFrame(data, **options)


def _Format(output: Path | None, format: str | None) -> str:
    """Resolve a supported explicit format or an unambiguous filename suffix."""

    aliases = {"htm": "html", "html": "html", "svg": "svg", "png": "png", "jpg": "jpeg", "jpeg": "jpeg"}
    suffix = output.suffix.lower().lstrip(".") if output is not None else ""

    if format is not None and not isinstance(format, str):
        raise TypeError("format must be a string or None")

    selected = format.lower() if format is not None else suffix or "html"

    if selected not in aliases:
        raise ValueError("chart format must be html, svg, png or jpeg")

    selected = aliases[selected]

    if suffix and (suffix not in aliases or aliases[suffix] != selected):
        raise ValueError("output filename suffix must match the chart format")

    if output is None and selected != "html":
        raise ValueError("static charts require an explicit output path")

    return selected


def Chart(
    data, output: str | Path | None = None, *, format: str | None = None,
    view: bool | None = None, quality: int = 90, analysis: bool = False,
    markdown_report: str | Path | None = None, **options,
) -> Path:
    """Save HTML by default and open it; static formats need an explicit path.

    Set view=False for batch use. SVG uses only the standard library; PNG/JPEG
    require pricegenerator[export]. Analytics are opt-in for DataFrame input.
    """

    if view is not None and not isinstance(view, bool):
        raise TypeError("view must be a boolean or None")

    output_path = Path(output) if output is not None else None
    selected = _Format(output_path, format)
    spec = PrepareChart(data, analysis=analysis, **options)

    if markdown_report is not None and output_path is not None:
        report_path = Path(markdown_report)

        if report_path.resolve() == output_path.resolve() or (
            report_path.exists() and output_path.exists() and report_path.samefile(output_path)
        ):
            raise ValueError("chart and Markdown report output paths must differ")

    temporary = output_path is None

    if temporary:
        descriptor, filename = tempfile.mkstemp(prefix="pricegenerator-", suffix=".html")
        os.close(descriptor)
        output_path = Path(filename)

    try:
        if selected == "html":
            from .interactive import SaveInteractive

            SaveInteractive(spec, output_path)

        elif selected == "svg":
            from .static import SaveSVG

            SaveSVG(spec, output_path)

        elif selected == "png":
            from .exports import SavePNG

            SavePNG(spec, output_path)

        else:
            from .exports import SaveJPEG

            SaveJPEG(spec, output_path, quality=quality)

        if markdown_report is not None:
            from .adapters import SaveMarkdown

            SaveMarkdown(spec, markdown_report)

    except Exception:
        if temporary:
            output_path.unlink(missing_ok=True)

        raise

    should_view = view if view is not None else selected == "html"

    if should_view:
        if not webbrowser.open(output_path.resolve().as_uri()):
            raise RuntimeError(f"No browser accepted the chart; open {output_path.resolve()} manually")

    return output_path


def DisplayChart(data, *, format: str = "html", analysis: bool = False, **options):
    """Display an isolated interactive notebook chart by default, or inline SVG."""

    from .adapters import DisplayChart as DisplaySpec

    return DisplaySpec(PrepareChart(data, analysis=analysis, **options), format=format)
