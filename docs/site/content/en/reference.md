---
layout: default
lang: en
route: reference
title: "Working with candle data"
permalink: /en/reference/
redirect_from:
  - /docs/site/content/en/reference.html
---
# Working with candle data

## CSV and volume
{: #csv }

The header is `datetime,open,high,low,close,volume`. Timestamps are unique, increasing and in UTC. Give naive broker timestamps an explicit time zone when importing. High and low enclose both open and close. Validation checks the structure. Use `--timeframe-seconds 3600 --no-gaps` to require consecutive hourly bars.

The default model generates integer activity counts. An imported quantity keeps its source unit and can be fractional. To write generated counts in exactly the same textual format as the CLI, use `WriteCSV(candles, "candles.csv", volume_as_count=True)`.

## Charts and indicators
{: #charts }

A basic HTML chart shows candles and volume. Add `--analysis` to turn on indicator controls and an expandable statistical report. SMA 200 needs 200 candles. Bollinger bands show a rolling envelope, while Midpoint marks the middle of each candle’s high–low range. Close limits, the endpoint trend and Zig-Zag use later data when describing earlier bars. Treat these as retrospective overlays.

```sh
python -m pricegenerator chart candles.csv --analysis --output chart.html --view
```

Use the wheel or box zoom to inspect an interval. **Export PNG** saves the visible chart and overlays. Direct static export to PNG/JPEG needs `pricegenerator[export]`. A static export with `--analysis` includes the statistics under the plot. SVG and offline HTML work with the base installation.

## Distribution and drawdown
{: #analysis }

`python -m pricegenerator analyze candles.csv --output stats.json` reports candle direction, returns, volume, tails and dependence. Drawdown based on closes measures the fall from a previous closing high to a later close. Strategy drawdown depends on positions and execution costs. Undefined estimates include the reason.

## Model assumptions
{: #model }

Drift and volatility apply per candle. A change from minutes to hours changes the clock spacing. Choose movement parameters for the new interval. The generator provides candle boundaries and a whole synthetic activity count. Exchange holidays, spread, intrabar ticks and order execution require separate inputs. Read [how candles and volume are generated](https://fuzzy-technologies.com/PriceGenerator/en/scenario-guide/).

## Research options
{: #research }

The Python calibration API fits selected training moments and can score a later window. Its restricted continuous-volume fit holds activity constant. The optional fuzzy diagnostic on CPython 3.13–3.15 summarizes volatility and activity in a separate score. The diagnostic does not feed back into the price generator. [Read the BTC/USD results](https://fuzzy-technologies.com/PriceGenerator/en/experiments/#bitstamp).

## Source and verification
{: #development }

Install a local checkout with `python -m pip install .`. To build the public Python API reference, install `.[docs]` and run `python PDocBuilder.py` from the checkout root. The generated index is `build/docs-api/pricegenerator.html`. The current model and chart contracts are covered by the release tests. The earlier series used a mutable generator and different CLI flags. [Migrate an existing script](https://fuzzy-technologies.com/PriceGenerator/en/migration/).


## Validation and release checks
{: #validation }
Check the CSV structure, distributions and time dependence separately. Agreement on volatility alone does not establish agreement on volume or the clustering of big moves. Choose tolerances on earlier data and evaluate a later period. Keep the seed, manifest and data fingerprint.

## Packaging and installation
{: #packaging }
The project builds a wheel and a source distribution and verifies clean installs before the approved PyPI publication. The release tag records the source commit. Install the base package for offline HTML and SVG or add the export extra for PNG and JPEG.

[Русский](../ru/reference.md) · [简体中文](../zh-CN/reference.md)
