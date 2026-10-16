"""Protect embedding-process streams, logging and private random state."""

import subprocess
import sys


def test_ImportAndGenerationPreserveProcessState():
    """Exercise import and generation with external launches forbidden."""

    script = '''"""Check the host-process contract in a fresh interpreter."""
import logging
import os
import random
import sys
import webbrowser
import numpy
import pandas


def RejectLaunch(*args, **kwargs):
    """Reject any attempt to launch an external process."""

    raise AssertionError("Core attempted to launch an external process")


os.system = RejectLaunch
webbrowser.open = RejectLaunch
random.seed(8128)
state = random.getstate()
streams = (sys.stdout, sys.stderr)
handlers = list(logging.getLogger().handlers)
from pricegenerator import Generate, GenerationConfig
Generate(GenerationConfig(seed=0, horizon=8))
assert (sys.stdout, sys.stderr) == streams, "Core replaced host streams"
assert random.getstate() == state, "Core consumed host random state"
assert logging.getLogger().handlers == handlers, "Core changed root logging"
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Core changed embedding process state: {result.stderr}"
