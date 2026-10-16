"""Adapt explicit generation, validation, analysis, replay and chart operations."""

import argparse
import json
from pathlib import Path
from typing import Any

from pricegenerator.config import GenerationConfig


def _JSONPairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON members instead of silently replacing input values."""

    result = {}

    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON object member: {name}")

        result[name] = value

    return result


def _JSONConstant(value: str) -> None:
    """Reject nonstandard JSON floating constants before configuration handling."""

    raise ValueError(f"Nonstandard JSON constant: {value}")


def _ReadJSON(path: Path) -> Any:
    """Read strict JSON inputs with no duplicate members or nonfinite constants."""

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_JSONPairs, parse_constant=_JSONConstant)


def _DistinctPaths(inputs: list[Path | None], outputs: list[Path | None]) -> None:
    """Prevent adapters from overwriting inputs or two outputs sharing one file."""

    sources = [path.resolve() for path in inputs if path is not None]
    destinations = [path.resolve() for path in outputs if path is not None]

    for index, destination in enumerate(destinations):
        for previous in [*sources, *destinations[:index]]:
            if destination == previous or (destination.exists() and previous.exists() and destination.samefile(previous)):
                raise ValueError("output paths must be distinct and must not overwrite any input")


def _WriteJSON(value: Any, destination: Path | None) -> None:
    """Serialize standard JSON to the requested output or standard output."""

    serialized = json.dumps(value, indent=2, allow_nan=False) + "\n"

    if destination is None:
        print(serialized, end="")

    else:
        destination.write_text(serialized, encoding="utf-8")


def _Parser() -> argparse.ArgumentParser:
    """Describe the intentional v2 commands without historical flag aliases."""

    parser = argparse.ArgumentParser(prog="pricegenerator", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate canonical OHLCV from explicit reproducible inputs.")
    generate.add_argument("--config", type=Path, help="JSON GenerationConfig; explicit flags override fields.")
    generate.add_argument("--seed", type=int)
    generate.add_argument("--horizon", type=int)
    generate.add_argument("--start", help="Timezone-aware ISO timestamp.")
    generate.add_argument("--timeframe-seconds", type=int)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--manifest", type=Path)
    replay = commands.add_parser("replay", help="Verify a manifest and reproduce canonical OHLCV.")
    replay.add_argument("input", type=Path)
    replay.add_argument("--output", type=Path, required=True)
    replay.add_argument("--allow-environment-change", action="store_true", help="Still require exact fingerprint equality.")
    validate = commands.add_parser("validate", help="Validate canonical CSV and print structural evidence.")
    validate.add_argument("input", type=Path)
    validate.add_argument("--timezone", help="Explicit timezone for imported naive timestamps.")
    validate.add_argument("--timeframe-seconds", type=int)
    validate.add_argument("--no-gaps", action="store_true")
    analyze = commands.add_parser("analyze", help="Calculate nonmutating diagnostics for canonical CSV.")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output", type=Path)
    analyze.add_argument("--acf-lags", type=int, default=10)
    chart = commands.add_parser("chart", help="Render canonical CSV with the optional chart adapter.")
    chart.add_argument("input", type=Path)
    chart.add_argument("--output", type=Path)
    chart.add_argument("--format", choices=("html", "svg", "png", "jpeg"))
    view = chart.add_mutually_exclusive_group()
    view.add_argument("--view", dest="view", action="store_true")
    view.add_argument("--no-view", dest="view", action="store_false")
    chart.set_defaults(view=None)
    chart.add_argument("--analysis", action="store_true", help="Attach statistics and financial indicator overlays.")
    chart.add_argument("--title", default="PriceGenerator")
    chart.add_argument("--theme", choices=("dark", "light"), default="dark")
    chart.add_argument("--width", type=int, default=1280)
    chart.add_argument("--height", type=int, default=760)
    chart.add_argument("--quality", type=int, default=90)
    chart.add_argument("--line", type=Path, action="append", default=[])
    chart.add_argument("--markers", type=Path)
    chart.add_argument("--summary", action="append", default=[])
    chart.add_argument("--report", type=Path)

    return parser


def _Execute(arguments: argparse.Namespace) -> None:
    """Perform an already parsed operation using the public feature boundaries."""

    from pricegenerator.io import ReadCSV, WriteCSV

    if arguments.command == "generate":
        from pricegenerator.generation import Generate
        from pricegenerator.scenario import CreateManifest

        _DistinctPaths([arguments.config], [arguments.output, arguments.manifest])
        configuration = {} if arguments.config is None else _ReadJSON(arguments.config)

        if not isinstance(configuration, dict):
            raise ValueError("configuration JSON must be an object")

        for name in ("seed", "horizon", "start", "timeframe_seconds"):
            if getattr(arguments, name) is not None:
                configuration[name] = getattr(arguments, name)

        config = GenerationConfig.FromDict(configuration)
        data = Generate(config)
        WriteCSV(data, arguments.output)

        if arguments.manifest is not None:
            _WriteJSON(CreateManifest(config, data), arguments.manifest)

    elif arguments.command == "replay":
        from pricegenerator.scenario import Replay

        _DistinctPaths([arguments.input], [arguments.output])
        manifest = _ReadJSON(arguments.input)

        if not isinstance(manifest, dict):
            raise ValueError("manifest JSON must be an object")

        WriteCSV(Replay(manifest, strict_environment=not arguments.allow_environment_change), arguments.output)

    elif arguments.command == "validate":
        from pricegenerator.scenario import Fingerprint

        data = ReadCSV(arguments.input, assume_timezone=arguments.timezone, timeframe_seconds=arguments.timeframe_seconds, allow_gaps=not arguments.no_gaps)
        _WriteJSON({"rows": len(data), "fingerprint": Fingerprint(data), "valid": True}, None)

    elif arguments.command == "analyze":
        from pricegenerator.analysis import Analyze

        _DistinctPaths([arguments.input], [arguments.output])
        _WriteJSON(Analyze(ReadCSV(arguments.input), acf_lags=arguments.acf_lags).ToDict(), arguments.output)

    elif arguments.command == "chart":
        import pandas as pd

        from pricegenerator.rendering.api import Chart

        _DistinctPaths([arguments.input, arguments.markers, *arguments.line], [arguments.output, arguments.report])
        options: dict[str, Any] = {
            "title": arguments.title, "theme": arguments.theme, "width": arguments.width, "height": arguments.height,
            "analysis": arguments.analysis,
        }

        if arguments.line:
            options["lines"] = [pd.read_csv(path) for path in arguments.line]

        if arguments.markers is not None:
            options["markers"] = pd.read_csv(arguments.markers, keep_default_na=False, dtype=str)

        if arguments.summary:
            options["summary"] = tuple(arguments.summary)

        if arguments.report is not None:
            options["markdown_report"] = arguments.report

        Chart(ReadCSV(arguments.input), arguments.output, format=arguments.format, view=arguments.view, quality=arguments.quality, **options)


def Main(argv: list[str] | None = None) -> int:
    """Run a v2 command and report expected input or I/O errors through argparse."""

    parser = _Parser()
    arguments = parser.parse_args(argv)

    try:
        _Execute(arguments)

    except (ValueError, TypeError, OSError, ImportError) as error:
        parser.error(str(error))

    return 0
