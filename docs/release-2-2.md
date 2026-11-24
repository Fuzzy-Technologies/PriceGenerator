---
layout: default
lang: en
route: release-2-2
title: "PriceGenerator 2.2.1"
permalink: /en/release-2-2/
redirect_from:
  - /docs/release-2-2.html
---
# PriceGenerator 2.2.1

[Package 2.2.1 on PyPI](https://pypi.org/project/pricegenerator/2.2.1/)

PriceGenerator makes synthetic market candles for testing trading systems.
In 2.2 you can put a historical series beside a generated one and see
where they differ. You can also share a complete experiment so a colleague
can reproduce the same candles, charts and comparison.

## What changed since 2.1

- **Compare two price series.** Give PriceGenerator two CSV files with the
  same candle interval. It shows how they differ in volatility, drawdown,
  volume and other measures. You can set how large a difference you are
  willing to accept for each measure.
- **Share an experiment.** The worked example creates two synthetic series
  and saves the settings, comparison and charts together. A colleague can
  use the saved settings to replay the experiment and check the results.
- **Generate whole-number volumes.** The default candle model records a count for each bar. Imported market data keeps its original units and precision, including fractional quantities such as BTC.

## How to read the chart

We ran the same scenario 32 times. The candles and volume bars show the first run. Each thin grey line follows one of the other 31 runs. The three coloured lines show how closing prices are distributed across all 32 runs at each hour.

[![Hourly candles and volume for path 00, 31 grey price paths and three coloured percentile lines.](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)](https://fuzzy-technologies.com/PriceGenerator/docs/assets/monte-carlo-32-paths.svg)

Pick the last hour. Sort its 32 closing prices from lowest to highest.
The purple line marks the middle at **101.27**. The blue and yellow lines
mark the lower and upper edges of the central 90% of the distribution,
roughly **75.01 to 150.46** for that hour. At another hour, different runs
can set those marks. The spread helps you see how far outcomes can vary
under the same scenario settings.

[See the 32 individual paths and download their OHLCV files](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#paths).

## Try it

With PriceGenerator 2.2.1 installed, generate 240 hourly candles and open
the resulting HTML chart in your browser. The chart works offline.

```sh
python -m pip install pricegenerator==2.2.1
pricegenerator generate --seed 42 --horizon 240 --start 2025-01-06T00:00:00Z --timeframe-seconds 3600 --output candles.csv
pricegenerator chart candles.csv --output candles.html --analysis --view
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

[Run the full experiment](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#bundle) ·
[Compare two CSV files](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#compare) ·
[Python API reference](https://fuzzy-technologies.com/PriceGenerator/api/2.2.1/en/) · [Upgrade from 1.4.93](https://fuzzy-technologies.com/PriceGenerator/en/migration/)

[Русский](https://fuzzy-technologies.com/PriceGenerator/ru/release-2-2/) · [简体中文](https://fuzzy-technologies.com/PriceGenerator/zh-CN/release-2-2/)
