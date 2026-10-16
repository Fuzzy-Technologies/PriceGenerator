"""Verify modern documentation examples use seeded data and explicit chart output."""

import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from tools.chart_examples import ExamplePrices, GenerateExamples


def test_SeededExampleIsDeterministicWithExplicitSessionGap():
    """Example-only gap and activity modifications retain valid detached data."""

    first = ExamplePrices()
    second = ExamplePrices()
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 96 and (first.volume.iloc[:4] == 0).all()
    assert first.datetime.iloc[48] - first.datetime.iloc[47] == pd.Timedelta(days=2, minutes=30)
    assert (first.open.iloc[1:].to_numpy() == first.close.iloc[:-1].to_numpy()).all()


def test_ExamplesContainModernIndicatorsAndOnePriceWordmark(tmp_path, monkeypatch):
    """Actual standalone outputs show independent indicators without browser use."""

    from pricegenerator.rendering import api

    def Fail(uri):
        """Reject accidental UI actions during deterministic example generation."""

        pytest.fail("Example generation must not open the browser")

    monkeypatch.setattr(api.webbrowser, "open", Fail)
    outputs = GenerateExamples(tmp_path, interactive=True)
    assert len(outputs) == 6 and all(path.exists() for path in outputs)
    namespace = {"svg": "http://www.w3.org/2000/svg"}

    for name in ("modern-market", "modern-indicator-alignment"):
        root = ET.fromstring((tmp_path / f"{name}.svg").read_text())
        groups = root.findall('.//svg:g[@data-watermark-panel]', namespace)
        assert len(groups) == 1 and groups[0].attrib["data-watermark-panel"] == "price"
        assert "<!doctype html>" in (tmp_path / f"{name}.html").read_text()
        assert "seed20261016" in (tmp_path / f"{name}.md").read_text()

    indicator = ET.fromstring((tmp_path / "modern-indicator-alignment.svg").read_text())
    keys = {element.attrib["data-series"] for element in indicator.findall('.//svg:g[@data-series]', namespace)}
    assert keys == {"hma5", "alligator-jaw", "alligator-teeth", "alligator-lips"}
