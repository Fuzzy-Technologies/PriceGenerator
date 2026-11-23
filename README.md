# PriceGenerator

![PriceGenerator by Fuzzy Technologies. Synthetic market data generator.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-product-card.webp)

[English](https://fuzzy-technologies.com/PriceGenerator/) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/) · [简体中文](https://fuzzy-technologies.com/PriceGenerator/zh-CN/) · [Quick start](https://fuzzy-technologies.com/PriceGenerator/en/quick-start/)


Reproducible synthetic OHLCV scenarios for trading-system tests and quantitative
research. The v2 API separates generation, validation, diagnostics, CSV, replay
and charts. It produces synthetic test data; it does not forecast markets or
establish that a strategy is profitable.

The [English product site](https://fuzzy-technologies.com/PriceGenerator/) has the quick start, model guide and market examples.

## What can I try?

- **Test a CSV importer.** Generate 240 candles with a fixed seed, save the manifest and replay the same file after a code change.
- **Check a chart or indicator.** Open the offline chart with `--analysis` and turn Bollinger bands or SMA 50 / 200 on and off on the same candles.
- **Stress-test a trading rule.** Run the same setup with many seeds and feed each price path into your own backtester. The ensemble report already gives the range of closing prices and drawdowns of the simulated price.
- **Compare with a real market.** Take a regular window of hourly BTC/USD, set parameters on an earlier window, then compare volatility and volume on later data. The [Bitstamp example](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#bitstamp) shows which statistics matched. The default scenario starts at 100 and has no instrument attached.

On hourly Bitstamp BTC/USD, all 16 fitted runs met the stated tolerances for return volatility and mean volume on the following month. Fitted volume stayed constant, while observed volume varied with the size of price movements.

## Install

[PriceGenerator 2.2.1 on PyPI](https://pypi.org/project/pricegenerator/2.2.1/)

PriceGenerator 2.2.1 supports CPython 3.10–3.15.

```bash
python -m pip install pricegenerator==2.2.1
python -m pip install 'pricegenerator[export]==2.2.1'  # Optional PNG/JPEG.
```

To work from a source checkout, run `python -m pip install .`.
See [what's new in 2.2.1](https://fuzzy-technologies.com/PriceGenerator/en/release-2-2/) or
[find earlier builds on GitHub](https://github.com/Fuzzy-Technologies/PriceGenerator/releases).

## Generate and save

```python
from pricegenerator import Generate, GenerationConfig, ReadCSV, WriteCSV

config = GenerationConfig(seed=0, horizon=240, volatility=0.01)
prices = Generate(config)
WriteCSV(prices, "prices.csv", volume_as_count=True)
restored = ReadCSV("prices.csv")
```

`GenerationConfig` is immutable. Defaults include a fixed UTC start and the
versioned `regime_v3` model with whole synthetic volume counts. Seed zero is valid. Generation owns a private RNG
and leaves process-global random state alone. See [model semantics and the 1.4.93 comparison](https://fuzzy-technologies.com/PriceGenerator/en/scenario-guide/).
Use `model="regime_v2"` for prior continuous-volume scenarios.

Canonical data has exactly `datetime, open, high, low, close, volume`: UTC
nanosecond timestamps and finite float64 values. Fractional imported
trade quantities retain their original values. Imported naive timestamps need
an explicit timezone. `ValidateOHLCV` returns detached canonical data and can
check cadence/gaps. Structural validity is separate from empirical market fit.

## Replay, diagnose and chart

```python
import json
from pricegenerator import Analyze, Chart, CreateManifest, Indicators, Replay

manifest = CreateManifest(config, prices)
with open("scenario.json", "w", encoding="utf-8") as stream:
    json.dump(manifest, stream, allow_nan=False, indent=2)
replayed = Replay(manifest)
statistics = Analyze(prices).ToDict()
indicators = Indicators(prices).ToDict()
chart_path = Chart(prices, "chart.html", analysis=True, view=False)
```

A manifest records full configuration, model/RNG/library identity, environment
and separate scenario-identity and canonical-output fingerprints. Replay requires
a matching environment by default; `strict_environment=False` still requires exact fingerprint equality.
Diagnostics and indicators do not mutate source data. Missing/domain-limited
estimates include reasons, rather than fabricated finite values.

`Chart(prices)` creates offline interactive HTML and opens it in the browser.
Use `view=False` in batch jobs. SVG needs an explicit `.svg` destination; PNG and
JPEG additionally need `[export]`. `analysis=True` explicitly attaches financial
overlays and diagnostics. `DisplayChart(prices)` embeds HTML in a notebook;
install `.[notebook]` if the host lacks notebook tooling. Charts contain one
translucent corporate wordmark in the price panel. See [chart guide](https://fuzzy-technologies.com/PriceGenerator/en/reference/#charts).

## Command line

```bash
pricegenerator generate --seed 0 --horizon 240 --output prices.csv --manifest scenario.json
pricegenerator replay scenario.json --output replay.csv
pricegenerator validate prices.csv --timeframe-seconds 3600 --no-gaps
pricegenerator analyze prices.csv --output statistics.json
pricegenerator chart prices.csv --output chart.html --no-view --analysis
```

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

![Offline candlestick chart with volume, Bollinger Bands and 50- and 200-bar moving averages enabled](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

Version 2.1 also provides [ensemble generation and exact replay](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#monte-carlo) through the CLI and Python, and optional
[fuzzy regime diagnostics](https://fuzzy-technologies.com/PriceGenerator/en/reference/#research) on Python 3.13–3.15.

`python -m pricegenerator` exposes the same commands. A JSON `--config` supplies
all generation parameters; explicit common CLI flags override those fields.
Unknown fields, nonfinite values, ambiguous times and aliased input/output paths
fail early. The old mutable class, rendering methods and old CLI flags are
removed; [migration](https://fuzzy-technologies.com/PriceGenerator/en/reference/#charts) and [ADR-0010](https://fuzzy-technologies.com/PriceGenerator/en/migration/)
record the deliberate break. Historical evidence remains [archived](https://fuzzy-technologies.com/PriceGenerator/en/migration/).

## Run a complete experiment

In 2.2, [compare two OHLCV CSVs](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#compare) at an explicit
bar interval, or use the [experiment bundle](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#bundle)
to generate two seeded fixtures. The example verifies single-path and ensemble
replay and records a comparison, an offline quantile chart and checksums.

## Develop and extend

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Start with [development commands](https://fuzzy-technologies.com/PriceGenerator/en/reference/#development), [packaging](https://fuzzy-technologies.com/PriceGenerator/en/reference/#packaging)
and the [model validation guide](https://fuzzy-technologies.com/PriceGenerator/en/reference/#validation). Read `AGENTS.md` in your checkout before changing code, then follow the project protocol and style contract.
Research helpers remain experimental and module-qualified under
`pricegenerator.calibration`, `pricegenerator.evaluation`,
`pricegenerator.extended_models` and `pricegenerator.registry`; they are outside
the compact root API and do not imply validation against every real market.
Large-data adapters are `GenerateChunks` and `WriteCSVChunks`.

[Repository](https://github.com/Fuzzy-Technologies/PriceGenerator) ·
[Issues](https://github.com/Fuzzy-Technologies/PriceGenerator/issues) ·
[Apache-2.0 license](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/LICENSE) · [Русский](https://fuzzy-technologies.com/PriceGenerator/ru/)
