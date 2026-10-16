"""Verify that core v2 operations never import optional feature dependencies."""

import subprocess
import sys


def test_CoreOperationsAvoidOptionalImports():
    """Exercise configuration, generation and manifest replay behind an import guard."""

    script = '''"""Reject optional backend resolution in a core-only process."""
import importlib.abc
import sys

OPTIONAL_MODULES = {"bokeh", "jinja2", "pandas_ta", "pandas_ta_classic", "matplotlib", "IPython", "notebook", "requests", "PIL"}


class RejectOptionalModules(importlib.abc.MetaPathFinder):
    """Fail when a core operation tries to load an optional backend."""

    def find_spec(self, fullname, path=None, target=None):
        """Intercept attempted optional imports before they execute."""

        if fullname.partition(".")[0] in OPTIONAL_MODULES:
            raise AssertionError("Core attempted optional import: " + fullname)


sys.meta_path.insert(0, RejectOptionalModules())
from pricegenerator import Generate, GenerationConfig, CreateManifest, Replay
configuration = GenerationConfig(seed=0, horizon=8)
prices = Generate(configuration)
Replay(CreateManifest(configuration, prices))
assert len(prices) == 8, "Core did not generate the requested horizon"
assert not OPTIONAL_MODULES.intersection(sys.modules), "Core imported optional backend"
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Core dependency boundary failed: {result.stderr}"


def test_LegacyPublicModulesAreAbsent():
    """Prevent accidental resurrection of removed classes, loggers or imports."""

    import importlib.util

    import pricegenerator

    assert "PriceGenerator" not in pricegenerator.__all__, "Legacy class returned to the public API"
    assert importlib.util.find_spec("pricegenerator.PriceGenerator") is None, "Legacy runtime module is still installed"
    assert importlib.util.find_spec("pricegenerator.UniLogger") is None, "Legacy logger module is still installed"
