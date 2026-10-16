"""Verify real Python raster encoders preserve the native static geometry."""

from dataclasses import replace
from io import BytesIO
import xml.etree.ElementTree as ET

import pytest

from pricegenerator.rendering import Chart, ChartCandle, ChartMarker, ChartSpec, RenderJPEG, RenderPNG, RenderSVG
from pricegenerator.rendering import exports
from pricegenerator.rendering.theme import THEMES


def Spec() -> ChartSpec:
    """Exercise negative values, Unicode text and nontransparent theme geometry."""

    return ChartSpec((ChartCandle("2026-01-01T00:00:00Z", -2, 1, -3, 0, 10),),
        width=480, height=360, title="Prices Δ — Пример", markers=(ChartMarker(0, "↑ Δ", "above"),),
        summary=("Negative prices and zero close",))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_RealPNGAndJPEGDecodeToSVGDimensionsAndBackground(theme, tmp_path) -> None:
    """Actual decoders verify signatures, dimensions and defined opaque background."""

    pytest.importorskip("resvg_py")
    image_module = pytest.importorskip("PIL.Image")
    spec = replace(Spec(), theme=theme)
    svg = ET.fromstring(RenderSVG(spec))
    expected_size = (int(svg.attrib["width"]), int(svg.attrib["height"]))
    png = RenderPNG(spec)
    jpeg = RenderJPEG(spec)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert jpeg.startswith(b"\xff\xd8\xff")

    for payload, format in ((png, "PNG"), (jpeg, "JPEG")):
        with image_module.open(BytesIO(payload)) as decoded:
            decoded.load()
            assert decoded.format == format and decoded.size == expected_size
            assert decoded.convert("RGBA").getpixel((0, 0))[3] == 255
            expected = tuple(bytes.fromhex(THEMES[theme]["background"].lstrip("#")))
            assert all(abs(first - second) <= 3 for first, second in zip(decoded.convert("RGB").getpixel((0, 0)), expected))

    assert Chart(spec, tmp_path / "chart.png", view=False).read_bytes() == png
    assert Chart(spec, tmp_path / "chart.jpg", view=False).read_bytes() == jpeg


@pytest.mark.parametrize("value", [0, -1e308, 1e308, 1e-308])
def test_RasterSupportsFlatAndExtremeFinitePrices(value) -> None:
    """The SVG numeric domain survives real rasterization with no browser engine."""

    pytest.importorskip("resvg_py")
    image_module = pytest.importorskip("PIL.Image")
    candle = ChartCandle("2026-01-01T00:00:00Z", value, value, value, value, 0)

    with image_module.open(BytesIO(RenderPNG(ChartSpec((candle,), width=480, height=360)))) as image:
        image.load()
        assert image.size == (480, 360)


def test_OnePriceWordmarkChangesOnlyItsNativeRasterRegion(monkeypatch) -> None:
    """The real renderer preserves filtered logo pixels at their SVG geometry."""

    pytest.importorskip("resvg_py")
    image_module = pytest.importorskip("PIL.Image")
    difference_module = pytest.importorskip("PIL.ImageChops")
    spec = Spec()
    svg = RenderSVG(spec)
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    group = root.find('.//svg:g[@data-watermark-panel]', namespace)
    assert group.attrib["data-watermark-panel"] == "price"
    assert group.attrib["opacity"] == "0.28"
    uses = group.findall("svg:use", namespace)
    assert len(uses) == 1
    use = uses[0]
    x, y = float(use.attrib["x"]), float(use.attrib["y"])
    branded = image_module.open(BytesIO(RenderPNG(spec))).convert("RGB")
    parent = next(element for element in root.iter() if group in list(element))
    parent.remove(group)
    monkeypatch.setattr(exports, "RenderSVG", lambda chart: ET.tostring(root, encoding="unicode"))
    plain = image_module.open(BytesIO(RenderPNG(spec))).convert("RGB")
    bounds = difference_module.difference(branded, plain).getbbox()
    assert bounds is not None, "The wordmark filter rendered no actual pixels"
    assert x <= bounds[0] < bounds[2] <= x + 160
    assert int(y) <= bounds[1] < bounds[3] <= y + 30


@pytest.mark.parametrize("quality", [True, 0, 96, 1.5, "90"])
def test_InvalidJPEGQualityFailsBeforeImport(quality) -> None:
    """Bounded quality rejects bools and values the documented encoder discourages."""

    with pytest.raises(ValueError, match="1 through 95"):
        RenderJPEG(Spec(), quality=quality)


def test_MissingExportDependencyProvidesActionableExtra(monkeypatch) -> None:
    """Missing optional bindings are distinct from unrelated initialization errors."""

    def Missing(name):
        """Represent an absent native binding without requiring environment edits."""

        raise ModuleNotFoundError("missing", name=name)

    monkeypatch.setattr(exports, "import_module", Missing)

    with pytest.raises(ImportError, match=r"pricegenerator\[export\]"):
        RenderPNG(Spec())

    def Broken(name):
        """Represent an internal dependency import failure that must propagate."""

        raise ModuleNotFoundError("internal dependency missing", name="unexpected_internal")

    monkeypatch.setattr(exports, "import_module", Broken)

    with pytest.raises(ModuleNotFoundError, match="internal dependency"):
        RenderPNG(Spec())
