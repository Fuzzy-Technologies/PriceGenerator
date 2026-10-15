"""Verify lazy integrations and the characterized legacy indicator boundary."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pricegenerator import PriceGenerator


def test_CoreGenerationDoesNotImportOptionalModules():
    """Exercise generation with optional integrations forbidden by the importer."""

    script = '''"""Check the dependency boundary in a fresh process."""
import importlib.abc
import sys

OPTIONAL_MODULES = {"bokeh", "jinja2", "pandas_ta", "pandas_ta_classic", "matplotlib", "IPython", "notebook", "requests"}

class RejectOptionalModules(importlib.abc.MetaPathFinder):
    """Fail if generation even attempts to import an optional backend."""

    def find_spec(self, fullname, path=None, target=None):
        """Reject optional dependency resolution before import side effects."""

        if fullname.partition(".")[0] in OPTIONAL_MODULES:
            raise AssertionError("Core attempted optional import: " + fullname)

sys.meta_path.insert(0, RejectOptionalModules())
from pricegenerator.PriceGenerator import PriceGenerator
model = PriceGenerator()
model.horizon = 8
prices = model.Generate()
assert len(prices) == 8, "Core generation did not return the requested horizon"
assert list(prices) == model.dfHeaders, "Core generation changed legacy OHLCV columns"
assert not OPTIONAL_MODULES.intersection(sys.modules), "Optional dependency leaked into core"
'''
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"Core optional-dependency boundary failed: {result.stderr}"


@pytest.mark.parametrize(
    "module_name, method_name, extra",
    [
        ("bokeh", "RenderBokeh", "render"),
        ("jinja2", "RenderGoogle", "render"),
        ("pandas_ta_classic", "GetStatistics", "indicators"),
    ],
)
def test_MissingOptionalDependencyIsActionable(monkeypatch, module_name, method_name, extra):
    """Report the requested extra before mutating data or writing output."""

    real_import = PriceGenerator.import_module

    def ImportWithoutDependency(name):
        """Simulate one absent distribution without changing other imports."""

        if name == module_name:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        return real_import(name)

    model = PriceGenerator.PriceGenerator()
    model.horizon = 8
    original = model.Generate().copy(deep=True)
    monkeypatch.setattr(PriceGenerator, "import_module", ImportWithoutDependency)

    with pytest.raises(ImportError, match=rf"pricegenerator\[{extra}\]") as error:
        getattr(model, method_name)()

    assert method_name in str(error.value), "Missing-dependency guidance lost the requested feature"
    pd.testing.assert_frame_equal(model.prices, original)


def test_BrokenTransitiveDependencyIsNotMisdiagnosed(monkeypatch):
    """Preserve evidence for a broken installed backend instead of suggesting reinstall."""

    failure = ModuleNotFoundError("Broken backend dependency", name="broken_transitive_dependency")

    def ImportBrokenDependency(name):
        """Expose an internal import failure from the requested backend."""

        raise failure

    monkeypatch.setattr(PriceGenerator, "import_module", ImportBrokenDependency)

    with pytest.raises(ModuleNotFoundError) as error:
        PriceGenerator._LoadOptionalDependency("bokeh", "render", "RenderBokeh")

    assert error.value is failure, "An internal dependency failure was replaced with misleading guidance"


def test_LegacyIndicatorVectorsMatchCharacterizedBackend():
    """Compare every legacy output vector against the real pandas-ta 0.3.14b0 baseline."""

    pytest.importorskip("pandas_ta_classic")
    fixture_path = Path(__file__).with_name("legacy_indicators.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    model = PriceGenerator.PriceGenerator()
    model.prices = pd.DataFrame(fixture["prices"])
    model.prices["datetime"] = pd.to_datetime(model.prices["datetime"], utc=True)
    model.horizon = len(model.prices)
    summary = model.GetStatistics()
    assert summary, "Legacy statistics returned no summary with the indicators extra installed"

    for name, expected in fixture["indicators"].items():
        group, separator, column = name.partition(".")
        actual = model.stat[group][column] if separator else model.stat[name]
        np.testing.assert_allclose(
            np.asarray(actual, dtype=float), np.asarray(expected, dtype=float),
            rtol=1e-10, atol=1e-10, equal_nan=True,
            err_msg=f"Optional backend changed the characterized legacy {name} vector",
        )
