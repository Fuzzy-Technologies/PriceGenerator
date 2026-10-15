"""Exercise renderer-independent validation, isolation, and safe serialization."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pricegenerator.rendering.spec import ChartCandle, ChartMarker, ChartSeries, ChartSpec


def Candle(timestamp: str = "2026-10-15T12:00:00Z") -> ChartCandle:
    """Build an ordinary valid candle for independent boundary tests."""

    return ChartCandle(timestamp, 10, 12, 8, 11, 100)


def test_SpecSnapshotsCallerSequences() -> None:
    """Caller list mutation must not change an existing chart snapshot."""

    candles = [Candle(), Candle("2026-10-15T12:01:00Z")]
    values = [10, None]
    series = ChartSeries("moving-average", "Moving average", values)
    spec = ChartSpec(candles, series=[series], summary=["Two candles"])
    candles.clear()
    values[0] = 999

    assert len(spec.candles) == 2, "Caller mutation changed the chart's candles"
    assert spec.series[0].values == (10.0, None), "Caller mutation changed overlay data"

    with pytest.raises(FrozenInstanceError):
        spec.title = "Changed"


@pytest.mark.parametrize("timestamp", [
    "2026-10-15T12:00:00", "not-a-date", "2026-02-30T00:00:00Z",
    "2026-10-15T12:00:00.000001Z", "2026-10-15", None,
])
def test_RejectsAmbiguousOrInvalidTimestamps(timestamp: str) -> None:
    """Timezones and browser-safe timestamp precision are explicit inputs."""

    with pytest.raises(ValueError, match="datetime"):
        Candle(timestamp)


def test_NormalizesTimezoneAndRejectsInstantDuplicates() -> None:
    """Equivalent timezone offsets must not become distinct candle identities."""

    shifted = Candle("2026-10-15T15:00:00+03:00")
    assert shifted.datetime == "2026-10-15T12:00:00.000Z", "UTC normalization changed the instant"

    with pytest.raises(ValueError, match="strictly increasing"):
        ChartSpec((Candle(), shifted))

    with pytest.raises(ValueError, match="strictly increasing"):
        ChartSpec((Candle("2026-10-15T12:01:00Z"), Candle()))


@pytest.mark.parametrize("field,value", [
    ("open", float("nan")), ("high", float("inf")), ("low", -float("inf")),
    ("close", True), ("volume", -1), ("high", 10), ("low", 11),
])
def test_RejectsInvalidOhlcv(field: str, value: float) -> None:
    """Invalid market data must fail before any renderer builds an artifact."""

    with pytest.raises(ValueError):
        replace(Candle(), **{field: value})


@pytest.mark.parametrize("options", [
    {"candles": ()}, {"width": True}, {"height": 10}, {"theme": "unknown"},
    {"price_precision": 13}, {"show_controls": "yes"}, {"title": "bad\x00text"},
    {"title": "bad\ud800text"}, {"summary": ("bad\ufffftext",)}, {"summary": "not a sequence of lines"},
    {"series": (ChartSeries("short", "Short", ()),)},
    {"markers": (ChartMarker(1, "Missing candle"),)},
])
def test_RejectsInvalidChartConfiguration(options: dict) -> None:
    """Cross-field validation prevents silent omissions and malformed output."""

    values = {"candles": (Candle(),), **options}

    with pytest.raises(ValueError):
        ChartSpec(**values)


@pytest.mark.parametrize("options", [
    {"key": 'bad" onload="alert(1)'}, {"color": "url(javascript:alert(1))"},
    {"kind": "javascript"}, {"visible": 1}, {"width": 0}, {"values": (float("nan"),)}, {"values": {1: 2}},
])
def test_RejectsUnsafeOrInvalidOverlay(options: dict) -> None:
    """Untrusted style-like input must not become raw SVG or JavaScript."""

    values = {"key": "valid", "label": "Overlay", "values": (10,), **options}

    with pytest.raises(ValueError):
        ChartSeries(**values)


def test_RejectsDuplicateOverlayIdentity() -> None:
    """Series identity must be unique for predictable controls and exports."""

    series = ChartSeries("same", "Same", (10,))

    with pytest.raises(ValueError, match="unique"):
        ChartSpec((Candle(),), series=(series, series))


def test_SerializationRoundtripEscapesEmbeddedMarkup() -> None:
    """JSON remains lossless while resisting inline HTML script termination."""

    title = '</script><script>alert("&")</script>\u2028\u2029'
    spec = ChartSpec((Candle(),), title=title, markers=(ChartMarker(0, "↑ & <buy>"),))
    serialized = spec.ToJSON()

    assert "</script>" not in serialized and "&" not in serialized, "Chart JSON can escape its script element"
    assert ChartSpec.FromDict(json.loads(serialized)) == spec, "JSON serialization changed chart meaning"
    detached = spec.ToDict()
    detached["candles"][0]["open"] = 0
    assert spec.candles[0].open == 10, "ToDict exposed mutable chart internals"


@pytest.mark.parametrize("data", [{}, {"schema_version": True}, {"schema_version": 2}, {"schema_version": 1, "unknown": 1}])
def test_RejectsUnknownSerializedContract(data: dict) -> None:
    """Malformed versions and fields must fail instead of guessing migrations."""

    with pytest.raises(ValueError):
        ChartSpec.FromDict(data)


def test_StandaloneRenderingImportsNoHeavyDependencies() -> None:
    """A clean Python process can import static charts without analysis stacks."""

    root = str(Path(__file__).resolve().parents[1])
    code = (
        "import sys; "
        f"sys.path.insert(0, {root!r}); "
        "from pricegenerator.rendering import ChartCandle, ChartSpec, RenderSVG; "
        "spec = ChartSpec((ChartCandle('2026-10-15T00:00:00Z',1,2,0,1,0),)); "
        "assert '<svg' in RenderSVG(spec); "
        "assert not {'pandas','numpy','bokeh','jinja2','pandas_ta'} & sys.modules.keys()"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False)

    assert result.returncode == 0, f"Standalone chart dependency isolation failed: {result.stderr}"
