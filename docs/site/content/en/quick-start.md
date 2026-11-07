# Reproduce a synthetic OHLCV scenario

![PriceGenerator by Fuzzy Technologies. Synthetic market data generator.](../../../assets/pricegenerator-product-card.webp)

[Русский](../ru/quick-start.md) · [简体中文](../zh-CN/quick-start.md)

[Scientific guide](scenario-guide.md) · [What's new in 2.1](release-2-1.md)

Generate a seeded series, replay it from a manifest, and render it without
opening a browser. Use this fixture for software tests and controlled
experiments. Its timestamps are synthetic, and its prices reflect the
configured model assumptions.

## Install the 2.2 source

Use CPython 3.10–3.15 and a fresh environment. The commands below use
the 2.2 source on `master`. Keep the commit printed by Git with your results.

```sh
git clone --branch master --depth 1 https://github.com/Fuzzy-Technologies/PriceGenerator.git pg-demo
cd pg-demo
git rev-parse HEAD
python -m venv .venv
```

Activate the environment with `. .venv/bin/activate` on POSIX or
`.\.venv\Scripts\Activate.ps1` in Windows PowerShell. From the checkout, install
the package with its runtime constraints. The version check should print
`2.2.0`.

```sh
python -m pip install -c requirements/modern.txt .
python -m pip check
python -I -c "from importlib.metadata import version; print(version('pricegenerator'))"
mkdir pg-example
cd pg-example
```

## Generate, verify, and chart

```sh
python -I -m pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 60 --output prices.csv --manifest scenario.json
python -I -m pricegenerator validate prices.csv --timeframe-seconds 60 --no-gaps
python -I -m pricegenerator replay scenario.json --output replay.csv
python -I -m pricegenerator chart prices.csv --output chart.html --analysis --no-view
python -I -m pricegenerator chart prices.csv --output chart.svg --no-view
```

Validation reports 240 rows, `"valid": true` and a canonical OHLCV fingerprint.
The fingerprint equals `fingerprint` in `scenario.json`. Replay checks the
recorded configuration, library version, environment and exact data fingerprint.
The generated and replayed CSV files have identical contents. Open `chart.html`
locally to zoom and inspect the series. `chart.svg` is a static vector export.

**Want indicator buttons?** Rebuild the HTML from the same CSV with
`--analysis` (or use `Chart(prices, "chart.html", analysis=True)` in Python).
Open the HTML in your browser. Click **Bollinger bands** to see the price
envelope, **SMA 50 / 200** to compare moving averages, or **Midpoint** to mark
the middle of each candle's high–low range. Other groups include HMA, VWMA,
PSAR, Alligator and Zig-Zag. Expand **Individual series** to toggle one line
at a time. SMA 200 needs at least 200 candles.

Use the wheel or **Box zoom** to focus on an interval. Switch to **Light theme**
if you prefer, or download the current view with **Export PNG**. The brief
overview sits below the chart. Expand **Detailed statistics** for the full report.

## Generate the same series in Python

Save the following as `scenario.py` in the example directory and run
`python -I scenario.py`.

```python
"""Reproduce a seeded minute-bar fixture using the installed package."""

from datetime import datetime, timezone

from pricegenerator import Chart, CreateManifest, Fingerprint, Generate, GenerationConfig, Replay, WriteCSV

config = GenerationConfig(
    seed=42,
    horizon=240,
    start=datetime(2025, 1, 6, tzinfo=timezone.utc),
    timeframe_seconds=60,
)
prices = Generate(config)
manifest = CreateManifest(config, prices)

if Fingerprint(Replay(manifest)) != Fingerprint(prices):
    raise RuntimeError("Replay changed the canonical OHLCV fingerprint")

WriteCSV(prices, "python-prices.csv")
Chart(prices, "python-chart.svg", view=False)
Chart(prices, "python-analysis.html", analysis=True, view=False)
print(manifest["fingerprint"])
```

The printed data fingerprint matches the CLI example under the same environment.
Seed identifies the random stream. The full configuration also fixes the model,
start time, interval and other parameters. Keep the manifest to reproduce a run.

## Figure provenance

Keep the source tag or commit, the generation manifest, the chart command and
its options with a figure. Record the SHA-256 of an exported file separately
from the OHLCV fingerprint. Renderer versions and fonts can affect raster
output. In particular, the fingerprint of a single trajectory identifies
only its source candles. An ensemble figure also needs its member seeds or
seed derivation rule, path count, and aggregation method.

The repository's market and indicator figures use a different fixture. Their
script starts with a seeded path, then adds a deliberate session gap and
zero-volume bars. From the tagged checkout root, run
`python -m tools.chart_examples --output-dir pg-figures --html` to rebuild the
SVG, HTML and provenance notes. [Figure recipe](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/tools/chart_examples.py) · [Market figure notes](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/examples/modern-market.md)

## Exchange bars with MetaTrader 5

PriceGenerator writes UTF-8 comma-separated rows with the header
`datetime,open,high,low,close,volume`, ISO 8601 UTC timestamps, and finite
numbers with a decimal point. For imports from a broker, first convert the
format explicitly and declare the source timezone for naive timestamps.
Keep session gaps and validate them against the known interval.
[Canonical data and CSV contract](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.0.0/docs/data-contract.md)

An adapter that loads a custom MT5 symbol through `CustomRatesReplace` needs
minute bars aligned to M1 opening times. Generate M1 directly, as above.
MQL5 `datetime` uses whole seconds since 1970. Check the range and alignment
before mapping timestamps. Map the whole synthetic `volume` to `tick_volume` only if the test uses
it as a stand-in for tick count. Obtain `real_volume` and spread in points
separately. Imported asset quantities can be fractional, so define the source
unit before mapping them to an integer MT5 field. Document price rounding for the
symbol's digits and check candle geometry after conversion. Use a dedicated
custom symbol and a bounded replacement interval.
[CustomRatesReplace](https://www.mql5.com/en/docs/customsymbols/customratesreplace) · [MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates) · [MQL5 datetime](https://www.mql5.com/en/docs/basis/types/integer/datetime)

This example verifies the CSV on the Python side. Terminal import, bar
round-trip checks and strategy-tester settings belong to a separate integration
test. Real-tick testing requires a separate tick history.
[MQL5 guide to custom-symbol history](https://www.mql5.com/en/book/advanced/custom_symbols/custom_symbols_rates)
