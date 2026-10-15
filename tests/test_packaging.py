"""Verify package metadata and smoke installed artifacts outside the checkout."""

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
from importlib import metadata, resources, util
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_MODULES = ("bokeh", "jinja2", "pandas_ta", "pandas_ta_classic", "notebook", "IPython")


def ReadProjectMetadata():
    """Read metadata in test environments across supported Python versions."""

    try:
        import tomllib

    except ModuleNotFoundError:
        import tomli as tomllib

    return tomllib.loads((SOURCE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_CanonicalVersionIsLiteralAndShared():
    """Keep builds deterministic without importing optional or runtime code."""

    from pricegenerator import __version__

    tree = ast.parse((SOURCE_ROOT / "pricegenerator/_version.py").read_text(encoding="utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    assert len(assignments) == 1, "Version source must contain one deterministic assignment"
    assert assignments[0].targets[0].id == "__version__", "Build and runtime version names diverged"
    assert ast.literal_eval(assignments[0].value) == __version__, "Runtime version differs from canonical source"
    configuration = ReadProjectMetadata()
    assert configuration["project"]["dynamic"] == ["version"], "Package version must use the canonical source"
    assert configuration["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "pricegenerator._version.__version__",
    }, "Setuptools does not read the canonical version literal"
    assert "TRAVIS" not in (SOURCE_ROOT / "setup.py").read_text(), "Legacy environment-derived versions returned"


def test_CoreMetadataExcludesOptionalAndUnusedDependencies():
    """Keep production generation requirements separate from tooling and legacy charts."""

    project = ReadProjectMetadata()["project"]
    core_names = {re.split(r"[<>=!~ ]", requirement, maxsplit=1)[0] for requirement in project["dependencies"]}
    assert core_names == {"numpy", "pandas", "python-dateutil"}, "Core dependency boundary changed unexpectedly"
    assert {"render", "indicators", "notebook", "test", "docs", "release", "dev"} <= set(
        project["optional-dependencies"],
    ), "An optional workflow has no documented extra"
    assert "bkcharts" not in json.dumps(project), "Obsolete bkcharts was reintroduced"
    assert all("Fuzzy-Technologies/PriceGenerator" in url for url in project["urls"].values()), (
        "Active package metadata still points to the historical personal repository"
    )


def test_PythonMetadataMatchesTestedRuntimeWindow():
    """Keep the compatibility promise explicit instead of inheriting unsupported runtimes."""

    project = ReadProjectMetadata()["project"]
    assert project["requires-python"] == ">=3.10,<3.14", "Runtime support changed without matrix evidence"

    for minor in range(10, 14):
        assert f"Programming Language :: Python :: 3.{minor}" in project["classifiers"], (
            f"Python 3.{minor} classifier is missing from the supported matrix"
        )


def SmokeInstalledArtifact(mode):
    """Check installed metadata, resources, CLI, generation and the requested extra set."""

    import pricegenerator
    from pricegenerator import PriceGenerator

    package_path = Path(pricegenerator.__file__).resolve()
    assert not package_path.is_relative_to(SOURCE_ROOT), "Smoke imported the source checkout instead of the installed artifact"
    assert metadata.version("pricegenerator") == pricegenerator.__version__, "Installed distribution and runtime versions differ"
    assert resources.files("pricegenerator").joinpath("google_template_example.j2").is_file(), (
        "Installed package is missing its legacy template resource"
    )
    source_assets = SOURCE_ROOT / "pricegenerator/rendering/assets"

    if source_assets.is_dir():
        installed_assets = resources.files("pricegenerator.rendering").joinpath("assets")

        for source_file in source_assets.rglob("*"):
            if source_file.is_file():
                resource = installed_assets.joinpath(*source_file.relative_to(source_assets).parts)
                assert resource.is_file(), f"Installed renderer resource is missing: {source_file.name}"
                assert resource.read_bytes() == source_file.read_bytes(), (
                    f"Installed renderer resource differs from reviewed source: {source_file.name}"
                )

    model = PriceGenerator.PriceGenerator()
    model.horizon = 240
    prices = model.Generate()
    assert len(prices) == 240, "Installed generation did not return the configured horizon"
    assert list(prices) == model.dfHeaders, "Installed generation changed legacy OHLCV columns"

    with tempfile.TemporaryDirectory() as temporary:
        output_directory = Path(temporary)
        for command in ([sys.executable, "-m", "pricegenerator", "--help"],
                        [str(Path(sys.executable).with_name("pricegenerator")), "--help"]):
            result = subprocess.run(command, cwd=temporary, capture_output=True, text=True, check=False)
            assert result.returncode == 0, f"Installed CLI entry point failed: {result.stderr}"
            assert "--generate" in result.stdout, "Installed CLI help lost the generation command"

        output_file = output_directory / "generated.csv"
        result = subprocess.run(
            [sys.executable, "-m", "pricegenerator", "--generate", "--horizon", "8", "--save-to", str(output_file)],
            cwd=temporary, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"Installed CLI generation failed: {result.stderr}"
        assert len(output_file.read_text().splitlines()) == 8, "Installed CLI failed to write eight CSV rows"

        if mode == "core":
            for name in OPTIONAL_MODULES:
                assert util.find_spec(name) is None, f"Core environment unexpectedly installed optional module {name}"

            try:
                model.GetStatistics()

            except ImportError as error:
                assert "pricegenerator[indicators]" in str(error), "Core install lacks actionable indicator guidance"

            else:
                raise AssertionError("Core installed artifact unexpectedly loaded indicators")

        else:
            for name in ("bokeh", "jinja2", "pandas_ta_classic"):
                assert util.find_spec(name) is not None, f"Requested extras did not install {name}"

            assert model.GetStatistics(), "Installed indicator integration returned no statistics"
            model.RenderBokeh(fileName=str(output_directory / "bokeh.html"), viewInBrowser=False)
            model.RenderGoogle(fileName=str(output_directory / "google.html"), viewInBrowser=False)
            assert (output_directory / "bokeh.html").stat().st_size > 1000, "Installed Bokeh rendering produced no chart"
            assert (output_directory / "google.html").stat().st_size > 1000, "Installed Google rendering produced no chart"

    print(json.dumps({"version": pricegenerator.__version__, "python": sys.version.split()[0], "mode": mode, "package": str(package_path)}))


def Main():
    """Run the installed-wheel smoke with no pytest or build dependencies."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("core", "extras"))
    arguments = parser.parse_args()
    SmokeInstalledArtifact(arguments.mode)


if __name__ == "__main__":
    Main()
