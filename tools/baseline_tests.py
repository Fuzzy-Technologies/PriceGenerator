"""Run installed legacy-package tests in a disposable directory, with real dependencies."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


SMOKE_CODE = '''"""Inspect the installed package without importing from the checkout."""
import importlib.metadata
import json
import platform
import sys

original_stderr = sys.stderr
from pricegenerator import PriceGenerator
sys.stderr = original_stderr

print(json.dumps({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "module_path": PriceGenerator.__file__,
    "packages": {
        name: importlib.metadata.version(name)
        for name in ["pricegenerator", "numpy", "pandas", "pandas-ta", "bokeh", "pytest"]
    },
}))
'''

PYTEST_CODE = '''"""Seed the unmodified historical tests before their normal collection."""
import random
import sys
import pytest

random.seed(0)
raise SystemExit(pytest.main(sys.argv[1:]))
'''


def RunBaseline(repository, report_path=None):
    """Exercise the installed package and remove every legacy file output afterwards."""

    repository = Path(repository).resolve()
    tests = ["test_PriceGenerator.py", "legacy_harness.py", "legacy_cases.json", "legacy_indicators.json", "test_legacy_baseline.py", "AFLT_day.csv", "test_template.j2"]

    with tempfile.TemporaryDirectory(prefix="pricegenerator-baseline-") as temporary:
        working = Path(temporary)
        (working / "tests").mkdir()

        for name in tests:
            shutil.copy2(repository / "tests" / name, working / "tests" / name)

        smoke = subprocess.run(
            [sys.executable, "-I", "-c", SMOKE_CODE], cwd=working,
            text=True, capture_output=True, check=True,
        )
        runtime = json.loads(smoke.stdout)
        module_path = Path(runtime["module_path"]).resolve()

        if module_path.is_relative_to(repository):
            raise RuntimeError("Clean-install smoke imported the source checkout")

        command = [
            sys.executable, "-I", "-c", PYTEST_CODE, "-q",
            "tests/test_PriceGenerator.py", "tests/test_legacy_baseline.py",
            "-rxX", "--junitxml=baseline-results.xml",
        ]
        completed = subprocess.run(command, cwd=working, text=True, capture_output=True, check=False)
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        report = {
            "schema_version": 1, "runtime": runtime,
            "legacy_rng_seed": 0, "pytest_exit_code": completed.returncode,
            "command": command,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }
        junit_path = working / "baseline-results.xml"

        if junit_path.exists():
            suites = ET.parse(junit_path).getroot().findall("testsuite")
            report["suites"] = [dict(suite.attrib) for suite in suites]
            report["testcases"] = [
                {"name": case.attrib["name"], "class": case.attrib.get("classname"),
                 "outcome": "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"}
                for suite in suites for case in suite.findall("testcase")
            ]

        if report_path is not None:
            report_path = Path(report_path).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        return completed.returncode


def Main():
    """Run the repository's legacy evidence command using the active environment."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()

    return RunBaseline(arguments.repository, arguments.report)


if __name__ == "__main__":
    raise SystemExit(Main())
