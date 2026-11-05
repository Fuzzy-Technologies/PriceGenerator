"""Run the same source quality checks locally and in GitHub Actions."""

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def Run(*arguments: str) -> None:
    """Run one Python module from the repository root and propagate failures."""

    command = (sys.executable, "-m", *arguments)
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def Main() -> None:
    """Validate all maintained Python and run focused or full tests."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tests", nargs="*", help="Optional pytest paths or node IDs")
    parser.add_argument("--reports", type=Path, help="Write test and coverage reports to this directory")
    arguments = parser.parse_args()
    reports = arguments.reports

    if reports is not None:
        reports = reports.resolve()
        reports.mkdir(parents=True, exist_ok=True)

    Run("compileall", "-q", "pricegenerator", "tools", "tests")
    Run("ruff", "check", "--config", "pyproject.toml", "pricegenerator", "tools", "tests")
    Run("tools.markdown_tables")
    Run("tools.documentation_links")

    if arguments.tests:
        Run("pytest", "-q", *arguments.tests)

        return

    lifecycle_reports = (f"--junitxml={reports / 'lifecycle.xml'}",) if reports else ()
    Run("pytest", "-q", "tests/test_pr_merge_links.py", "--cov=tools.pr_merge_links",
        "--cov-branch", "--cov-fail-under=95", "--cov-report=term-missing", *lifecycle_reports)

    suite_reports = (
        f"--junitxml={reports / 'package-tests.xml'}",
        f"--cov-report=json:{reports / 'coverage.json'}",
    ) if reports else ()
    Run("pytest", "-q", "tests", "--cov=pricegenerator", "--cov-branch",
        "--cov-fail-under=90", "--cov-report=term-missing", *suite_reports)


if __name__ == "__main__":
    Main()
