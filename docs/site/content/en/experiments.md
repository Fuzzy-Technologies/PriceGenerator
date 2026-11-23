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

The JSON contains maximum price drawdown for each path. To test entries, exits and costs, regenerate each member and run your rule in a backtester.

```python
from dataclasses import replace
from datetime import datetime, timezone
from pricegenerator import Generate, GenerationConfig
from pricegenerator.monte_carlo import DerivePathSeed

config = GenerationConfig(seed=42, horizon=120, start=datetime(2025, 1, 6, tzinfo=timezone.utc))
for index in range(32):
    candles = Generate(replace(config, seed=DerivePathSeed(config.seed, index)))
    print(index, round(candles["close"].iloc[-1], 2))
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

[Русский](../ru/experiments.md) · [简体中文](../zh-CN/experiments.md)
