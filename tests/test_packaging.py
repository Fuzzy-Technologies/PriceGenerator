"""Verify modern metadata and installed artifacts without checkout imports."""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from html import unescape
from importlib import metadata, resources, util
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

SOURCE_ROOT = Path(__file__).resolve().parents[1]
OBSOLETE_MODULES = ("bokeh", "jinja2", "pandas_ta", "pandas_ta_classic", "bkcharts")
OPTIONAL_MODULES = ("resvg_py", "PIL", "notebook", "IPython")


def ReadProjectMetadata():
    """Read canonical metadata on every supported interpreter."""

    try:
        import tomllib

    except ModuleNotFoundError:
        import tomli as tomllib

    return tomllib.loads((SOURCE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_CanonicalVersionIsLiteralAndShared():
    """Keep deterministic build metadata separate from runtime imports."""

    from pricegenerator import __version__

    tree = ast.parse((SOURCE_ROOT / "pricegenerator/_version.py").read_text(encoding="utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    assert len(assignments) == 1, "Version source must contain one deterministic assignment"
    assert assignments[0].targets[0].id == "__version__", "Canonical version name changed"
    assert ast.literal_eval(assignments[0].value) == __version__, "Runtime version differs from build source"
    configuration = ReadProjectMetadata()
    assert configuration["project"]["dynamic"] == ["version"], "Version must come from canonical source"
    assert configuration["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "pricegenerator._version.__version__",
    }, "Setuptools must read the canonical version literal"
    assert "TRAVIS" not in (SOURCE_ROOT / "setup.py").read_text(), "Environment-derived version returned"


def test_CoreMetadataExcludesObsoleteDependencies():
    """Keep modern runtime independent of former render and indicator backends."""

    project = ReadProjectMetadata()["project"]
    core_names = {re.split(r"[<>=!~ ]", requirement, maxsplit=1)[0] for requirement in project["dependencies"]}
    assert core_names == {"numpy", "pandas", "python-dateutil"}, "Core dependency boundary changed"
    assert {"export", "notebook", "test", "docs", "release", "dev"} <= set(project["optional-dependencies"]), (
        "Documented optional workflow is missing"
    )
    assert not {"render", "indicators"} & set(project["optional-dependencies"]), "Legacy extras returned"
    serialized = json.dumps(project).lower()

    for name in ("bokeh", "jinja2", "pandas-ta", "bkcharts"):
        assert name not in serialized, f"Obsolete dependency returned: {name}"

    assert project["scripts"] == {"pricegenerator": "pricegenerator.cli:Main"}, "CLI must use the modern entry point"
    assert all("Fuzzy-Technologies/PriceGenerator" in url for url in project["urls"].values()), (
        "Active metadata still points to the historical personal repository"
    )


def test_PythonMetadataMatchesMatrix():
    """Require explicit metadata for the Python versions checked by CI."""

    project = ReadProjectMetadata()["project"]
    assert project["requires-python"] == ">=3.10,<3.14", "Runtime window changed without matrix evidence"

    for minor in range(10, 14):
        assert f"Programming Language :: Python :: 3.{minor}" in project["classifiers"], "Supported classifier missing"


def SmokeInstalledCharts(output_directory, mode):
    """Render SVG, self-contained HTML and optional actual raster exports."""

    from pricegenerator.rendering import ChartCandle, ChartSpec, RenderSVG, SaveSVG
    from pricegenerator.rendering.interactive import RenderInteractive, SaveInteractive

    spec = ChartSpec((
        ChartCandle("2026-01-01T00:00:00Z", 10, 13, 9, 12, 100),
        ChartCandle("2026-01-01T01:00:00Z", 12, 13, 10, 11, 120),
        ChartCandle("2026-01-01T02:00:00Z", 11, 14, 10, 13, 150),
    ), title="Installed artifact <offline>")
    svg = RenderSVG(spec)
    root = ElementTree.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg", "Installed renderer did not produce SVG"
    assert len(root.findall('.//{http://www.w3.org/2000/svg}g[@data-candle-index]')) == 3, "SVG lost candles"
    assert "data:image/png;base64," in svg, "SVG lost the embedded corporate logo"
    svg_path = output_directory / "api chart.svg"
    assert SaveSVG(spec, svg_path) == svg_path, "SaveSVG lost its destination"
    assert svg_path.read_text(encoding="utf-8") == svg, "SaveSVG changed its document"
    html = RenderInteractive(spec)
    assert "PriceGeneratorView.Mount" in html, "HTML lost its offline runtime"
    assert "data:image/png;base64," in html, "HTML lost embedded corporate logo"
    asset_root = resources.files("pricegenerator.rendering").joinpath("assets", "echarts")
    runtime = asset_root.joinpath("echarts-financial.min.js").read_bytes()
    build = json.loads(asset_root.joinpath("build.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(runtime).hexdigest() == build["sha256"], "Installed runtime hash differs from build record"

    for name in ("NOTICE.txt", "LICENSE-APACHE-2.0.txt", "LICENSE-ZRENDER-BSD-3.txt", "LICENSE-TSLIB-0BSD.txt"):
        notice = asset_root.joinpath(name).read_text(encoding="utf-8")
        assert notice in unescape(html), f"Generated HTML lost notice: {name}"

    html_path = output_directory / "api chart.html"
    assert SaveInteractive(spec, html_path) == html_path, "SaveInteractive lost its destination"
    assert html_path.read_text(encoding="utf-8") == html, "SaveInteractive changed its document"

    if mode == "export":
        from PIL import Image
        from pricegenerator.rendering import RenderJPEG, RenderPNG, SaveJPEG, SavePNG

        for extension, render, save, image_format in (
            ("png", RenderPNG, SavePNG, "PNG"), ("jpg", RenderJPEG, SaveJPEG, "JPEG"),
        ):
            content = render(spec)
            destination = output_directory / f"api chart.{extension}"
            assert save(spec, destination) == destination, "Raster saver lost destination"
            assert destination.read_bytes() == content, "Raster save differs from API bytes"

            with Image.open(BytesIO(content)) as image:
                image.load()
                assert image.format == image_format, "Raster export has incorrect encoding"
                assert image.width > 100 and image.height > 100, "Raster export dimensions are empty"
                extrema = image.convert("RGB").getextrema()
                assert any(low < high for low, high in extrema), "Raster export is a blank image"


def SmokeInstalledArtifact(mode):
    """Exercise public API, CLI, replay and packaged resources in isolation."""

    import pricegenerator
    from pricegenerator import Generate, GenerationConfig, ReadCSV, ValidateOHLCV, WriteCSV

    package_path = Path(pricegenerator.__file__).resolve()
    assert not package_path.is_relative_to(SOURCE_ROOT), "Smoke imported source instead of installed artifact"
    assert metadata.version("pricegenerator") == pricegenerator.__version__, "Metadata and runtime versions differ"
    distribution = metadata.distribution("pricegenerator")
    files = [str(path) for path in distribution.files or ()]
    licenses = [path for path in files if path.endswith(".dist-info/licenses/LICENSE")]
    assert len(licenses) == 1, "Wheel lost Apache license"
    assert Path(distribution.locate_file(licenses[0])).read_bytes() == (SOURCE_ROOT / "LICENSE").read_bytes(), (
        "Installed Apache license differs from reviewed source"
    )
    assert not any(path.endswith(".j2") for path in files), "Wheel contains retired legacy templates"
    source_assets = SOURCE_ROOT / "pricegenerator/rendering/assets"
    assert source_assets.is_dir(), "Expected reviewed assets are missing from source distribution"
    installed_assets = resources.files("pricegenerator.rendering").joinpath("assets")

    for source_file in source_assets.rglob("*"):
        if source_file.is_file():
            resource = installed_assets.joinpath(*source_file.relative_to(source_assets).parts)
            assert resource.is_file(), f"Installed resource missing: {source_file.name}"
            assert resource.read_bytes() == source_file.read_bytes(), f"Installed resource changed: {source_file.name}"

    prices = Generate(GenerationConfig(seed=0, horizon=8))
    ValidateOHLCV(prices)
    assert len(prices) == 8, "Installed generation ignored requested horizon"
    assert list(prices) == ["datetime", "open", "high", "low", "close", "volume"], "Canonical columns changed"

    with tempfile.TemporaryDirectory() as temporary:
        output_directory = Path(temporary)
        api_csv = output_directory / "api.csv"
        WriteCSV(prices, api_csv)
        assert len(ReadCSV(api_csv)) == 8, "Installed CSV round trip lost rows"
        commands = ([sys.executable, "-I", "-m", "pricegenerator"],
                    [str(Path(sys.executable).with_name("pricegenerator"))])

        for command in commands:
            result = subprocess.run([*command, "--help"], cwd=temporary, capture_output=True, text=True, check=False)
            assert result.returncode == 0, f"Installed CLI entry point failed: {result.stderr}"
            assert "generate" in result.stdout and "replay" in result.stdout, "Modern CLI commands are missing"

        cli_csv = output_directory / "cli.csv"
        manifest = output_directory / "scenario.json"
        replay_csv = output_directory / "replay.csv"
        commands = [
            ["generate", "--seed", "0", "--horizon", "8", "--output", str(cli_csv), "--manifest", str(manifest)],
            ["replay", str(manifest), "--output", str(replay_csv)],
            ["chart", str(cli_csv), "--output", str(output_directory / "cli.html"), "--no-view"],
        ]

        for arguments in commands:
            result = subprocess.run([sys.executable, "-I", "-m", "pricegenerator", *arguments],
                                    cwd=temporary, capture_output=True, text=True, check=False)
            assert result.returncode == 0, f"Installed CLI failed: {arguments}: {result.stderr}"

        assert len(ReadCSV(cli_csv)) == 8, "CLI generation lost rows"
        assert cli_csv.read_bytes() == replay_csv.read_bytes(), "Manifest replay changed generated candles"
        assert "PriceGeneratorView.Mount" in (output_directory / "cli.html").read_text(), "CLI HTML runtime missing"
        SmokeInstalledCharts(output_directory, mode)

    for name in OBSOLETE_MODULES:
        assert util.find_spec(name) is None, f"Modern artifact installed obsolete backend {name}"

    if mode == "core":
        for name in OPTIONAL_MODULES:
            assert util.find_spec(name) is None, f"Core installation pulled optional dependency {name}"

    print(json.dumps({"version": pricegenerator.__version__, "python": sys.version.split()[0],
                      "mode": mode, "package": str(package_path)}))


def Main():
    """Run artifact verification with only the requested runtime dependencies."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("core", "export"))
    arguments = parser.parse_args()
    SmokeInstalledArtifact(arguments.mode)


if __name__ == "__main__":
    Main()
