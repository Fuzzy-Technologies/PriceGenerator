"""Adapt explicit generation, replay, validation, analysis, comparison and charts."""

import argparse
import json
from pathlib import Path
from typing import Any

from pricegenerator.config import COUNT_MODEL_ID, GenerationConfig


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


def _GenerationArguments(parser: argparse.ArgumentParser) -> None:
    """Expose the same generation options for single paths and ensembles."""

    parser.add_argument("--config", type=Path, help="JSON GenerationConfig; explicit flags override fields.")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--start", help="Timezone-aware ISO timestamp.")
    parser.add_argument("--timeframe-seconds", type=int)


def _ReadConfiguration(arguments: argparse.Namespace) -> GenerationConfig:
    """Load validated configuration with explicit command-line overrides."""

    configuration = {} if arguments.config is None else _ReadJSON(arguments.config)

    if not isinstance(configuration, dict):
        raise ValueError("configuration JSON must be an object")

    for name in ("seed", "horizon", "start", "timeframe_seconds"):
        if getattr(arguments, name) is not None:
            configuration[name] = getattr(arguments, name)

    return GenerationConfig.FromDict(configuration)


def _EnsembleOutputArguments(parser: argparse.ArgumentParser) -> None:
    """Define identical report and chart destinations for generation and replay."""

    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1).")
    parser.add_argument("--output", type=Path, help="Write the JSON report here instead of stdout.")
    parser.add_argument("--chart", type=Path, help="Export path-zero candles and pointwise quantiles; choose format by suffix.")


def _Parser() -> argparse.ArgumentParser:
    """Describe the intentional v2 commands without historical flag aliases."""

    parser = argparse.ArgumentParser(prog="pricegenerator", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate canonical OHLCV from explicit reproducible inputs.")
    _GenerationArguments(generate)
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
    compare = commands.add_parser("compare", help="Compare two canonical OHLCV series at a shared interval.")
    compare.add_argument("reference", type=Path)
    compare.add_argument("synthetic", type=Path)
    compare.add_argument("--timeframe-seconds", type=int, required=True, help="Shared candle interval in whole seconds.")
    compare.add_argument("--tolerances", type=Path, help="JSON object of predeclared absolute tolerances by metric.")
    compare.add_argument("--output", type=Path, help="Write the JSON report here instead of stdout.")
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
    monte_carlo = commands.add_parser("monte-carlo", help="Summarize a reproducible synthetic path ensemble.")
    _GenerationArguments(monte_carlo)
    _EnsembleOutputArguments(monte_carlo)
    monte_carlo.add_argument("--paths", type=int, required=True)
    monte_carlo.add_argument("--manifest", type=Path, help="Save the experiment inputs and result fingerprints for replay.")
    replay_ensemble = commands.add_parser("replay-ensemble", help="Replay and verify a recorded synthetic path ensemble.")
    _EnsembleOutputArguments(replay_ensemble)
    replay_ensemble.add_argument("input", type=Path)
    replay_ensemble.add_argument("--allow-environment-change", action="store_true", help="Still require exact fingerprint equality.")

    return parser


def _Execute(arguments: argparse.Namespace) -> None:
    """Perform an already parsed operation using the public feature boundaries."""

    from pricegenerator.io import ReadCSV, WriteCSV

    if arguments.command == "generate":
        from pricegenerator.generation import Generate
        from pricegenerator.scenario import CreateManifest

        _DistinctPaths([arguments.config], [arguments.output, arguments.manifest])
        config = _ReadConfiguration(arguments)
        data = Generate(config)
        WriteCSV(data, arguments.output, volume_as_count=config.model == COUNT_MODEL_ID)

        if arguments.manifest is not None:
            _WriteJSON(CreateManifest(config, data), arguments.manifest)

    elif arguments.command == "replay":
        from pricegenerator.scenario import Replay

        _DistinctPaths([arguments.input], [arguments.output])
        manifest = _ReadJSON(arguments.input)

        if not isinstance(manifest, dict):
            raise ValueError("manifest JSON must be an object")

        data = Replay(manifest, strict_environment=not arguments.allow_environment_change)
        WriteCSV(data, arguments.output, volume_as_count=manifest["model"] == COUNT_MODEL_ID)

    elif arguments.command == "validate":
        from pricegenerator.scenario import Fingerprint

        data = ReadCSV(arguments.input, assume_timezone=arguments.timezone, timeframe_seconds=arguments.timeframe_seconds, allow_gaps=not arguments.no_gaps)
        _WriteJSON({"rows": len(data), "fingerprint": Fingerprint(data), "valid": True}, None)

    elif arguments.command == "analyze":
        from pricegenerator.analysis import Analyze

        _DistinctPaths([arguments.input], [arguments.output])
        _WriteJSON(Analyze(ReadCSV(arguments.input), acf_lags=arguments.acf_lags).ToDict(), arguments.output)

    elif arguments.command == "compare":
        from pricegenerator.evaluation import Compare

        _DistinctPaths([arguments.reference, arguments.synthetic, arguments.tolerances], [arguments.output])
        tolerances = {} if arguments.tolerances is None else _ReadJSON(arguments.tolerances)

        if not isinstance(tolerances, dict):
            raise ValueError("tolerances JSON must be an object")

        interval = arguments.timeframe_seconds
        reference = ReadCSV(arguments.reference, timeframe_seconds=interval, allow_gaps=False)
        synthetic = ReadCSV(arguments.synthetic, timeframe_seconds=interval, allow_gaps=False)

        if len(reference) < 2 or len(synthetic) < 2:
            raise ValueError("each series needs at least two candles to verify its interval")

        try:
            report = Compare(reference, synthetic, tolerances=tolerances)

        except OverflowError as error:
            raise ValueError("comparison values exceed the supported numeric range") from error

        _WriteJSON({"schema_version": 1, "timeframe_seconds": interval, **report.ToDict()}, arguments.output)

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

    elif arguments.command == "monte-carlo":
        from pricegenerator.monte_carlo import ChartEnsemble, CreateEnsembleManifest, RunEnsemble

        _DistinctPaths([arguments.config], [arguments.output, arguments.manifest, arguments.chart])
        report = RunEnsemble(_ReadConfiguration(arguments), path_count=arguments.paths, workers=arguments.workers)

        if arguments.chart is not None:
            ChartEnsemble(report, arguments.chart)

        if arguments.manifest is not None:
            _WriteJSON(CreateEnsembleManifest(report), arguments.manifest)

        _WriteJSON(report.ToDict(), arguments.output)

    elif arguments.command == "replay-ensemble":
        from pricegenerator.monte_carlo import ChartEnsemble, ReplayEnsemble

        _DistinctPaths([arguments.input], [arguments.output, arguments.chart])
        report = ReplayEnsemble(
            _ReadJSON(arguments.input), workers=arguments.workers,
            strict_environment=not arguments.allow_environment_change,
        )

        if arguments.chart is not None:
            ChartEnsemble(report, arguments.chart)

        _WriteJSON(report.ToDict(), arguments.output)


def Main(argv: list[str] | None = None) -> int:
    """Run a v2 command and report expected input or I/O errors through argparse."""

    parser = _Parser()
    arguments = parser.parse_args(argv)

    try:
        _Execute(arguments)

    except (ValueError, TypeError, OSError, ImportError) as error:
        parser.error(str(error))

    return 0
