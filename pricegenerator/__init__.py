"""Expose explicit v2 generation, validation, diagnostics and optional chart APIs."""

from importlib import import_module
from typing import Any

from pricegenerator._version import __version__
from pricegenerator.config import GenerationConfig


_EXPORTS = {
    "Generate": ("generation", "Generate"),
    "CreateManifest": ("scenario", "CreateManifest"),
    "Replay": ("scenario", "Replay"),
    "Fingerprint": ("scenario", "Fingerprint"),
    "ValidateOHLCV": ("market_data", "ValidateOHLCV"),
    "ReadCSV": ("io", "ReadCSV"),
    "WriteCSV": ("io", "WriteCSV"),
    "Analyze": ("analysis", "Analyze"),
    "Indicators": ("indicators", "Indicators"),
    "Chart": ("rendering.api", "Chart"),
    "DisplayChart": ("rendering.api", "DisplayChart"),
    "GenerateChunks": ("streaming", "GenerateChunks"),
    "WriteCSVChunks": ("streaming", "WriteCSVChunks"),
}
__all__ = ["__version__", "GenerationConfig", *_EXPORTS]


def __getattr__(name: str) -> Any:
    """Import feature modules only when an explicit public feature is requested."""

    if name not in _EXPORTS:
        raise AttributeError(f"module 'pricegenerator' has no attribute {name!r}")

    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(f"pricegenerator.{module_name}"), attribute)
    globals()[name] = value

    return value
