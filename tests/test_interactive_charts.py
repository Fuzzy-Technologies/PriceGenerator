"""Verify offline HTML, safe input handling, and reproducible bundled assets."""

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pricegenerator.rendering.interactive import RenderInteractive, SaveInteractive
from pricegenerator.rendering.spec import ChartCandle, ChartMarker, ChartSeries, ChartSpec


class DocumentParser(HTMLParser):
    """Collect executable surfaces without executing untrusted document text."""

    def __init__(self) -> None:
        """Initialize detached lists for each parsed HTML document."""

        super().__init__()
        self.tags = []
        self.scripts = {}
        self.current_script = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record attributes and the identifier of script data blocks."""

        attributes = dict(attrs)
        self.tags.append((tag, attributes))

        if tag == "script":
            self.current_script = attributes.get("id", "script-" + str(len(self.scripts)))
            self.scripts[self.current_script] = ""

    def handle_data(self, data: str) -> None:
        """Preserve script text for exact JSON restoration and script counting."""

        if self.current_script is not None:
            self.scripts[self.current_script] += data

    def handle_endtag(self, tag: str) -> None:
        """Stop collecting text after the actual parser sees a script ending."""

        if tag == "script":
            self.current_script = None


def SampleSpec(**changes: object) -> ChartSpec:
    """Create a representative chart with a time gap and missing overlay point."""

    values = {
        "candles": (
            ChartCandle("2026-01-01T00:00:00Z", 100, 105, 98, 103, 10),
            ChartCandle("2026-01-01T01:00:00Z", 103, 104, 99, 101, 20),
            ChartCandle("2026-01-02T01:00:00Z", 101, 107, 100, 105, 30),
        ),
        "series": (ChartSeries("sma", "Moving average", (None, 102, 103), group="Trend", visible=False),),
        "markers": (ChartMarker(2, "Breakout"),),
        "summary": ("Three deterministic candles",),
    }
    values.update(changes)

    return ChartSpec(**values)


def ParseDocument(html: str) -> DocumentParser:
    """Return a structural document parser with all script bodies collected."""

    parser = DocumentParser()
    parser.feed(html)

    return parser


def test_OfflineDocumentEmbedsRuntimeBrandingAndLicenses() -> None:
    """An exported chart needs no CDN, package manager, or external image."""

    spec = SampleSpec()
    document = RenderInteractive(spec)
    parsed = ParseDocument(document)
    restored = ChartSpec.FromDict(json.loads(parsed.scripts["chart-spec"]))
    branding = json.loads(parsed.scripts["chart-branding"])
    assert restored == spec, "HTML must retain the exact validated market-data snapshot"
    assert len(parsed.scripts) == 6, "Only the three data blocks and three trusted scripts may appear"
    assert all(source.startswith("data:image/png;base64,") for source in branding.values())
    assert set(branding) == {"wordmark", "emblem"}
    assert not any(attrs.get("src") or attrs.get("href") for _, attrs in parsed.tags), "No external resource references are allowed"
    assert "Apache License" in document and "BSD 3-Clause License" in document
    assert "Microsoft Corporation" in document and "Apache Software Foundation" in document
    assert "prefers-reduced-motion:reduce" in document
    assert "data-action=\"full\"" in document


@pytest.mark.parametrize("hostile", [
    '</script><script>alert("injected")</script>',
    '<img src="https://untrusted.example/logo" onerror="alert(1)">',
    '\u2028\u2029 & <b>quoted "text"</b>',
])
def test_UntrustedStringsCannotCreateMarkupOrScript(hostile: str) -> None:
    """Titles, legends, markers, groups and summaries remain inert user text."""

    spec = SampleSpec(title=hostile, summary=(hostile,), markers=(ChartMarker(0, hostile),),
        series=(ChartSeries("safe", hostile, (1, 2, 3), group=hostile),))
    parsed = ParseDocument(RenderInteractive(spec))
    assert len(parsed.scripts) == 6, "A user string must not create an extra script tag"
    assert not any(tag == "img" for tag, _ in parsed.tags), "A user string must not create an image request"
    assert ChartSpec.FromDict(json.loads(parsed.scripts["chart-spec"])) == spec
    assert "</script" not in parsed.scripts["chart-spec"].lower()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_DeterministicThemesAndControls(theme: str) -> None:
    """Each theme exports reproducibly and explicitly disables requested controls."""

    spec = SampleSpec(theme=theme, show_controls=False)
    first = RenderInteractive(spec)
    second = RenderInteractive(spec)
    parsed = ParseDocument(first)
    controls = next(attrs for tag, attrs in parsed.tags if attrs.get("id") == "controls")
    assert first == second, "Identical snapshots must produce byte-identical HTML"
    assert "hidden" in controls
    assert json.loads(parsed.scripts["chart-spec"])["show_controls"] is False
    assert f'content="{theme}"' in first


def test_SaveInteractivePreservesExplicitPathAndUTF8(tmp_path: Path) -> None:
    """Saving writes the supplied document without starting any browser."""

    spec = SampleSpec(title="Price Δ — chart")
    path = tmp_path / "chart.html"
    result = SaveInteractive(spec, path)
    assert result == path
    assert path.read_text(encoding="utf-8") == RenderInteractive(spec)


def test_SaveInteractivePropagatesFilesystemErrors(tmp_path: Path) -> None:
    """Missing output directories remain explicit errors rather than silent success."""

    with pytest.raises(FileNotFoundError):
        SaveInteractive(SampleSpec(), tmp_path / "absent" / "chart.html")


def test_RendererRequiresValidatedContract() -> None:
    """Raw dictionaries cannot bypass the shared validation boundary."""

    with pytest.raises(TypeError, match="validated ChartSpec"):
        RenderInteractive({"candles": []})


def test_HiddenExtremeOverlayFailsBeforeWritingHTML(tmp_path: Path) -> None:
    """A hidden outlier must not silently flatten all ordinary candle geometry."""

    spec = SampleSpec(series=(ChartSeries("outlier", "Hidden extreme", (1e308, 1e308, 1e308), visible=False),))

    with pytest.raises(ValueError, match="rescale prices/overlays"):
        RenderInteractive(spec)

    path = tmp_path / "chart.html"

    with pytest.raises(ValueError, match="rescale prices/overlays"):
        SaveInteractive(spec, path)

    assert not path.exists(), "An unsupported numerical domain must not create a misleading chart"


@pytest.mark.parametrize("value", [1e-308, 1e308, -1e308])
def test_HomogeneousExtremePricesRemainSupported(value: float) -> None:
    """The numerical capability guard must not reject valid small or large prices."""

    spec = ChartSpec((ChartCandle("2026-01-01T00:00:00Z", value, value, value, value, 1),))
    assert "<!doctype html>" in RenderInteractive(spec)


def test_VendoredRuntimeMatchesRecordedIntegrity() -> None:
    """The vendored artifact must match its official-source and build manifest."""

    root = Path(__file__).resolve().parents[1] / "pricegenerator/rendering/assets/echarts"
    runtime = (root / "echarts-financial.min.js").read_bytes()
    metadata = json.loads((root / "build.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(runtime).hexdigest() == metadata["sha256"]
    assert len(runtime) == metadata["raw_bytes"]
    assert metadata["echarts_version"] == "6.1.0"
    assert metadata["echarts_source"].startswith("https://registry.npmjs.org/echarts/")
    assert metadata["echarts_source_integrity"].startswith("sha512-")


def test_RendererWorksWithoutOptionalDependencies() -> None:
    """Fresh Python imports require neither legacy renderers nor data libraries."""

    code = '''"""Check that offline rendering does not import optional legacy dependencies."""
import sys
from pricegenerator.rendering.spec import ChartCandle, ChartSpec
from pricegenerator.rendering.interactive import RenderInteractive
chart = ChartSpec((ChartCandle("2026-01-01T00:00:00Z", 1, 2, 0, 1, 0),))
assert "<!doctype html>" in RenderInteractive(chart)
assert not {"bokeh", "pandas", "jinja2", "numpy"}.intersection(sys.modules)
'''
    completed = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
