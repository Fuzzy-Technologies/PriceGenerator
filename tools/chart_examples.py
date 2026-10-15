"""Rebuild deterministic branded examples of the new chart and HMA migration APIs."""

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
import math
from pathlib import Path

import pandas as pd

from pricegenerator.rendering.adapters import FromDataFrame, SaveMarkdown
from pricegenerator.rendering.spec import ChartSeries
from pricegenerator.rendering.static import SaveSVG


def ExamplePrices(length: int = 96) -> pd.DataFrame:
    """Create analytical OHLCV values with an explicit session gap and zero volume."""

    candles = []
    start = datetime(2026, 10, 12, 8, tzinfo=timezone.utc)

    for index in range(length):
        opening = 100 + index * 0.025 + 1.8 * math.sin(index / 8)
        closing = opening + 0.45 * math.cos(index / 3)
        candles.append({
            "datetime": start + timedelta(minutes=30 * index, days=2 if index >= 48 else 0),
            "open": round(opening, 2), "close": round(closing, 2),
            "high": round(max(opening, closing) + 0.27, 2),
            "low": round(min(opening, closing) - 0.22, 2),
            "volume": 0 if index < 4 else 160 + (index * 71) % 430,
        })

    return pd.DataFrame(candles)


def GenerateExamples(output_directory: Path, *, interactive: bool = False) -> list[Path]:
    """Render fixed fixtures; all prices and indicators have explicit provenance."""

    output_directory.mkdir(parents=True, exist_ok=True)
    prices = ExamplePrices()
    annotations = pd.DataFrame({
        "datetime": [prices.datetime.iloc[20], prices.datetime.iloc[48], prices.datetime.iloc[78]],
        "markersUpper": ["Scenario peak", "", ""],
        "markersCenter": ["", "Session resumes", ""],
        "markersLower": ["", "", "Research marker"],
    })
    reference = pd.DataFrame({"datetime": prices.datetime, "Reference path": [100 + index * 0.025 for index in range(len(prices))]})
    market = FromDataFrame(
        prices, title="Synthetic market scenario · Fuzzy Technologies",
        markers=annotations, lines=[reference], width=1280, height=680,
        summary=(
            "Analytical fixture: periodic movement plus a fixed linear reference; no realism claim.",
            "The two-day session gap is preserved on the elapsed UTC time axis.",
            "Volume includes four valid zero-volume candles. Marker positions use screen spacing.",
        ),
    )

    try:
        backend = import_module("pandas_ta_classic")

    except ModuleNotFoundError as error:
        if error.name != "pandas_ta_classic":
            raise

        backend = import_module("pandas_ta")

    unshifted = backend.hma(close=prices.close, length=5, offset=None)
    shifted = backend.hma(close=prices.close, length=5, offset=3)
    indicator = replace(
        market, title="HMA 5: historical shift and explicit correction", markers=(),
        series=(
            ChartSeries("hma5-unshifted", "HMA 5 · unshifted", tuple(None if pd.isna(value) else float(value) for value in unshifted), color="#57c7ff", width=2.6),
            ChartSeries("hma5-shifted", "Historical HMA 5 / Alligator lips · shift 3", tuple(None if pd.isna(value) else float(value) for value in shifted), color="#ee72d3", width=2.3, dashed=True),
        ),
        summary=(
            "Calculated by the real TA backend: HMA(close, length=5, offset=None) and offset=3.",
            "Legacy GetStatistics overwrites HMA 5 with Alligator lips, shifting both displayed lines.",
            "BuildLegacyChart preserves that behavior by default; hma5_mode='unshifted' corrects only HMA 5.",
            "Warmup periods remain gaps. A shift is three candles, including across a session gap.",
        ),
    )
    outputs = []

    for name, chart in (("modern-market", market), ("hma5-migration", indicator)):
        outputs.append(SaveSVG(chart, output_directory / f"{name}.svg"))
        outputs.append(SaveMarkdown(chart, output_directory / f"{name}.md"))

        if interactive:
            from pricegenerator.rendering.interactive import SaveInteractive

            outputs.append(SaveInteractive(chart, output_directory / f"{name}.html"))

    return outputs


def Main() -> None:
    """Write reviewable examples only when the command is explicitly invoked."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/examples"))
    parser.add_argument("--html", action="store_true", help="Also generate the larger standalone interactive examples.")
    arguments = parser.parse_args()

    for output_path in GenerateExamples(arguments.output_dir, interactive=arguments.html):
        print(output_path)


if __name__ == "__main__":
    Main()
