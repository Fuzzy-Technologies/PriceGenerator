"""Verify practical chart migration against real legacy analysis and caller state."""

from copy import deepcopy
from datetime import timedelta
import os
import random
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest
from pytz import AmbiguousTimeError, NonExistentTimeError

from pricegenerator import PriceGenerator
from pricegenerator.rendering import ChartCandle, ChartSpec
from pricegenerator.rendering import adapters
from pricegenerator.rendering.__main__ import Main


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


def MakeModel(length: int = 240):
    """Prepare an existing model; adapter tests snapshot RNG after this setup."""

    model = PriceGenerator.PriceGenerator()
    model.prices = MakeFrame(length)
    model.ticker = "MIGRATION"
    model.horizon = length
    model.timeframe = timedelta(hours=1)
    model.precision = 2

    return model


def AssertVector(actual, expected) -> None:
    """Compare renderer gaps and finite values against real analysis output."""

    converted = [np.nan if value is None else value for value in actual]
    np.testing.assert_allclose(converted, expected, rtol=1e-12, atol=1e-12, equal_nan=True, err_msg="Migrated indicator differs from the selected legacy formula")


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


def test_LegacyAnalysisPreservesCallerAndRng() -> None:
    """Analysis may mutate only the detached copy, including private stat fields."""

    model = MakeModel()
    original_prices = model.prices.copy(deep=True)
    original_stat = deepcopy(model.stat)
    original_config = (model.precision, model._chartTitle, model.horizon, model.timeframe)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    adapters.BuildLegacyChart(model)
    pd.testing.assert_frame_equal(model.prices, original_prices)

    assert model.stat == original_stat, "Chart analysis must not replace or mutate the caller's statistics."
    assert (model.precision, model._chartTitle, model.horizon, model.timeframe) == original_config, "Chart creation must not alter generator configuration."
    assert random.getstate() == python_state, "Adapters must not instantiate a randomizing generator or consume Python RNG."
    np.testing.assert_equal(np.random.get_state(), numpy_state, err_msg="Adapter changed NumPy RNG state")


def test_CompleteReportAndEveryHistoricalIndicator() -> None:
    """Retain all report lines and actual legacy TA vectors, not placeholder values."""

    model = MakeModel()
    legacy = deepcopy(model)
    legacy.DetectTimeframe()
    expected_summary = legacy.GetStatistics()
    chart = adapters.BuildLegacyChart(model)
    series = {item.key: item for item in chart.series}

    assert chart.summary == tuple(expected_summary), "Every historical Markdown report line must survive migration."

    for key in ("sma5", "sma20", "sma50", "sma200", "hma5", "hma20", "vwma5", "vwma20"):
        AssertVector(series[key].values, legacy.stat[key])
        assert not series[key].visible, "Legacy technical indicators must initially remain hidden."

    for key in ("lower", "mid", "upper"):
        AssertVector(series[f"bbands-{key}"].values, legacy.stat["bbands"][key])

    for key in ("long", "short"):
        AssertVector(series[f"psar-{key}"].values, legacy.stat["psar"][key])
        assert series[f"psar-{key}"].kind == "points", "PSAR must remain separate long/short point series."

    for key in ("hma13", "hma8", "hma5"):
        AssertVector(series[f"alligator-{key}"].values, legacy.stat[key])

    AssertVector(series["average-line"].values, legacy.prices.avg)
    AssertVector(series["average-points"].values, legacy.prices.avg)
    assert series["average-points"].kind == "points", "Midpoint points must coexist with its line."
    assert series["close-max"].values == (float(legacy.stat["closeMax"]),) * len(model.prices), "Maximum-close overlay changed."
    assert series["close-min"].values == (float(legacy.stat["closeMin"]),) * len(model.prices), "Minimum-close overlay changed."
    assert "legacy shift 3" in series["hma5"].label, "The historical HMA5 overwrite must be disclosed."


def test_ExplicitHMA5CorrectionPreservesAlligatorLips() -> None:
    """Opting into true HMA5 must not remove the historical shifted Alligator line."""

    model = MakeModel()
    legacy = {item.key: item for item in adapters.BuildLegacyChart(model).series}
    corrected = {item.key: item for item in adapters.BuildLegacyChart(model, hma5_mode="unshifted").series}
    expected = adapters._UnshiftedHMA(model.prices.close)
    AssertVector(corrected["hma5"].values, expected)

    assert corrected["hma5"].values != legacy["hma5"].values, "The explicit correction must produce unshifted HMA5."
    assert corrected["alligator-hma5"].values == legacy["alligator-hma5"].values, "Alligator lips must retain offset 3."
    assert corrected["hma5"].label == "HMA 5 (unshifted)", "Corrected semantics must be visible in the label."


