"""Corporate colors and exact-source image assets shared by chart renderers."""

import base64
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType


THEMES = MappingProxyType({
    "dark": MappingProxyType({
        "background": "#080d18", "panel": "#111a2b", "text": "#e3ecff",
        "muted": "#95a6c6", "grid": "#26344b", "up": "#40e0cf",
        "down": "#ee72d3", "accent": "#57c7ff", "secondary": "#ad8cff",
        "warning": "#ffc46b",
    }),
    "light": MappingProxyType({
        "background": "#f5f7fc", "panel": "#ffffff", "text": "#182338",
        "muted": "#53627d", "grid": "#d9e0ed", "up": "#087f86",
        "down": "#ae2878", "accent": "#126caa", "secondary": "#7142ac",
        "warning": "#946000",
    }),
})


@lru_cache(maxsize=1)
def _EncodedBranding() -> tuple[str, str]:
    """Load each packaged asset once without network or runtime rewriting."""

    asset_root = files("pricegenerator.rendering").joinpath("assets", "branding")
    encoded = []

    for name in ("FuzzyTechnologies-Logo-transp.png", "ftech-emblem-192.png"):
        encoded.append("data:image/png;base64," + base64.b64encode(asset_root.joinpath(name).read_bytes()).decode("ascii"))

    return encoded[0], encoded[1]


def BrandingData() -> dict[str, str]:
    """Return detached wordmark and emblem data URIs for offline exports."""

    wordmark, emblem = _EncodedBranding()

    return {"wordmark": wordmark, "emblem": emblem}
