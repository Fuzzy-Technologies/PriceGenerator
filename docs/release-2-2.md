# PriceGenerator 2.2.0

[Русский](release-2-2-ru.md) · [简体中文](release-2-2-zh-CN.md)

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
- **Get started in Russian.** The quick start and guides now explain how to
  work with candles, reproduce a run and exchange data with MetaTrader 5
  using familiar market-data terms.

## How to read the chart

We ran the same scenario settings 32 times, with different random price
moves in each run. The candles and volume show one run. The three lines
summarize the closing prices across all 32 runs, one hour at a time.

![One simulated price series and three lines summarizing 32 runs](assets/pricegenerator-2-2-experiment-quantiles.svg)

Pick the last hour. Sort its 32 closing prices from lowest to highest.
The purple line marks the middle at **101.27**. The blue and yellow lines
mark the lower and upper edges of the central 90% of the distribution,
roughly **75.01 to 150.46** for that hour. At another hour, different runs
can set those marks. The spread helps you see how far outcomes can vary
under the same scenario settings.

## Try it

With PriceGenerator 2.2 installed, generate 240 hourly candles and open
the resulting HTML chart in your browser. The chart works offline.

```sh
pricegenerator generate --seed 42 --horizon 240 --timeframe-seconds 3600 --output candles.csv
pricegenerator chart candles.csv --output candles.html --analysis --no-view
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

![Offline candlestick chart with volume, Bollinger Bands and 50- and 200-bar moving averages enabled](assets/pricegenerator-chart-analysis.webp)

[Run the full experiment](examples/experiment-bundle.md) ·
[Compare two CSV files](reference-comparison.md) ·
[Upgrade from 1.4.93](site/content/en/migrate-to-2-1.md) ·
[Verification details](evidence/pricegenerator-2-2-experiment.md)
