# PriceGenerator 2.2.0 experiment evidence

[Release notes](../release-2-2.md) · [Experiment instructions](../examples/experiment-bundle.md)

The example generates two 120-bar hourly series and 32 simulated paths. Both
CSV replays matched the originals. Replaying with one worker reproduced the
two-worker ensemble report. The final close quantiles were 75.01, 101.27 and
150.46. The quantiles of maximum drawdown across paths were 11.36%, 22.99% and
39.24%.

## Whole-count example

The current [release chart](../assets/pricegenerator-2-2-experiment-quantiles.svg)
was rendered from a freshly generated bundle using CPython 3.14.6, NumPy 2.3.5
and pandas 2.3.3. The bundle verification passed. Both CSV replays matched
byte for byte and single-worker replay reproduced the two-worker ensemble.
The scenario CSV has SHA-256
`ac9f95833b6d2d9818a04d6036fa3f64df73c179615cd893ba5c5a9ad456df47`.

## Earlier continuous-volume candidate

The release run and checksums below describe the earlier `regime_v2` candidate.
The current worked example and illustrations use `regime_v3`, which emits
whole synthetic volume counts. The price paths and close quantiles are
identical between these models at the same inputs. Volume values and bundle
checksums differ.

### Verified candidate and outputs

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

The [archived chart](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/2b1f8b7881e9be38b0722e2998afd57d5e1779c6/docs/assets/pricegenerator-2-2-experiment-quantiles.svg)
was rendered from the earlier verified ensemble manifest. See the
[release procedure](../releasing.md) for publication status.
