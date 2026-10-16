"""Rebuild deterministic branded examples using only the modern generation APIs."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.rendering.api import Chart, PrepareChart


def ExamplePrices(length: int = 96) -> pd.DataFrame:
    """Generate seeded data, then explicitly add a session gap and zero activity."""

    prices = Generate(GenerationConfig(seed=20261016, horizon=length,
        start=datetime(2026, 10, 12, 8, tzinfo=timezone.utc), timeframe_seconds=1800,
        volatility=0.004, regime_scale=2, shock_probability=0.02))
    prices.loc[prices.index >= 48, "datetime"] += pd.Timedelta(days=2)
    prices.loc[prices.index < 4, "volume"] = 0

    return prices


def GenerateExamples(output_directory: Path, *, interactive: bool = False) -> list[Path]:
    """Render seeded modern analytics with explicit alignment and fixture provenance."""

    output_directory.mkdir(parents=True, exist_ok=True)
    prices = ExamplePrices()
    annotations = pd.DataFrame({
        "datetime": [prices.datetime.iloc[20], prices.datetime.iloc[48], prices.datetime.iloc[78]],
        "markersUpper": ["Research marker", "", ""],
        "markersCenter": ["", "Session resumes", ""],
        "markersLower": ["", "", "Research marker"],
    })
    provenance = (
        "Seeded regime_v2 fixture: seed20261016, 96 half-hour observations; no realism claim.",
        "A deliberate two-day session gap and four zero-volume observations were added after generation.",
        "The UTC axis preserves the session gap. Indicators count observations without resampling.",
    )
    analyzed = PrepareChart(prices, analysis=True,
        title="Synthetic market scenario · Fuzzy Technologies", markers=annotations,
        width=1280, height=680)
    market = replace(analyzed, summary=provenance + analyzed.summary[:6])
    keys = {"hma5", "alligator-jaw", "alligator-teeth", "alligator-lips"}
    aligned = tuple(replace(series, visible=True, width=2) for series in analyzed.series if series.key in keys)
    indicator = replace(market, title="Modern indicator alignment: HMA and Alligator", markers=(),
        series=aligned, summary=provenance + (
            "HMA5 is unshifted: WMA(2WMA(close,2)-WMA(close,5),2). Warmup values remain gaps.",
            "Alligator uses median-price SMMA: jaw13 shifted8, teeth8 shifted5, lips5 shifted3 observations.",
            "Each SMMA starts from its complete SMA seed. Forward shifts use existing rows across the gap.",
            "These are independent calculations; Alligator never overwrites HMA5.",
        ))
    outputs = []

    for name, chart in (("modern-market", market), ("modern-indicator-alignment", indicator)):
        report_path = output_directory / f"{name}.md"
        outputs.append(Chart(chart, output_directory / f"{name}.svg", view=False, markdown_report=report_path))
        outputs.append(report_path)

        if interactive:
            outputs.append(Chart(chart, output_directory / f"{name}.html", view=False))

    return outputs


def Main() -> None:
    """Write reviewable examples only when the command is explicitly invoked."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/examples"))
    parser.add_argument("--html", action="store_true", help="Also generate standalone interactive examples.")
    arguments = parser.parse_args()

    for output_path in GenerateExamples(arguments.output_dir, interactive=arguments.html):
        print(output_path)


if __name__ == "__main__":
    Main()
