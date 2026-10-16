"""Verify modern chart integration and immutable caller-owned data boundaries."""

import random
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from pytz import AmbiguousTimeError, NonExistentTimeError

from pricegenerator.rendering import ChartCandle, ChartSpec
from pricegenerator.rendering import adapters


def MakeFrame(length: int = 240) -> pd.DataFrame:
    """Create deterministic, valid and nontrivial prices without any RNG calls."""

    index = np.arange(length)
    opening = 100 + np.sin(index / 9) * 8 + index / 100
    closing = opening + np.cos(index / 5) * 2

    return pd.DataFrame({
        "datetime": pd.date_range("2026-10-15T00:00:00Z", periods=length, freq="h"),
        "open": np.round(opening, 2), "high": np.round(np.maximum(opening, closing) + 1, 2),
        "low": np.round(np.minimum(opening, closing) - 1, 2), "close": np.round(closing, 2),
        "volume": 100 + index % 19 * 5,
    })


def test_DataFrameSnapshotDoesNotMutateOrRetainInput() -> None:
    """Chart values must be detached from both original data and its index."""

    frame = MakeFrame(5)
    frame.index = [10, 20, 30, 40, 50]
    original = frame.copy(deep=True)
    state = random.getstate()
    chart = adapters.FromDataFrame(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert random.getstate() == state, "Snapshot conversion must not consume global RNG state."
    frame.loc[10, "close"] = 999

    assert chart.candles[0].close == original.loc[10, "close"], "The immutable chart must not retain mutable DataFrame values."


def test_ModernOverlaysAreExplicitAndIndependent() -> None:
    """Analysis is a separate request and never changes the raw chart or frame."""

    from pricegenerator.analysis import Analyze
    from pricegenerator.indicators import Indicators

    frame = MakeFrame()
    original = frame.copy(deep=True)
    state = random.getstate()
    numpy_state = np.random.get_state()
    raw = adapters.FromDataFrame(frame)
    overlays = adapters.MarketOverlays(frame, split_counts=(80, 80, 80))
    report = Analyze(frame)
    chart = adapters.FromDataFrame(frame, series=overlays, summary=report.Summary())
    values = {item.key: item.values for item in chart.series}
    expected = {item.key: item.values for item in Indicators(frame).series}
    pd.testing.assert_frame_equal(frame, original)
    np.testing.assert_equal(np.random.get_state(), numpy_state)

    assert random.getstate() == state, "Modern analysis must not consume Python RNG."
    assert raw.series == () and raw.summary == (), "Raw chart construction must not calculate indicators implicitly."
    assert chart.summary == report.Summary(), "Modern diagnostics must supply the complete chart report."

    for key in expected.keys() - {"zigzag"}:
        assert values[key] == expected[key], f"Indicator {key} must preserve exact aligned modern output."

    assert values["hma5"] != values["alligator-lips"], "Ordinary HMA must never be overwritten by Alligator."
    assert set(values) >= {"close-max", "close-min", "trend", "midpoint-line", "midpoint-points", "zigzag", "trend-segment-3"}, "All retained nonindicator capabilities require an explicit modern route."
    assert not hasattr(adapters, "BuildLegacyChart"), "Legacy calculation adapters must not remain callable."


def test_ElapsedTimeTrendsAndZeroVolume() -> None:
    """Trend geometry follows UTC elapsed time while zero-volume VWMA stays null."""

    frame = MakeFrame(30)
    frame.loc[10:, "datetime"] += pd.Timedelta(days=2)
    frame["volume"] = 0
    overlays = {item.key: item.values for item in adapters.MarketOverlays(frame, split_counts=(10, 10, 10))}
    ratio = (frame.datetime.iloc[10] - frame.datetime.iloc[0]) / (frame.datetime.iloc[-1] - frame.datetime.iloc[0])
    expected = (1 - ratio) * frame.close.iloc[0] + ratio * frame.close.iloc[-1]

    assert overlays["trend"][10] == pytest.approx(expected), "Trend interpolation must follow elapsed time."
    assert overlays["trend-segment-2"][:10] == (None,) * 10, "Split trends cannot extrapolate before their segment."
    assert overlays["trend-segment-2"][20:] == (None,) * 10, "Split trends cannot extrapolate after their segment."
    assert overlays["vwma5"] == (None,) * 30, "Zero-volume VWMA must remain undefined."


def test_NaiveTimeRequiresExplicitTimezone() -> None:
    """Localize naive data only under a caller-supplied timezone policy."""

    frame = MakeFrame(5)
    frame["datetime"] = frame.datetime.dt.tz_localize(None)

    with pytest.raises(ValueError, match="assume_timezone"):
        adapters.FromDataFrame(frame)

    chart = adapters.FromDataFrame(frame, assume_timezone="Europe/Moscow")

    assert chart.candles[0].datetime == "2026-10-14T21:00:00.000Z", "Explicit Moscow timestamps must normalize to UTC correctly."


@pytest.mark.parametrize("timestamp", ["2026-10-15T00:00:00.000000001Z", "2026-10-15T00:00:00.000001Z", "NaT"])
def test_SubmillisecondAndMissingTimesAreRejected(timestamp: str) -> None:
    """Never discard nanoseconds or allow missing times during conversion."""

    frame = MakeFrame(1)
    frame["datetime"] = [timestamp]

    with pytest.raises(ValueError):
        adapters.FromDataFrame(frame)


@pytest.mark.parametrize("timestamp,error", [("2026-03-29T02:30:00", NonExistentTimeError), ("2026-10-25T02:30:00", AmbiguousTimeError)])
def test_DstAmbiguityIsNeverGuessed(timestamp: str, error) -> None:
    """Reject nonexistent and repeated civil times instead of shifting them."""

    frame = MakeFrame(1)
    frame["datetime"] = [timestamp]

    with pytest.raises(error, match="2026-"):
        adapters.FromDataFrame(frame, assume_timezone="Europe/Berlin")


def test_CustomMarkersAndLinesUseExactTimestampsAndGaps() -> None:
    """Support sparse user annotations and multiple named columns without mutation."""

    frame = MakeFrame(5)
    markers = pd.DataFrame({
        "datetime": [frame.datetime.iloc[3], frame.datetime.iloc[1]],
        "markersUpper": ["BUY <test>", ""], "markersCenter": ["", "×"], "markersLower": [None, "SELL"],
    })
    line = pd.DataFrame({"datetime": [frame.datetime.iloc[0], frame.datetime.iloc[4]], "Signal": [100, 105], "Limit": [101, np.nan]})
    original_markers = markers.copy(deep=True)
    original_line = line.copy(deep=True)
    chart = adapters.FromDataFrame(frame, markers=markers, lines=[line], show_controls=False)
    pd.testing.assert_frame_equal(markers, original_markers)
    pd.testing.assert_frame_equal(line, original_line)

    assert [(marker.candle_index, marker.position, marker.text) for marker in chart.markers] == [(3, "above", "BUY <test>"), (1, "center", "×"), (1, "below", "SELL")], "Marker text and relative positions must align by timestamp."
    assert chart.series[0].values == (100, None, None, None, 105), "Sparse custom lines must retain explicit gaps."
    assert chart.series[1].values == (101, None, None, None, None), "Missing user values must be gaps."
    assert not chart.show_controls and all(item.visible for item in chart.series), "Hiding controls must not remove custom overlays."


@pytest.mark.parametrize("representation", ["other-timezone", "reordered"])
def test_DenseAnnotationAlignmentHasIdenticalSerializedMeaning(representation: str) -> None:
    """Fast aligned frames must equal independently normalized or reordered inputs."""

    frame = MakeFrame(8)
    markers = pd.DataFrame({"datetime": frame.datetime, "markersUpper": [f"Event {index}" for index in range(8)]})
    lines = pd.DataFrame({"datetime": frame.datetime, "Reference": [100 + index for index in range(8)]})
    expected = adapters.FromDataFrame(frame, markers=markers, lines=[lines])

    if representation == "other-timezone":
        markers["datetime"] = markers.datetime.dt.tz_convert("Europe/Moscow")
        lines["datetime"] = lines.datetime.dt.tz_convert("Europe/Moscow")

    else:
        # Line values follow their timestamps, not the caller's current row order.
        lines = lines.iloc[::-1]

    actual = adapters.FromDataFrame(frame, markers=markers, lines=[lines])

    assert actual.ToJSON() == expected.ToJSON(), "Equivalent dense annotations must retain identical serialized chart meaning."


@pytest.mark.parametrize("annotation_kind", ["markers", "lines"])
def test_EqualObjectDatetimeValuesCannotBypassAnnotationTypeValidation(annotation_kind: str) -> None:
    """Scalar equality must not admit unsupported timestamp types in object columns."""

    frame = MakeFrame(1)
    frame["datetime"] = pd.Series([pd.Timestamp("2026-10-15").to_pydatetime()], dtype=object)
    annotation = pd.DataFrame({
        "datetime": pd.Series([np.datetime64("2026-10-15T00:00:00.000000")], dtype=object),
        "markersUpper": ["Event"], "Reference": [101],
    })
    options = {"markers": annotation} if annotation_kind == "markers" else {"lines": [annotation[["datetime", "Reference"]]]}

    with pytest.raises(ValueError, match="timestamp or ISO text"):
        adapters.FromDataFrame(frame, assume_timezone="UTC", **options)


@pytest.mark.parametrize("kind", ["outside-time", "duplicate-time", "no-markers", "numeric-marker", "no-line-values", "infinite-line"])
def test_RejectAmbiguousCustomAnnotations(kind: str) -> None:
    """Bad annotation data must fail rather than silently shift or disappear."""

    frame = MakeFrame(5)
    annotation = pd.DataFrame({"datetime": [frame.datetime.iloc[0]], "markersUpper": ["BUY"]})
    options = {"markers": annotation}

    if kind == "outside-time":
        annotation["datetime"] += pd.Timedelta(days=5)

    elif kind == "duplicate-time":
        options["markers"] = pd.concat([annotation, annotation])

    elif kind == "no-markers":
        options["markers"] = annotation[["datetime"]]

    elif kind == "numeric-marker":
        annotation["markersUpper"] = 10

    elif kind == "no-line-values":
        options = {"lines": [annotation[["datetime"]]]}

    else:
        annotation["Limit"] = np.inf
        options = {"lines": [annotation[["datetime", "Limit"]]]}

    with pytest.raises(ValueError):
        adapters.FromDataFrame(frame, **options)


def test_MarkdownPreservesReportAndPropagatesWriteFailure(tmp_path) -> None:
    """Exports include all report lines while rendering user markup as text."""

    chart = adapters.FromDataFrame(MakeFrame(5), title="Title <script>", summary=("# Summary", "- Safe <text>"))
    report = adapters.RenderMarkdown(chart)
    target = tmp_path / "report.md"

    assert report == "# Title &lt;script&gt;\n\n# Summary\n- Safe &lt;text&gt;\n", "Markdown must preserve report structure without raw HTML."
    assert adapters.SaveMarkdown(chart, target) == target, "Report save must return the requested path."
    assert target.read_text() == report, "Saved report must match the pure rendering result."

    with pytest.raises(FileNotFoundError):
        adapters.SaveMarkdown(chart, tmp_path / "missing" / "report.md")


def test_NotebookViewsAreIsolatedAndDisplayIsExplicit(monkeypatch) -> None:
    """Multiple notebook charts must not share DOM IDs or require implicit display."""

    chart = adapters.FromDataFrame(MakeFrame(5), title='Test "quotes"')
    content = adapters.NotebookHTML(chart)

    assert content.startswith("<iframe ") and "srcdoc=" in content, "Each notebook chart requires an isolated document."
    assert 'sandbox="allow-scripts allow-downloads"' in content, "Notebook chart scripts must not access the parent document."
    assert "allow-same-origin" not in content, "Notebook isolation must not grant host-origin script access."
    calls = []

    def RecordDisplay(document, display_id):
        """Record explicit notebook display without starting a kernel."""

        calls.append((document, display_id))

        return "display-handle"

    fake = SimpleNamespace(HTML=lambda value: ("html", value), SVG=lambda value: ("svg", value), display=RecordDisplay)
    original_import = adapters.import_module

    def ImportDisplay(name):
        """Replace only the optional notebook display integration."""

        return fake if name == "IPython.display" else original_import(name)

    monkeypatch.setattr(adapters, "import_module", ImportDisplay)

    assert adapters.DisplayChart(chart) == "display-handle", "Explicit HTML display must return the notebook handle."
    assert adapters.DisplayChart(chart, format="svg") == "display-handle", "Explicit SVG display must return the notebook handle."
    assert calls[0][0][0] == "html" and calls[1][0][0] == "svg", "The selected notebook format must be respected."
    assert all(call[1] is True for call in calls), "Notebook display must request a reusable display handle."


def test_MissingNotebookDependencyHasActionableError(monkeypatch) -> None:
    """A missing optional notebook package must not look like a chart failure."""

    def MissingDisplay(name):
        """Simulate the optional notebook package being absent."""

        raise ModuleNotFoundError("No IPython", name="IPython")

    monkeypatch.setattr(adapters, "import_module", MissingDisplay)
    chart = ChartSpec((ChartCandle("2026-10-15T00:00:00Z", 1, 2, 0, 1, 0),))

    with pytest.raises(ImportError, match=r"pricegenerator\[notebook\]"):
        adapters.DisplayChart(chart)

    with pytest.raises(ValueError, match="format"):
        adapters.DisplayChart(chart, format="pdf")


def test_AdapterImportDoesNotLoadOptionalOrDataframeLibraries() -> None:
    """Importing adapters must retain the renderer's dependency-free boundary."""

    script = "import sys; import pricegenerator.rendering.adapters; assert not {'pandas', 'numpy', 'bokeh', 'jinja2', 'pandas_ta', 'pandas_ta_classic', 'IPython'} & set(sys.modules)"
    completed = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, check=False)

    assert completed.returncode == 0, f"Chart adapter import loaded an optional dependency: {completed.stderr}"


