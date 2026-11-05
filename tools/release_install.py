"""Check wheel and sdist in separate clean environments outside the checkout."""

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODES = ("core", "export")


def Run(arguments, directory):
    """Execute an auditable command without inherited import overrides."""

    environment = {name: value for name, value in os.environ.items() if name not in ("PYTHONPATH", "PYTHONHOME")}
    print("+", " ".join(map(str, arguments)), flush=True)
    subprocess.run(list(map(str, arguments)), cwd=directory, env=environment, check=True)


def Verify(artifact, modes=DEFAULT_MODES):
    """Install the requested artifact modes and run the public APIs."""

    with tempfile.TemporaryDirectory(prefix="pricegenerator-artifact-") as temporary:
        directory = Path(temporary)
        environment = directory / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        constraints = SOURCE_ROOT / "requirements/modern.txt"
        smoke = SOURCE_ROOT / "tests/test_packaging.py"

        for mode in modes:
            requirement = artifact if mode == "core" else f"{artifact}[{mode}]"
            Run([python, "-m", "pip", "install", "-c", constraints, requirement], directory)
            Run([python, "-I", smoke, mode], directory)

        Run([python, "-m", "pip", "check"], directory)
        Run([python, "-m", "pip", "freeze"], directory)


def Main():
    """Verify both distribution formats under the selected interpreter."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--fuzzy", action="store_true", help="Verify the scalar fuzzy extra on Python 3.13.")
    arguments = parser.parse_args()
    artifacts = sorted(arguments.directory.resolve().glob("*.whl")) + sorted(arguments.directory.resolve().glob("*.tar.gz"))

    if len(artifacts) != 2:
        parser.error("Expected exactly one wheel and one sdist")

    modes = ("fuzzy",) if arguments.fuzzy else DEFAULT_MODES

    for artifact in artifacts:
        Verify(artifact, modes)

    print(f"Verified {'/'.join(modes)} wheel and sdist with Python {sys.version.split()[0]}")


if __name__ == "__main__":
    Main()
