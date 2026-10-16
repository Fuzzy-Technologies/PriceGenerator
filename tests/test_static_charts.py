"""Verify portable SVG geometry, annotations, branding, and data integrity."""

from dataclasses import replace
import re
import xml.etree.ElementTree as ET

import pytest

from pricegenerator.rendering import ChartCandle, ChartMarker, ChartSeries, ChartSpec, RenderSVG, SaveSVG
from pricegenerator.rendering.theme import BrandingData


SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def Spec() -> ChartSpec:
    """Build a chart with contrasting directions, zero volume, gaps, and markers."""

    candles = (
        ChartCandle("2026-10-15T00:00:00Z", 10, 12, 8, 11, 100),
        ChartCandle("2026-10-15T00:01:00Z", 11, 13, 9, 10, 0),
        ChartCandle("2026-10-15T00:02:00Z", 10, 11, 9, 10, 50),
    )

    return ChartSpec(candles, title="Research <OHLCV> & evidence", series=(
        ChartSeries("trend", "Visible trend", (10, None, 11), dashed=True),
        ChartSeries("psar", "PSAR", (12, 13, None), kind="points"),
        ChartSeries("hidden", "Hidden overlay", (1000, 1000, 1000), visible=False),
    ), markers=(
        ChartMarker(0, "↑ <buy>", "above"), ChartMarker(1, "× & hold", "center"),
        ChartMarker(2, "↓ sell", "below"),
    ), summary=("Summary & assumptions", "3 candles; no realism claim"))


def test_SvgPreservesDataAndVisibleFeatures() -> None:
    """SVG structure captures candles, volume, all marker positions, and gaps."""

    spec = Spec()
    rendered = RenderSVG(spec)
    root = ET.fromstring(rendered)

    assert len(root.findall('.//svg:g[@data-candle-index]', SVG_NS)) == 3, "SVG lost candle bodies or wicks"
    assert len(root.findall('.//svg:rect[@data-volume-index]', SVG_NS)) == 3, "SVG lost the synchronized volume panel"
    assert len(root.findall('.//svg:text[@data-marker]', SVG_NS)) == 3, "SVG lost custom text markers"
    assert len(root.findall('.//svg:g[@data-series="psar"]/svg:circle', SVG_NS)) == 2, "Point overlays lost nonmissing values"
    assert root.find('.//svg:g[@data-series="hidden"]', SVG_NS) is None, "Hidden overlay leaked into static output"
    path = root.find('.//svg:g[@data-series="trend"]/svg:path', SVG_NS)
    assert path is not None and path.attrib["d"].count("M") == 2 and "L" not in path.attrib["d"], "Missing overlay values were connected across a gap"
    assert root.find("svg:title", SVG_NS).text == spec.title, "Title escaping changed the plain text"
    assert '<buy>' not in rendered and '&lt;buy&gt;' in rendered, "Marker text was interpreted as SVG markup"
    assert RenderSVG(spec) == rendered, "Identical input changed serialized output"


def test_BrandingContainsOnePricePanelWordmark() -> None:
    """One translucent wordmark is anchored at the price panel lower left."""

    rendered = RenderSVG(Spec())
    root = ET.fromstring(rendered)
    branding = BrandingData()

    assert rendered.count(branding["wordmark"]) == 1, "Repeated wordmarks duplicate image bytes"
    assert rendered.count(branding["emblem"]) == 1, "The main emblem duplicates image bytes"
    assert len(root.findall('.//svg:use', SVG_NS)) == 2, "Chart must contain one emblem and one wordmark"
    assert {group.attrib["data-watermark-panel"] for group in root.findall('.//svg:g[@data-watermark-panel]', SVG_NS)} == {"price"}, "Only the main price panel may carry the wordmark"
    assert len(rendered.encode("utf-8")) < 100_000, "A three-candle SVG exceeded the fixture size budget"
    assert not re.search(r'(?:href|src)="https?://', rendered), "Offline SVG contains an external asset dependency"


@pytest.mark.parametrize("price,volume", [(0.0, 0.0), (1e308, 1e308), (-1e308, 1.0), (1e-300, 0.0)])
def test_FlatAndExtremeSeriesProduceFiniteGeometry(price: float, volume: float) -> None:
    """Flat prices and large finite numbers do not divide by zero or overflow."""

    candle = ChartCandle("2026-10-15T00:00:00Z", price, price, price, price, volume)
    root = ET.fromstring(RenderSVG(ChartSpec((candle,))))

    for element in root.iter():
        for name, value in element.attrib.items():
            if name in {"x", "y", "width", "height", "cx", "cy", "r", "d"}:
                assert not re.search(r"(?:nan|inf)", value, re.IGNORECASE), f"Nonfinite SVG geometry in {name}={value}"


def test_LongTitleAndReportStayInsideExportCanvas() -> None:
    """Long research descriptions extend the report without clipping geometry."""

    spec = replace(Spec(), title="Long research title " * 40, width=480, height=360, summary=("Detailed explanation " * 80,))
    root = ET.fromstring(RenderSVG(spec))
    height = float(root.attrib["height"])

    for element in root.findall('.//svg:rect', SVG_NS):
        if element.attrib.get("height", "").endswith("%"):
            continue

        assert float(element.attrib["height"]) >= 0, "Long title inverted a chart panel"

    for element in root.findall('.//svg:text', SVG_NS):
        assert float(element.attrib["y"]) < height, "Text fell outside the exported canvas"


