"""Protect embedding processes and keep browser launch behind explicit requests."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from pricegenerator import PriceGenerator


def test_ImportPreservesProcessStreamsAndRandomState():
    """Ensure importing the library does not redirect streams, launch commands, or draw randomness."""

    script = '''"""Check host-process invariants in a fresh interpreter."""
import logging
import os
import random
import sys
import webbrowser
import numpy
import pandas


def RejectLaunch(*args, **kwargs):
    """Reject browser or shell execution during import."""

    raise AssertionError("Import attempted to launch an external process")


os.system = RejectLaunch
webbrowser.open = RejectLaunch
random.seed(8128)
random_state = random.getstate()
stdout, stderr = sys.stdout, sys.stderr
root_handlers = list(logging.getLogger().handlers)
import pricegenerator
from pricegenerator import PriceGenerator
assert sys.stdout is stdout, "Import replaced host stdout"
assert sys.stderr is stderr, "Import replaced host stderr"
assert random.getstate() == random_state, "Import consumed host random state"
assert logging.getLogger().handlers == root_handlers, "Import reconfigured root logging"
'''
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"Import modified host-process state: {result.stderr}"


@pytest.mark.parametrize("method_name", ["RenderBokeh", "RenderGoogle"])
@pytest.mark.parametrize("view_in_browser", [False, True])
def test_BrowserLaunchUsesFileUriOnlyOnRequest(tmp_path, monkeypatch, method_name, view_in_browser):
    """Treat spaces, quotes, and shell metacharacters as filename data."""

    pytest.importorskip("bokeh" if method_name == "RenderBokeh" else "jinja2")
    model = PriceGenerator.PriceGenerator()
    model.horizon = 8
    model.Generate()
    monkeypatch.setattr(model, "GetStatistics", Mock(return_value=[]))
    browser = Mock(return_value=True)
    shell = Mock(side_effect=AssertionError("Rendering must never invoke a shell"))
    monkeypatch.setattr(PriceGenerator.webbrowser, "open", browser)
    monkeypatch.setattr(PriceGenerator.os, "system", shell)
    output_path = tmp_path / "chart 'quoted'; $command & space.html"
    options = {"showStatOnChart": False} if method_name == "RenderBokeh" else {}
    getattr(model, method_name)(
        fileName=str(output_path), viewInBrowser=view_in_browser, **options,
    )
    assert output_path.is_file(), "Renderer did not create the requested file"
    shell.assert_not_called()

    if view_in_browser:
        browser.assert_called_once_with(output_path.resolve().as_uri())

    else:
        browser.assert_not_called()


def test_FailedBokehSaveDoesNotOpenBrowser(tmp_path, monkeypatch):
    """Do not launch a stale or absent chart after Bokeh fails to serialize it."""

    plotting = pytest.importorskip("bokeh.plotting")
    model = PriceGenerator.PriceGenerator()
    model.horizon = 8
    model.Generate()
    browser = Mock()
    monkeypatch.setattr(PriceGenerator.webbrowser, "open", browser)
    monkeypatch.setattr(plotting, "save", Mock(side_effect=OSError("Output is unwritable")))
    model.RenderBokeh(
        fileName=str(tmp_path / "unwritten.html"), viewInBrowser=True, showStatOnChart=False,
    )
    browser.assert_not_called()
    assert not (tmp_path / "unwritten.html").exists(), "Failure unexpectedly wrote the chart"


def test_InlineRenderingReportsMissingNotebookExtra(monkeypatch):
    """Keep notebook infrastructure optional until inline output is requested."""

    pytest.importorskip("bokeh")
    real_import = PriceGenerator.import_module

    def ImportWithoutNotebook(name):
        """Represent a render installation without notebook support."""

        if name == "IPython":
            raise ModuleNotFoundError("No module named 'IPython'", name=name)

        return real_import(name)

    monkeypatch.setattr(PriceGenerator, "import_module", ImportWithoutNotebook)
    model = PriceGenerator.PriceGenerator()

    with pytest.raises(ImportError, match=r"pricegenerator\[notebook\]"):
        model.RenderBokeh(inline=True)
