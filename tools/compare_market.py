"""Compare a declared market-data window with an explicit, unfitted v2 scenario."""

import argparse
import csv
from datetime import datetime
import hashlib
from io import StringIO
from importlib import import_module, metadata
import json
from pathlib import Path
import re
import shlex
import sys

import pandas as pd

from pricegenerator.config import GenerationConfig
from pricegenerator.evaluation import Compare
from pricegenerator.generation import Generate
from pricegenerator.io import NUMBER_PATTERN, ReadCSV
from pricegenerator.market_data import ISO_DATETIME_PATTERN, OHLCV_COLUMNS, ValidateOHLCV
from pricegenerator.scenario import CreateManifest, Fingerprint


AFLT_DATE_PATTERN = re.compile(r"\d{4}\.\d{2}\.\d{2}\Z")
AFLT_TIME_PATTERN = re.compile(r"\d{2}:\d{2}(?::\d{2})?\Z")
SELECTED_DISTRIBUTIONS = ("simple_returns", "log_returns", "body_fraction", "upper_wick_fraction", "lower_wick_fraction", "range", "volume")


def _WindowBound(value):
    """Require an explicit-offset ISO timestamp without guessing a timezone."""

    if value is None:
        return None

    if not isinstance(value, str) or ISO_DATETIME_PATTERN.fullmatch(value) is None:
        raise ValueError("window bounds must be ISO timestamps with explicit timezone offsets")

    try:
        timestamp = pd.Timestamp(value)

        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError("window bounds require an explicit timezone")

        return timestamp.tz_convert("UTC").as_unit("ns")

    except (TypeError, OverflowError) as error:
        raise ValueError("window bound is outside the supported timestamp domain") from error


def _AFLTFrame(text: str, timezone: str | None):
    """Convert only the explicit seven-column AFLT fixture format to canonical OHLCV."""

    if not isinstance(timezone, str) or not timezone:
        raise ValueError("aflt-day requires an explicit --timezone; the file contains no timezone metadata")

    rows = []

    try:
        for line_number, row in enumerate(csv.reader(StringIO(text), strict=True), start=1):
            if len(row) != 7:
                raise ValueError(f"AFLT row {line_number} must have date,time,open,high,low,close,volume")

            if AFLT_DATE_PATTERN.fullmatch(row[0]) is None or AFLT_TIME_PATTERN.fullmatch(row[1]) is None:
                raise ValueError(f"AFLT row {line_number} requires YYYY.MM.DD and HH:MM[:SS]")

            if any(NUMBER_PATTERN.fullmatch(value) is None for value in row[2:]):
                raise ValueError(f"AFLT row {line_number} contains an invalid numeric field")

            time_format = "%H:%M:%S" if row[1].count(":") == 2 else "%H:%M"
            instant = datetime.strptime(f"{row[0]} {row[1]}", f"%Y.%m.%d {time_format}")
            rows.append([instant, *(float(value) for value in row[2:])])

    except csv.Error as error:
        raise ValueError("AFLT input is not valid comma-separated text") from error

    return ValidateOHLCV(pd.DataFrame(rows, columns=OHLCV_COLUMNS), assume_timezone=timezone)


def _TimezoneEnvironment() -> dict:
    """Record installed timezone rule packages alongside the explicit assumption."""

    versions = {"pandas": pd.__version__}

    for name in ("pytz", "tzdata"):
        try:
            versions[name] = metadata.version(name)

        except metadata.PackageNotFoundError:
            versions[name] = None

    return versions


def LoadReference(source, *, format: str = "canonical", timezone: str | None = None,
                  start: str | None = None, end: str | None = None):
    """Read exactly the hashed source bytes and select an inclusive UTC window."""

    path = Path(source)
    raw = path.read_bytes()
    text = raw.decode("utf-8")

    if format == "canonical":
        full = ReadCSV(StringIO(text), assume_timezone=timezone)

    elif format == "aflt-day":
        full = _AFLTFrame(text, timezone)

    else:
        raise ValueError("reference format must be canonical or aflt-day")

    if full.empty:
        raise ValueError("reference data must contain at least one candle")

    lower = _WindowBound(start)
    upper = _WindowBound(end)

    if lower is not None and upper is not None and lower > upper:
        raise ValueError("reference window start must not be after end")

    selected = pd.Series(True, index=full.index)

    if lower is not None:
        selected &= full.datetime >= lower

    if upper is not None:
        selected &= full.datetime <= upper

    positions = full.index[selected]
    frame = full.loc[selected].reset_index(drop=True)

    if frame.empty:
        raise ValueError("the requested reference window contains no candles")

    provenance = {
        "path": path.as_posix(), "file_sha256": hashlib.sha256(raw).hexdigest(),
        "format": format, "assume_timezone": timezone,
        "timezone_rules_environment": _TimezoneEnvironment(),
        "total_source_rows": len(full), "selected_rows": len(frame),
        "selected_row_positions_zero_based_inclusive": [int(positions[0]), int(positions[-1])],
        "source_start_utc": full.datetime.iloc[0].isoformat(),
        "source_end_utc": full.datetime.iloc[-1].isoformat(),
        "window": {
            "requested_start_utc": lower.isoformat() if lower is not None else None,
            "requested_end_utc": upper.isoformat() if upper is not None else None,
            "closure": "both", "actual_start_utc": frame.datetime.iloc[0].isoformat(),
            "actual_end_utc": frame.datetime.iloc[-1].isoformat(),
        },
        "canonical_fingerprint": Fingerprint(frame),
        "source_limit": "Caller-supplied data; venue, instrument identity, volume units and price-adjustment policy were not independently verified",
        "timestamp_policy": "Preserve observed rows and gaps; timezone is caller-supplied, not inferred from the instrument or filename",
    }

    return frame, provenance