def test_TrendsAndZigZagFollowElapsedTimeWithoutExtrapolation() -> None:
    """Sparse indicator connections must preserve time gaps and original endpoints."""

    model = MakeModel(30)
    model.prices.loc[10:, "datetime"] += pd.Timedelta(days=2)
    model.trendSplit = "/\\-"
    model.splitCount = [10, 10, 10]
    chart = adapters.BuildLegacyChart(model)
    series = {item.key: item for item in chart.series}
    legacy = deepcopy(model)
    legacy.GetStatistics()
    selected = legacy.stat["zigzag3"]

    for index, value in selected["filtered"].items():
        assert series["zigzag"].values[index] == value, "Zig-Zag selected endpoints must be unchanged."

    last = selected.index[-1]
    assert all(value is None for value in series["zigzag"].values[last + 1:]), "Zig-Zag must not extrapolate after its last selected point."
    first_time = model.prices.datetime.iloc[0]
    ratio = (model.prices.datetime.iloc[10] - first_time) / (model.prices.datetime.iloc[-1] - first_time)
    expected = (1 - ratio) * model.prices.close.iloc[0] + ratio * model.prices.close.iloc[-1]

    assert series["trend"].values[10] == pytest.approx(expected), "Trend interpolation must follow elapsed time, not row count."
    assert series["trend-segment-2"].values[:10] == (None,) * 10, "A split trend must not extend outside its segment."
    assert series["trend-segment-2"].values[20:] == (None,) * 10, "A split trend must end at its segment boundary."


def test_ZeroVolumeRemainsValidWithVWMAWarmupGaps() -> None:
    """Undefined zero-volume VWMA values become gaps, without inventing prices."""

    model = MakeModel(30)
    model.prices["volume"] = 0
    chart = adapters.BuildLegacyChart(model)
    values = {item.key: item.values for item in chart.series}

    assert values["vwma5"] == (None,) * 30, "Zero-volume VWMA must be represented as gaps."
    assert all(candle.volume == 0 for candle in chart.candles), "The renderer must preserve the original zero volumes."


def test_RawLegacyAdapterNeedsNoStatisticsAndAllowsOneCandle(monkeypatch) -> None:
    """Turning analysis off must support raw edge cases without loading TA."""

    model = MakeModel(1)
    model.prices.loc[0, ["open", "close", "high", "low"]] = [0, 0, 1, -1]

    def RejectAnalysis(*args, **kwargs):
        """Fail if raw chart conversion accidentally requests technical analysis."""

        raise AssertionError("Raw charts must not call GetStatistics")

    monkeypatch.setattr(model, "GetStatistics", RejectAnalysis)
    chart = adapters.BuildLegacyChart(model, include_statistics=False)

    assert len(chart.candles) == 1 and chart.candles[0].close == 0, "Raw charts must support a single zero-close candle."
    assert chart.series == () and chart.summary == (), "Raw conversion must not silently calculate overlays or reports."


@pytest.mark.parametrize("change", ["short", "zero-close", "bad-split", "bad-mode", "bad-boolean"])
def test_ExplicitLegacyAnalysisBoundaries(change: str) -> None:
    """Reject known legacy limitations and invalid options with actionable errors."""

    model = MakeModel(30)
    options = {}

    if change == "short":
        model.prices = model.prices.head(4)

    elif change == "zero-close":
        model.prices.loc[0, ["open", "close", "high", "low"]] = [0, 0, 1, -1]

    elif change == "bad-split":
        model.trendSplit = "/"
        model.splitCount = [10]

    elif change == "bad-mode":
        options["hma5_mode"] = "guessed"

    else:
        options["include_statistics"] = 1

    with pytest.raises(ValueError):
        adapters.BuildLegacyChart(model, **options)


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


