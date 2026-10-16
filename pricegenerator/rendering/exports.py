"""Export the native SVG geometry through optional permissive raster libraries."""

from importlib import import_module
from io import BytesIO
from pathlib import Path

from .spec import ChartSpec
from .static import RenderSVG
from .theme import THEMES


def _ExportModule(name: str):
    """Load an export dependency while preserving unrelated import failures."""

    try:
        return import_module(name)

    except ModuleNotFoundError as error:
        if error.name not in {name, name.split(".")[0]}:
            raise

        raise ImportError('Raster export requires: python -m pip install "pricegenerator[export]"') from error


def RenderPNG(spec: ChartSpec) -> bytes:
    """Rasterize exactly the native SVG, including its report, fonts and logos."""

    svg = RenderSVG(spec)
    renderer = _ExportModule("resvg_py")

    return renderer.svg_to_bytes(svg_string=svg, background=THEMES[spec.theme]["background"])


def SavePNG(spec: ChartSpec, path: str | Path) -> Path:
    """Write actual PNG bytes and propagate dependency or filesystem errors."""

    output_path = Path(path)
    output_path.write_bytes(RenderPNG(spec))

    return output_path


def RenderJPEG(spec: ChartSpec, *, quality: int = 90) -> bytes:
    """Encode RGB JPEG over the theme background with quality from 1 through 95."""

    if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 95:
        raise ValueError("JPEG quality must be an integer from 1 through 95")

    image_module = _ExportModule("PIL.Image")
    png = RenderPNG(spec)
    destination = BytesIO()

    with image_module.open(BytesIO(png)) as source:
        rgba = source.convert("RGBA")
        background = image_module.new("RGBA", source.size, THEMES[spec.theme]["background"])
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
        rgb.save(destination, format="JPEG", quality=quality, subsampling=0)

    return destination.getvalue()


def SaveJPEG(spec: ChartSpec, path: str | Path, *, quality: int = 90) -> Path:
    """Write an RGB JPEG without invoking a browser, shell or external process."""

    output_path = Path(path)
    output_path.write_bytes(RenderJPEG(spec, quality=quality))

    return output_path
