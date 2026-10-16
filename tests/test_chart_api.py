"""Exercise unified chart outputs and viewing without launching an actual browser."""

import pytest

from pricegenerator.rendering import Chart, ChartCandle, ChartSpec
from pricegenerator.rendering import api


def Spec() -> ChartSpec:
    """Provide valid raw geometry without optional data dependencies."""

    return ChartSpec((ChartCandle("2026-01-01T00:00:00Z", -2, 0, -3, -1, 10),), title="Prices Δ — 測試")


def test_DefaultHTMLCreatesTemporaryStandaloneFileAndOpensURI(monkeypatch) -> None:
    """Interactive viewing opens a file URI after a complete file is written."""

    calls = []

    def Open(uri):
        """Observe an existing file instead of opening the system browser."""

        calls.append(uri)

        return True

    monkeypatch.setattr(api.webbrowser, "open", Open)
    result = Chart(Spec())

    try:
        assert result.is_absolute() and result.suffix == ".html"
        assert "<!doctype html>" in result.read_text(encoding="utf-8")
        assert calls == [result.as_uri()]

    finally:
        result.unlink()


@pytest.mark.parametrize("suffix", ["html", "svg"])
def test_ViewFalseNeverCallsBrowser(tmp_path, monkeypatch, suffix) -> None:
    """Batch paths suppress browser calls for both interactive and static files."""

    def Fail(uri):
        """Fail deterministically if batch operation attempts user interaction."""

        pytest.fail("view=False attempted to launch a browser")

    monkeypatch.setattr(api.webbrowser, "open", Fail)
    result = Chart(Spec(), tmp_path / f"chart.{suffix}", view=False)
    assert result.exists()


def test_StaticDefaultsDoNotViewAndExplicitViewOpensURI(tmp_path, monkeypatch) -> None:
    """Static output is noninteractive unless the caller requests viewing."""

    calls = []
    monkeypatch.setattr(api.webbrowser, "open", lambda uri: calls.append(uri) or True)
    path = tmp_path / "chart.svg"
    assert Chart(Spec(), path) == path
    assert calls == []
    Chart(Spec(), path, view=True)
    assert calls == [path.as_uri()]


@pytest.mark.parametrize("format", ["svg", "png", "jpeg"])
def test_StaticRequiresExplicitOutput(format) -> None:
    """Missing static paths fail before rendering or optional imports."""

    with pytest.raises(ValueError, match="explicit output"):
        Chart(Spec(), format=format, view=False)


@pytest.mark.parametrize("name,format", [("chart.webp", None), ("chart.svg", "html"), ("chart.png", "jpeg")])
def test_UnsupportedOrMismatchedFormatFails(tmp_path, name, format) -> None:
    """Filename extensions never mislabel the encoded output."""

    with pytest.raises(ValueError):
        Chart(Spec(), tmp_path / name, format=format, view=False)


def test_BrowserFailureKeepsReviewableOutput(tmp_path, monkeypatch) -> None:
    """A refused browser launch is explicit and preserves the generated chart."""

    path = tmp_path / "chart.html"
    monkeypatch.setattr(api.webbrowser, "open", lambda uri: False)

    with pytest.raises(RuntimeError, match="No browser accepted"):
        Chart(Spec(), path)

    assert path.exists()


def test_OutputErrorsPropagateAndTemporaryFailureCleansUp(tmp_path, monkeypatch) -> None:
    """Failed generation cannot leave an empty temporary output behind."""

    with pytest.raises(FileNotFoundError):
        Chart(Spec(), tmp_path / "absent" / "chart.svg")

    path = tmp_path / "temporary.html"
    original = api.tempfile.mkstemp

    def Temporary(**options):
        """Create the deterministic test output using a real file descriptor."""

        return original(dir=tmp_path, prefix="temporary-", suffix=".html")

    def Fail(*args):
        """Represent an encoder failure after temporary allocation."""

        raise ValueError("encoder failed")

    from pricegenerator.rendering import interactive

    monkeypatch.setattr(api.tempfile, "mkstemp", Temporary)
    monkeypatch.setattr(interactive, "SaveInteractive", Fail)

    with pytest.raises(ValueError, match="encoder failed"):
        Chart(Spec(), view=False)

    assert not list(tmp_path.glob("temporary-*.html"))
    assert not path.exists()


def test_ReportCannotOverwriteChart(tmp_path) -> None:
    """A chart and accompanying report need distinct output paths."""

    path = tmp_path / "chart.html"

    with pytest.raises(ValueError, match="paths must differ"):
        Chart(Spec(), path, markdown_report=path, view=False)

    assert not path.exists()


def test_NotebookDefaultsToHTMLWithoutBrowser(monkeypatch) -> None:
    """The notebook wrapper delegates a validated spec to the isolated HTML path."""

    from pricegenerator.rendering import adapters

    calls = []
    monkeypatch.setattr(adapters, "DisplayChart", lambda spec, **options: calls.append((spec, options)) or "handle")
    assert api.DisplayChart(Spec()) == "handle"
    assert calls == [(Spec(), {"format": "html"})]


def test_DataFrameDefaultsToRawDetachedSnapshot() -> None:
    """Ordinary chart creation has no hidden indicator calculations or mutation."""

    import pandas as pd

    frame = pd.DataFrame({"datetime": pd.to_datetime(["2026-01-01T00:00:00Z"]),
        "open": [-2], "high": [0], "low": [-3], "close": [-1], "volume": [10]})
    original = frame.copy(deep=True)
    spec = api.PrepareChart(frame)
    assert spec.series == () and spec.summary == ()
    assert spec.candles[0].close == -1
    pd.testing.assert_frame_equal(frame, original)
    frame.loc[0, "close"] = -2
    assert spec.candles[0].close == -1


def test_PreparedSpecAllowsPresentationWithoutRecomputingAnalysis() -> None:
    """Presentation options create another immutable spec and preserve overlays."""

    original = Spec()
    result = api.PrepareChart(original, theme="light")
    assert result.theme == "light" and original.theme == "dark"
    assert result.candles == original.candles

    with pytest.raises(ValueError, match="prepared ChartSpec"):
        api.PrepareChart(original, analysis=True)


def test_OptInAnalysisCombinesModernOverlaysAndUserNotes(tmp_path) -> None:
    """The unified path uses actual modern analysis and keeps custom report text."""

    import pandas as pd

    frame = pd.DataFrame({"datetime": pd.date_range("2026-01-01", periods=40, freq="h", tz="UTC"),
        "open": [100 + index / 2 for index in range(40)],
        "high": [102 + index / 2 for index in range(40)],
        "low": [98 + index / 2 for index in range(40)],
        "close": [101 + index / 2 for index in range(40)], "volume": [10] * 40})
    original = frame.copy(deep=True)
    spec = api.PrepareChart(frame, analysis=True, summary=("Caller supplied note",))
    assert len(spec.series) >= 20 and spec.summary[-1] == "Caller supplied note"
    assert any("40" in line for line in spec.summary)
    assert any(series.key == "sma5" for series in spec.series)
    path = Chart(spec, tmp_path / "analyzed.svg", markdown_report=tmp_path / "report.md")
    assert path.exists() and "Caller supplied note" in (tmp_path / "report.md").read_text()
    pd.testing.assert_frame_equal(frame, original)
