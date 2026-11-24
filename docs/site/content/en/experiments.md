---
layout: default
lang: en
route: experiments
title: "Experiments with synthetic prices"
permalink: /en/experiments/
redirect_from:
  - /docs/site/content/en/experiments.html
---
# Experiments with synthetic prices

## Run the same setup 32 times
{: #monte-carlo }

Keep the initial price and model parameters fixed. Give every path its own reproducible random stream. In `quantiles.html` the candles and volume come from path zero. The lines show the 5th, 50th and 95th percentiles of all closes at each hour. For the last hour in this 120-hour example they are 75.01, 101.27 and 150.46. A path can cross the band at another hour.

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output ensemble.json --manifest ensemble-manifest.json --chart quantiles.html
python -m pricegenerator replay-ensemble ensemble-manifest.json --output replayed.json
```

The JSON report includes the maximum **price** drawdown of each path. To measure a strategy's drawdown, feed the individual OHLCV rows into your own backtester with its position and trading-cost rules.

### Where are the other 31 paths?
{: #paths }

All 32 paths are generated in full. The standard chart shows the candles and volume of **path 00** and three percentiles calculated across all paths. The report stores those percentiles, one maximum drawdown per path and the settings needed to reproduce each series. You can reproduce the full OHLCV data for any path from those settings and its index.

The candles and volume bars below show path 00. Each thin grey line follows the hourly closing prices of one of the other 31 paths. At any hour, the blue line marks the 5th percentile, the purple line the median and the gold line the 95th percentile across all 32 closes.

[![Hourly candles and volume for path 00, 31 grey price paths and three coloured percentile lines.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)

**[Download the 32 OHLCV files (ZIP)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.zip)** for this exact example. Each file from `path-00.csv` to `path-31.csv` contains 120 hourly candles with opens, highs, lows, closes and volumes.

To export your own run, execute the following Python code in the folder containing `ensemble.json` created above. It reads the original settings and derives the same seed for each zero-based path index. The files are written to the `paths` folder.

```python
import json
from dataclasses import replace
from pathlib import Path

from pricegenerator import Generate, GenerationConfig, WriteCSV
from pricegenerator.monte_carlo import DerivePathSeed

report = json.loads(Path("ensemble.json").read_text(encoding="utf-8"))
config = GenerationConfig.FromDict(report["configuration"])
output = Path("paths")
output.mkdir(exist_ok=True)

for index in range(report["path_count"]):
    seed = DerivePathSeed(config.seed, index)
    candles = Generate(replace(config, seed=seed))
    WriteCSV(candles, output / f"path-{index:02d}.csv", volume_as_count=config.model == "regime_v3")
```

To see the candles and volume for a particular path, replace `17` with its index.

```sh
python -m pricegenerator chart paths/path-17.csv --analysis --output path-17.html --view
```

## Compare synthetic data with observations
{: #compare }

Use two canonical OHLCV files on a regular grid, with the same bar interval and comparable volume units. Select contiguous windows. Optionally pass a JSON mapping of metric names to absolute tolerances via `--tolerances`. A successful command means the comparison ran. The individual metric decisions are in the report.

```sh
python -m pricegenerator compare observed.csv synthetic.csv --timeframe-seconds 3600 --output comparison.json
```

## Which market does this resemble?
{: #bitstamp }

The default scenario starts at 100 and has no ticker. To reproduce selected features of a market, choose an instrument, timeframe and calibration window. Evaluate later data separately. In the Bitstamp BTC/USD experiment, 720 hourly bars from September 2024 were used for fitting and 744 October bars for testing. All 16 runs met the declared tolerances for return volatility and mean hourly BTC volume.

The restricted `regime_v2` fit held volume at 71.93 BTC per hour. Observed volume averaged 67.45 BTC and moved with absolute returns (correlation 0.522). Constant synthetic volume has no defined correlation. Volatility clustering also differed. These results support reproducing selected statistics and measuring the differences. The default `regime_v3` produces varying whole activity counts. [Numerical results and data provenance](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/reference-bitstamp-holdout.json).

## Share a complete experiment
{: #bundle }

From a checkout matching the installed package, run the supplied example script with a new output directory. It creates two synthetic hourly CSVs, both manifests, a comparison, a 32-path chart and checksums. The verify command checks the saved files.

```sh
python -I tools/experiment_bundle.py create pg-experiment
python -I tools/experiment_bundle.py verify pg-experiment
```

Open `pg-experiment/quantiles.html`. For indicator controls run `python -m pricegenerator chart pg-experiment/scenario.csv --analysis --output analysis.html --view`. The bundle has 120 bars, so use the 240-bar [quick start](https://fuzzy-technologies.com/PriceGenerator/en/quick-start/) to display SMA 200.

## How fast can I generate a million candles?
{: #performance }

On a Linux x86-64 server with an AMD EPYC 9V74, one Python process generated **1,000,000 minute candles in 3.72 seconds** (about **269,000 candles/s**). Generating and saving all six columns to a local CSV took **8.59 seconds** in total. The file was 109.5 MB. With the default 2.2.1 model, the `volume` column contains whole counts.

| Minute candles | Generate in memory | Write the CSV | Generate and write |
| -------------: | -----------------: | ------------: | -----------------: |
| 100,000        | 0.33 s             | 0.45 s        | 0.77 s             |
| 1,000,000      | 3.72 s             | 4.87 s        | 8.59 s             |

Each column shows its own median over five fresh processes per size. The benchmark used the PyPI 2.2.1 package with CPython 3.14.10, pandas 2.3.3, NumPy 2.3.5 and seed 42. The timer covered `Generate` and `WriteCSV`, including their validation and the buffered local file write. Imports, warm-up, checksums and chart rendering took place outside the measured stages or were omitted. The host and storage affect the result.

One series can contain up to **1,000,000 candles**. Monte Carlo supports 2–10,000 paths with at most **1,000,000 candles across them all**. For 32 equal-length paths this allows up to 31,250 candles per path. To measure your own machine, download the script and run `python -I measure_generation.py 1000000` with 2.2.1 installed. [Benchmark script](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/measure_generation.py) · [Timings and CSV checksums (JSON)](https://fuzzy-technologies.com/PriceGenerator/docs/evidence/generation-speed-2.2.1.json)

[Русский](../ru/experiments.md) · [简体中文](../zh-CN/experiments.md)
