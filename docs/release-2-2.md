# PriceGenerator 2.2.0 verification digest

PriceGenerator generates reproducible synthetic OHLCV series for testing
trading systems and quantitative research. In 2.2, the installed
`pricegenerator compare` command compares canonical series at a declared
bar interval and records their fingerprints, statistical differences,
undefined metrics and any per-metric tolerance decisions. The Russian
onboarding, migration and replay guides use market-data terminology and
retain the examples from the English guides.

## Reproduce the experiment

Install a verified 2.2.0 distribution in a clean environment. Use the
[runner from the exact tag](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v2.2.0/tools/experiment_bundle.py)
and replace its path below with the path in your checkout. Run from a writable
directory outside the checkout.

```sh
python -I /path/to/PriceGenerator/tools/experiment_bundle.py create pg-experiment
python -I /path/to/PriceGenerator/tools/experiment_bundle.py verify pg-experiment
pricegenerator compare pg-experiment/reference.csv pg-experiment/scenario.csv --timeframe-seconds 3600 --output comparison.json
```

The bundle contains two 120-bar hourly fixtures, their replay manifests, a
32-path ensemble, an offline quantile chart and a comparison report. Each
CSV replay matched its input bytes. The one-worker replay matched the
two-worker ensemble. The comparison describes these two synthetic fixtures.
Its metrics do not establish market realism.

![Pointwise close quantiles with the candles and volume of path 0](assets/pricegenerator-2-2-experiment-quantiles.svg)

The final close P05, P50 and P95 were 75.01, 101.27 and 150.46. The
corresponding quantiles of maximum drawdown across paths were 11.36%,
22.99% and 39.24%. Close quantiles describe each time step separately.
They do not give whole-path coverage.

[Experiment guide](examples/experiment-bundle.md) ·
[Comparison metrics](reference-comparison.md) ·
[Ensemble contract](monte-carlo.md)

## Verified candidate and outputs

The [Git tag](https://github.com/Fuzzy-Technologies/PriceGenerator/tree/v2.2.0)
resolves to `31c4df2b1229cdda554224d3fe6f930c94a9f99e`.
The [release workflow](https://github.com/Fuzzy-Technologies/PriceGenerator/actions/runs/42262311992)
verified clean wheel and sdist installations on CPython 3.10–3.13 with
publication disabled. The verified distribution files are in
[`release-distributions`](https://github.com/Fuzzy-Technologies/PriceGenerator/actions/runs/42262311992/artifacts/13525635990).

Separate clean wheel and sdist installs on Linux produced byte-identical
experiment bundles on CPython 3.12.14, NumPy 2.2.6 and pandas 2.2.3. The
manifests include environment metadata, so hashes can differ on other
platforms or dependency versions. This run produced the following SHA-256
values.

```text
780fea9224700a2bb1bdee9b27259276524dcbcb279c202da9bea9d5ebb7b069  scenario.csv
9255a303d141b9ba5912ca9a2c0d72e800a0129f071b7483368faa0a88a2570c  reference.csv
42481bda0bc07919c46ebd9aadd079629acb981c62735e85823f918422d5be23  ensemble.json
9f756e8c479cc362771e43daf295bec7d03374251950e70304cb1e833a6c3efb  comparison.json
688047de02f48cd5fdf981144f20ea7fd77a7693ff249dfb0c5d4c2d0d3768e0  quantiles.html
0f17b9d8168413dddf735fb2040b8d9a5b5836f767d22ff8227c4d68ece40915  SHA256SUMS
```

The SVG above was rendered from the same verified ensemble manifest. See
the [migration guide](site/content/en/migrate-to-2-1.md) for projects based
on 1.4.93 and earlier 2.x candidates, and the [release procedure](releasing.md)
for publication status.