def _SelectedAnalysis(analysis: dict) -> dict:
    """Retain distribution and temporal diagnostics without observation-sized vectors."""

    result = {key: analysis[key] for key in ("candle_count", "cadence_regular", "path", "maximum_drawdown",
                                             "maximum_drawdown_duration_bars", "up_candle_fraction", "zero_volume_fraction",
                                             "volume_absolute_return_correlation", "volume_range_correlation", "notes")}
    result["distributions"] = [value for value in analysis["distributions"] if value["name"] in SELECTED_DISTRIBUTIONS]

    for key in ("return_acf", "absolute_return_acf", "squared_return_acf"):
        result[key] = analysis[key]

    return result


def _ImplementationSources() -> dict:
    """Hash explicitly used implementation modules rather than the whole directory."""

    sources = {"tools.compare_market": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    for name in ("analysis", "config", "evaluation", "generation", "io", "market_data", "models", "scenario"):
        module = import_module(f"pricegenerator.{name}")
        sources[f"pricegenerator.{name}"] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()

    return sources


def BuildComparison(source, *, config: GenerationConfig | None = None, tolerances=None,
                    format: str = "canonical", timezone: str | None = None,
                    start: str | None = None, end: str | None = None) -> dict:
    """Generate once from explicit inputs and compare without fitting or resampling."""

    reference, provenance = LoadReference(source, format=format, timezone=timezone, start=start, end=end)
    config = GenerationConfig() if config is None else config

    if not isinstance(config, GenerationConfig):
        raise ValueError("config must be an explicit GenerationConfig")

    selected_tolerances = {} if tolerances is None else dict(tolerances)
    synthetic = Generate(config)
    comparison = Compare(reference, synthetic, tolerances=selected_tolerances).ToDict()

    for name in ("reference_analysis", "synthetic_analysis"):
        comparison[name] = _SelectedAnalysis(comparison[name])

    manifest = CreateManifest(config, synthetic, metadata={
        "purpose": "Unfitted descriptive comparison with a declared reference window",
        "reference_file_sha256": provenance["file_sha256"],
        "reference_canonical_fingerprint": provenance["canonical_fingerprint"],
    })

    return {
        "evidence_version": 1, "reference": provenance, "scenario_manifest": manifest,
        "recipe": {"name": "declared-market-comparison-v1", "implementation_source_sha256": _ImplementationSources()},
        "predeclared_absolute_tolerances": selected_tolerances, "comparison": comparison,
        "analysis_scope": "Selected marginal/path/dependence summaries; no raw observation vectors",
        "procedure": {
            "parameter_fit": False, "calendar_alignment": False, "resampling": False,
            "seed_search": False, "price_or_volume_scaling": False,
            "generator_inputs": "Explicit complete configuration in scenario_manifest; defaults are library defaults, never inferred from reference data",
        },
        "interpretation": "Metric differences describe this reference window and this one seeded scenario. No universal realism, model acceptance, calibration, forecast or market-mechanics claim. A null tolerance decision means no threshold was supplied or the metric was undefined.",
    }


def _Scalar(value) -> str:
    """Format numbers and undefined values compactly for a plain Markdown report."""

    if value is None:
        return "undefined"

    if isinstance(value, bool):
        return "yes" if value else "no"

    return f"{value:.8g}"


def _Cell(value) -> str:
    """Prevent file paths and input text from adding raw HTML or table structure."""

    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def RenderMarkdown(evidence: dict) -> str:
    """Explain comparison provenance, observed differences and limited decisions."""

    source = evidence["reference"]
    comparison = evidence["comparison"]
    manifest = evidence["scenario_manifest"]
    configuration = manifest["configuration"]
    lines = ["# Declared market-reference comparison", "", evidence["interpretation"], "",
             f"Reference: {_Cell(source['path'])} ({source['format']}); caller timezone: {_Cell(source['assume_timezone'])}.",
             f"Selected {source['selected_rows']} of {source['total_source_rows']} rows, inclusive UTC window {source['window']['actual_start_utc']} to {source['window']['actual_end_utc']}.",
             f"Reference bytes SHA-256: `{source['file_sha256']}`.",
             f"Reference canonical fingerprint: `{source['canonical_fingerprint']}`.", "",
             f"Synthetic: {manifest['model']}, seed {manifest['seed']}, {configuration['horizon']} rows, {configuration['timeframe_seconds']} seconds per observation, initial price {configuration['initial_price']:g}.",
             f"Synthetic canonical fingerprint: `{manifest['fingerprint']}`.",
             f"Scenario identity fingerprint: `{manifest['scenario_fingerprint']}`.", "",
             "Parameters were not fitted. Calendar dates, session gaps, price level and volume units were not aligned or rescaled. Different row counts or timestamp spacing remain explicit.", "",
             "| Metric | Reference | Synthetic | Synthetic − reference | Absolute tolerance | Within tolerance |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]

    for metric in comparison["metrics"]:
        decision = "not assessed" if metric["within_tolerance"] is None else "yes" if metric["within_tolerance"] else "no"
        lines.append(f"| {metric['name']} | {_Scalar(metric['reference'])} | {_Scalar(metric['synthetic'])} | {_Scalar(metric['difference'])} | {_Scalar(metric['absolute_tolerance']) if metric['absolute_tolerance'] is not None else 'not supplied'} | {decision} |")

    lines.extend(("", "Undefined metrics retain reasons in the JSON summaries. Supplied tolerances apply only to the listed metrics; absent thresholds make no acceptance decision.", "", "The JSON artifact includes full configuration, model/RNG/library identity, environment, source/window fingerprints, distribution tails and observation-lag dependence diagnostics."))

    if evidence.get("command"):
        lines.extend(("", "Reproduce from the repository root:", "", "```bash", evidence["command"], "```"))

    return "\n".join(lines) + "\n"


def _JSONObject(pairs):
    """Reject duplicate input keys so configuration provenance is unambiguous."""

    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")

        result[key] = value

    return result


def _RejectConstant(value):
    """Reject JavaScript-style nonfinite constants in declared inputs."""

    raise ValueError(f"Nonstandard JSON constant: {value}")


def _ReadObject(path):
    """Parse the exact hashed UTF-8 JSON bytes used as declared inputs."""

    raw = Path(path).read_bytes()
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=_JSONObject, parse_constant=_RejectConstant)

    if not isinstance(result, dict):
        raise ValueError("configuration and tolerances files must contain JSON objects")

    return result, {"path": Path(path).as_posix(), "file_sha256": hashlib.sha256(raw).hexdigest()}


def _OutputPaths(outputs, inputs):
    """Protect source inputs and reject aliased output destinations before writes."""

    used = [Path(path) for path in inputs]

    for output in outputs:
        if output is None:
            continue

        path = Path(output)

        for previous in used:
            same = path.resolve() == previous.resolve()

            if not same and path.exists() and previous.exists():
                same = path.samefile(previous)

            if same:
                raise ValueError("output paths must differ from all inputs and other outputs")

        used.append(path)


def Main(argv=None) -> int:
    """Write compact JSON plus a human report, with no implicit model acceptance."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--format", choices=("canonical", "aflt-day"), default="canonical")
    parser.add_argument("--timezone", help="Explicit timezone assumption; required for aflt-day")
    parser.add_argument("--start", help="Inclusive explicit-offset ISO reference window start")
    parser.add_argument("--end", help="Inclusive explicit-offset ISO reference window end")
    parser.add_argument("--config", type=Path, help="Declared GenerationConfig JSON object; unspecified fields use library defaults")
    parser.add_argument("--tolerances", type=Path, help="Predeclared absolute metric tolerances JSON object; absent means no acceptance decision")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    arguments = parser.parse_args(argv)

    try:
        inputs = [path for path in (arguments.reference, arguments.config, arguments.tolerances) if path is not None]
        _OutputPaths((arguments.output, arguments.markdown), inputs)
        configuration, config_source = _ReadObject(arguments.config) if arguments.config is not None else ({}, {"kind": "library defaults; no fit"})
        tolerances, tolerance_source = _ReadObject(arguments.tolerances) if arguments.tolerances is not None else ({}, {"kind": "none; no acceptance thresholds"})
        evidence = BuildComparison(arguments.reference, config=GenerationConfig.FromDict(configuration), tolerances=tolerances,
                                   format=arguments.format, timezone=arguments.timezone, start=arguments.start, end=arguments.end)
        evidence["declared_input_sources"] = {"configuration": config_source, "tolerances": tolerance_source}
        command_args = list(argv) if argv is not None else None

        if command_args is None:
            command_args = sys.argv[1:]

        evidence["command"] = "python -m tools.compare_market " + shlex.join(command_args)
        rendered_json = json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n"
        rendered_markdown = RenderMarkdown(evidence)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered_json, encoding="utf-8")

        if arguments.markdown is not None:
            arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
            arguments.markdown.write_text(rendered_markdown, encoding="utf-8")

    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))

    print(rendered_markdown, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
