---
layout: default
lang: en
route: scenario-guide
title: "Synthetic OHLCV scenarios and their limits"
permalink: /en/scenario-guide/
redirect_from:
  - /docs/site/content/en/scenario-guide.html
---
# Synthetic OHLCV scenarios and their limits

Start with the [2.2.1 quick start](https://fuzzy-technologies.com/PriceGenerator/en/quick-start/) to create and open your first chart. [Release notes](https://fuzzy-technologies.com/PriceGenerator/en/release-2-2/) · [Migration from earlier versions](https://fuzzy-technologies.com/PriceGenerator/en/migration/)

## Choose a first experiment

- **Test a CSV importer.** Generate 240 candles with a fixed seed, save the manifest and replay the same file after a code change.
- **Check a chart or indicator.** Open the offline chart with `--analysis` and turn Bollinger bands or SMA 50 / 200 on and off on the same candles.
- **Stress-test a trading rule.** Run the same setup with many seeds and feed each price path into your own backtester. The ensemble report already gives the range of closing prices and drawdowns of the simulated price.
- **Compare with a real market.** Take a regular window of hourly BTC/USD, set parameters on an earlier window, then compare volatility and volume on later data. The [Bitstamp example](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#bitstamp) shows which statistics matched. The default scenario starts at 100 and has no instrument attached.

## One candle at a time

1. The first open is `initial_price` (100 by default). Every later open equals the previous close.
2. The model stays in its current volatility regime or switches between calm and turbulent. Drift, a random move of the corresponding size and an occasional shock set the new close. A move beyond a price limit reflects back into range.
3. Two independent draws extend the body upwards and downwards to make the wicks. Price limits also apply to the high and low.
4. Volume starts from a base level. Random activity partly carries over from the previous candle and larger absolute moves relative to current volatility tend to raise it. The default model limits and rounds the result to a whole count of at least one. Then the next candle starts.

## What do 32 paths tell me?

Repeat the same assumptions 32 times with different random draws. At the last hour in the example below, sort the 32 closes from low to high. The middle is 101.27. The 5th and 95th percentiles are 75.01 and 150.46. Each preceding hour has its own three values. Candles and volume show the first path. The band describes the synthetic prices at each hour. A complete path can cross it, and real prices can behave differently.

```sh
python -m pricegenerator monte-carlo --seed 42 --paths 32 --horizon 120 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --chart range.html --output range.json
```

Open `range.html` in a browser. To test a strategy across full paths, [regenerate each member by its index](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#monte-carlo) and run it through your own backtester.

## Interpret the candles

The portable table has six columns in order:
`datetime,open,high,low,close,volume`. Timestamps are unique, increasing
UTC instants with nanosecond precision. Prices and volume are finite
binary64 values, and volume is nonnegative. The high and low enclose
both the open and close. The canonical reader accepts nonpositive prices
when candle geometry holds. The default generator produces positive prices.

Set the interval explicitly when checking a regular grid. For broker
data, declare the timezone of naive timestamps and preserve real gaps.
The [CSV contract](https://fuzzy-technologies.com/PriceGenerator/en/reference/#csv) documents parsing and validation.
For MT5, follow the [exchange example](https://fuzzy-technologies.com/PriceGenerator/en/quick-start/#exchange-bars-with-metatrader-5)
for M1 alignment, integer volume fields and spread. A bar CSV alone cannot
support a real-tick strategy test.

## Model a controlled scenario

The default `regime_v3` model starts in its low-volatility state. Before each candle it switches between
calm and stressed states with probability `1 - regime_persistence`.
The Gaussian return component has standard deviation $\sigma$ of `volatility` in the calm state
and `volatility * regime_scale` in the stressed state. Parameters apply
per candle, so changing the interval requires choosing parameters for that
cadence.

The proposed log return is
$r = \mu + \sigma Z + \sigma_0 s B Z_{\mathrm{shock}}$.
Here $\mu$ is `drift`, $\sigma_0$ is the base `volatility`, and $s$ is
`shock_scale`. The normal draws are independent and the independent
Bernoulli variable $B$ activates the shock with probability
`shock_probability`. The open is the previous close after the first bar.
The proposed log close is reflected at the configured bounds when needed,
so the realized return can differ from $r$.

Wick lengths extend from the body in log-price space, with independent
outlier events on each side and clipping at the price bounds.

The default model emits whole synthetic activity counts. The noise has memory
and the level can grow with the absolute realized return. Historical
`regime_v2` configurations retain continuous volume. Fractional traded asset
quantities in imported CSVs retain their values. A synthetic count does not
measure actual ticks, trades, or traded assets. See the [model specification](https://fuzzy-technologies.com/PriceGenerator/en/scenario-guide/)
for draw order, exact formulas and boundary rules, and the
[scripted numerical tests](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.1/tests/test_regime_v2_oracles.py)
for hand-derived cases.

## Inspect the result and keep provenance

From the quick start's example directory, run:

```sh
python -I -m pricegenerator analyze prices.csv --output statistics.json
python -I -m pricegenerator chart prices.csv --output analysis.html --analysis --no-view
```

The first command writes statistics with definedness information. The
second writes offline HTML with indicators and diagnostics. Open it
locally to inspect the chart. The [analysis guide](https://fuzzy-technologies.com/PriceGenerator/en/reference/#analysis)
defines the metrics and when they are unavailable.

**Want indicator buttons?** Rebuild the HTML from the same CSV with
`--analysis` (or use `Chart(prices, "chart.html", analysis=True)` in Python).
Open the HTML in your browser. Click **Bollinger bands** to see the price
envelope, **SMA 50 / 200** to compare moving averages, or **Midpoint** to mark
the middle of each candle's high–low range. Other groups include HMA, VWMA,
PSAR, Alligator and Zig-Zag. Expand **Individual series** to toggle one line
at a time. SMA 200 needs at least 200 candles. The close guides and Zig-Zag
use later candles to describe past movements. Use them to inspect a finished
series.

Use the wheel or **Box zoom** to focus on an interval. Switch to **Light theme**
if you prefer, or download the current view with **Export PNG**. The brief
overview sits below the chart. Expand **Detailed statistics** for the full report.

![Offline candlestick chart with volume, Bollinger Bands and 50- and 200-bar moving averages enabled](https://fuzzy-technologies.com/PriceGenerator/docs/assets/pricegenerator-chart-analysis.webp)

Record the source tag or commit, exact configuration and seed, manifest,
command, dependency versions and SHA-256 of each exported file. The
canonical candle fingerprint in the manifest identifies the data. Export
hashes identify file bytes and may depend on the rendering environment.
The [market](https://fuzzy-technologies.com/PriceGenerator/en/reference/#charts) and
[indicator alignment](https://fuzzy-technologies.com/PriceGenerator/en/reference/#charts)
figures give their generation and transformation recipe. The
[animated CLI demo](https://fuzzy-technologies.com/PriceGenerator/en/quick-start/) gives the commands and
provenance for its separate 120-candle fixture.

## Use research APIs with explicit assumptions

- [Calibration, bootstrap and scripted stress](https://fuzzy-technologies.com/PriceGenerator/en/reference/#research)
  provide experimental module APIs and reproducible synthetic evidence.
- [Monte Carlo](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#monte-carlo) describes the experimental seeded
  ensemble and pointwise price quantiles. A quantile at one candle is
  conditional on the model and is not a whole-path coverage guarantee.
- [Fuzzy diagnostics](https://fuzzy-technologies.com/PriceGenerator/en/reference/#research) describes the
  experimental optional integration on Python 3.13–3.15. The scalar score
  summarizes supplied volatility and activity ratios. It does not feed
  back into candle generation.
- [Reference comparison](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#compare) records the
  provenance, declared assumptions and limits of a historical fixture.
  Treat structural validity, marginal statistics and dependence as
  separate tests. The [statistical evidence policy](https://fuzzy-technologies.com/PriceGenerator/en/reference/#validation)
  describes the criteria for stronger claims.

The default model supports controlled tests of OHLCV consumers and stress
scenarios. It has no order book, spread, execution model or exchange
calendar. Its output cannot establish forecast skill or strategy returns.

Build the [public Python API reference](https://fuzzy-technologies.com/PriceGenerator/en/reference/#development)
from the same checkout to inspect the root exports and their signatures.

[Русский](../ru/scenario-guide.md) · [简体中文](../zh-CN/scenario-guide.md)
