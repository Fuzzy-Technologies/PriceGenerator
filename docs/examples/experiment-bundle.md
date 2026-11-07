# Create a reproducible OHLCV experiment bundle

Use this example to pass a compact synthetic experiment from a development
machine to a reviewer or a test runner. The bundle contains two OHLCV
fixtures, their replay manifests, a Monte Carlo report and offline chart,
a statistical comparison, and a checksum for each file.

## Generate and verify the bundle

Install the package from a wheel or source distribution. In a writable
directory outside the checkout, use your installed environment's Python
and replace the example path with the runner's absolute path.
[Example runner](../../tools/experiment_bundle.py)

```bash
python -I /path/to/PriceGenerator/tools/experiment_bundle.py create pg-experiment
python -I /path/to/PriceGenerator/tools/experiment_bundle.py verify pg-experiment
```

`create` requires a new output directory. The parent directory must already
exist. If generation stops partway through, use a fresh destination for the
next run. A complete bundle has `SHA256SUMS`, written after the replay checks.
`verify` recalculates SHA-256 for the expected files and checks the full
checksum list. Use the original checksum list to verify a transferred copy.

## Read the results

- `scenario.csv` contains 120 hourly candles from seed 42. `reference.csv`
  contains another synthetic series, with seed 43 and lower base volatility.
  The two `*-manifest.json` files record their configuration and environment.
  Creation replays each saved manifest and compares the canonical CSV bytes.
- `ensemble.json` summarizes 32 paths generated from the scenario
  configuration with two workers. The runner reads `ensemble-manifest.json`,
  replays with one worker, and requires identical report bytes.
- `quantiles.html` opens offline. The candles and volume come from path 0.
  The P05, P50 and P95 lines summarize closes at each individual candle
  across all paths. Whole-path coverage requires a separate calculation. [Ensemble conventions](../monte-carlo.md)
- `comparison.json` records `evaluation.Compare` metrics for the two
  synthetic fixtures, including their OHLCV fingerprints. Read the
  differences as descriptive statistics for these two simulated series.

To inspect indicators for the single generated series, create a separate HTML
file beside the bundle and open it in a browser.

```sh
pricegenerator chart pg-experiment/scenario.csv --analysis --output analysis.html --no-view
```

Use **Bollinger bands**, **Midpoint** or **SMA 5 / 20** below the toolbar.
The bundle has 120 candles, so SMA 200 has too few observations.
[See the indicator controls and a screenshot](cli-demo.md#open-the-same-candles-with-indicator-buttons).

Archive the directory with its checksum list. To regenerate the numerical
results, use the library and dependency versions recorded in the manifests.