def test_CliWritesRequestedOfflineChartsAndReport(tmp_path) -> None:
    """The new CSV command must produce useful offline files with explicit options."""

    source = tmp_path / "prices.csv"
    MakeFrame(5).to_csv(source, index=False)
    svg = tmp_path / "chart.svg"
    html = tmp_path / "chart.html"
    report = tmp_path / "report.md"
    state = random.getstate()
    result = Main([str(source), "--svg", str(svg), "--html", str(html), "--report", str(report), "--summary", "Research scenario", "--title", "CSV example"])

    assert result == 0, "CSV chart command must succeed for valid inputs."
    assert random.getstate() == state, "CSV chart conversion must not consume generator RNG state."
    assert "<svg" in svg.read_text() and "data:image/png;base64," in svg.read_text(), "SVG must include the rendered chart and packaged logos."
    assert "PriceGeneratorView.Mount" in html.read_text(), "HTML must include the offline interactive chart runtime."
    assert "Research scenario" in report.read_text(), "CLI report must retain the caller's summary."


def test_CliReadsHistoricalCsvOnlyWithExplicitTimezone(tmp_path) -> None:
    """Historical headerless prices need an explicit format and timezone policy."""

    source = tmp_path / "legacy.csv"
    source.write_text("2026.10.15,10:00,100,102,99,101,200\n2026.10.15,11:00:00,101,103,100,102,300\n")
    output = tmp_path / "chart.svg"

    with pytest.raises(SystemExit) as captured:
        Main([str(source), "--legacy-csv", "--svg", str(output)])

    assert captured.value.code == 2 and not output.exists(), "Naive CSV must fail before any output is written."
    assert Main([str(source), "--legacy-csv", "--timezone", "Europe/Moscow", "--svg", str(output)]) == 0, "Explicit timezone must enable historical CSV migration."
    assert "2026-10-15" in output.read_text(), "Historical input must produce a dated chart."


@pytest.mark.parametrize("mode", ["no-output", "input-overwrite", "output-collision"])
def test_CliRejectsMissingOrDangerousOutputPaths(tmp_path, mode: str) -> None:
    """Output selection must not accidentally destroy source data or another output."""

    source = tmp_path / "prices.csv"
    MakeFrame(5).to_csv(source, index=False)
    original = source.read_bytes()
    arguments = [str(source)]

    if mode == "input-overwrite":
        arguments += ["--svg", str(source)]

    elif mode == "output-collision":
        arguments += ["--svg", str(tmp_path / "same"), "--html", str(tmp_path / "same")]

    with pytest.raises(SystemExit) as captured:
        Main(arguments)

    assert captured.value.code == 2, "Unsafe output arguments must produce a command usage error."
    assert source.read_bytes() == original, "Rejected chart commands must preserve every input byte."


@pytest.mark.parametrize("mode", ["input-alias", "output-alias"])
def test_CliRejectsHardLinkedOutputPaths(tmp_path, mode: str) -> None:
    """Different names for one existing file must not bypass output safeguards."""

    source = tmp_path / "prices.csv"
    MakeFrame(5).to_csv(source, index=False)
    original = source.read_bytes()
    alias = tmp_path / "alias.svg"

    if mode == "input-alias":
        os.link(source, alias)
        arguments = [str(source), "--svg", str(alias)]

    else:
        output = tmp_path / "chart.html"
        output.write_text("Existing output")
        os.link(output, alias)
        arguments = [str(source), "--svg", str(alias), "--html", str(output)]

    with pytest.raises(SystemExit) as captured:
        Main(arguments)

    assert captured.value.code == 2, "File identity collisions must produce a command usage error."
    assert source.read_bytes() == original, "Hard-link aliases must never allow source data to be overwritten."

    if mode == "output-alias":
        assert output.read_text() == "Existing output", "Colliding output aliases must remain untouched."


def test_CliNumericMarkerTextRemainsText(tmp_path) -> None:
    """CSV type inference must not reject annotations containing only digits."""

    source = tmp_path / "prices.csv"
    MakeFrame(5).to_csv(source, index=False)
    markers = tmp_path / "markers.csv"
    markers.write_text("datetime,markersUpper\n2026-10-15T00:00:00Z,123\n")
    output = tmp_path / "chart.svg"

    assert Main([str(source), "--markers", str(markers), "--svg", str(output)]) == 0, "CSV markers are text even when they contain digits only."
    root = ET.fromstring(output.read_text())

    assert any(element.text == "123" for element in root.iter() if element.tag.rsplit("}", 1)[-1] in {"text", "tspan"}), "The numeric-looking marker must remain visible literal text."