def test_MixedExtremePriceRangeStaysFinite() -> None:
    """A finite range spanning both float signs must not overflow its scale."""

    candle = ChartCandle("2026-10-15T00:00:00Z", 0, 1e308, -1e308, 1, 0)
    rendered = RenderSVG(ChartSpec((candle,)))

    assert not re.search(r'(?:x|y|d|height|width)="[^"]*(?:inf|nan)', rendered, re.IGNORECASE), "Mixed-sign finite prices overflowed SVG geometry"


def test_CandleMetadataPreservesOriginalNumericPrecision() -> None:
    """Static tooltip metadata must not truncate source prices to six digits."""

    candle = ChartCandle("2026-10-15T00:00:00Z", 1.123456789, 1.2, 1.1, 1.123456790, 0)
    root = ET.fromstring(RenderSVG(ChartSpec((candle,), price_precision=9)))
    title = root.find('.//svg:g[@data-candle-index]/svg:title', SVG_NS)

    assert f"O={candle.open}" in title.text and f"C={candle.close}" in title.text, "Candle metadata changed the source numeric values"


def test_TimeGapsUseElapsedTimeInsteadOfCategorySpacing() -> None:
    """Missing periods retain their duration on the true datetime axis."""

    first = Spec().candles[0]
    spec = ChartSpec((first, replace(first, datetime="2026-10-15T00:01:00Z"), replace(first, datetime="2026-10-15T00:04:00Z")))
    root = ET.fromstring(RenderSVG(spec))
    bodies = root.findall('.//svg:g[@data-candle-index]/svg:rect', SVG_NS)
    positions = [float(body.attrib["x"]) for body in bodies]

    assert positions[2] - positions[1] == pytest.approx(3 * (positions[1] - positions[0]), abs=0.003), "Datetime gaps were compressed into equal category slots"


def test_EdgeAnnotationsAndLegendRemainReadable() -> None:
    """Long annotations at either endpoint fit, and legend swatches identify series."""

    spec = replace(Spec(), markers=(ChartMarker(0, "Leading marker annotation " * 3), ChartMarker(2, "Trailing marker annotation " * 3)))
    root = ET.fromstring(RenderSVG(spec))
    markers = root.findall('.//svg:text[@data-marker]', SVG_NS)
    assert markers[0].attrib["text-anchor"] == "start", "Leading annotation can extend outside the canvas"
    assert markers[-1].attrib["text-anchor"] == "end", "Trailing annotation can extend outside the canvas"
    legend_paths = [element for element in root.findall('.//svg:path', SVG_NS) if element.attrib.get("d", "").startswith("M 28 ")]
    assert legend_paths and legend_paths[0].attrib.get("stroke-dasharray") == "5 4", "Legend lost the visible line's style"
    assert legend_paths[0].attrib["stroke"] == root.find('.//svg:g[@data-series="trend"]', SVG_NS).attrib["stroke"], "Legend color differs from its plotted series"


def test_SubpixelIntervalsRemainVisibleAndDistantDatesStayAligned() -> None:
    """Tiny intervals retain glyphs, and relative millisecond precision is stable."""

    candle = Spec().candles[0]
    sparse = ChartSpec((
        candle, replace(candle, datetime="2026-10-15T00:00:00.001Z"),
        replace(candle, datetime="2026-10-16T00:00:00Z"),
    ))
    root = ET.fromstring(RenderSVG(sparse))
    bodies = root.findall('.//svg:g[@data-candle-index]/svg:rect', SVG_NS)
    assert all(float(body.attrib["width"]) >= 0.75 for body in bodies), "Subpixel intervals made candle bodies disappear"
    assert all(float(body.attrib["width"]) >= 0.75 for body in root.findall('.//svg:rect[@data-volume-index]', SVG_NS)), "Subpixel intervals made volume bars disappear"
    distant = ChartSpec(tuple(replace(candle, datetime=f"9999-12-31T23:59:59.{millisecond}Z") for millisecond in (997, 998, 999)))
    root = ET.fromstring(RenderSVG(distant))
    positions = [float(body.attrib["x"]) for body in root.findall('.//svg:g[@data-candle-index]/svg:rect', SVG_NS)]
    assert positions[1] - positions[0] == pytest.approx(positions[2] - positions[1], abs=0.003), "Epoch floating-point subtraction distorted equal millisecond gaps"


def test_LongAnnotationHasBoundedDisplayAndCompleteMetadata() -> None:
    """Paragraph-like markers cannot clip the canvas or silently lose their text."""

    text = "A long below annotation " * 100
    spec = ChartSpec((Spec().candles[0],), width=480, height=360, markers=(ChartMarker(0, text, "below"),))
    root = ET.fromstring(RenderSVG(spec))
    marker = root.find('.//svg:text[@data-marker]', SVG_NS)
    lines = marker.findall('svg:tspan', SVG_NS)

    assert len(lines) == 3 and lines[-1].text.endswith("…"), "Long marker has no bounded visible display"
    assert marker.find('svg:title', SVG_NS).text == text, "Marker overflow discarded the original annotation"
    assert float(marker.attrib["y"]) + (len(lines) - 1) * 15 < float(root.attrib["height"]), "Long annotation extended outside its canvas"


def test_SaveSvgUsesExactRenderedBytesAndPropagatesErrors(tmp_path) -> None:
    """File writes report real filesystem failures instead of claiming success."""

    spec = replace(Spec(), theme="light")
    path = tmp_path / "chart.svg"
    assert SaveSVG(spec, path) == path, "SaveSVG returned a different output path"
    assert path.read_text(encoding="utf-8") == RenderSVG(spec), "Saved SVG differs from the validated renderer output"

    with pytest.raises(OSError):
        SaveSVG(spec, tmp_path / "missing" / "chart.svg")
