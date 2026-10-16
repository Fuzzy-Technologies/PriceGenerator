# Declared market-reference comparison

Metric differences describe this reference window and this one seeded scenario. No universal realism, model acceptance, calibration, forecast or market-mechanics claim. A null tolerance decision means no threshold was supplied or the metric was undefined.

Reference: tests/AFLT_day.csv (aflt-day); caller timezone: Europe/Moscow.
Selected 2775 of 2775 rows, inclusive UTC window 2010-01-11T07:00:00+00:00 to 2021-01-25T07:00:00+00:00.
Reference bytes SHA-256: `55419201cc5af61892a80df68f70b36e8dd6be9c859816e37f85a4a9227f4f09`.
Reference canonical fingerprint: `f2cd25fb70d5618a56c99808fa8fea65a35db9eff62713f10dc8fc88e700f2d6`.

Synthetic: regime_v2, seed 20261016, 2775 rows, 86400 seconds per observation, initial price 100.
Synthetic canonical fingerprint: `3e509e7c9259578e849074b4b82a99840ba09a3f8f0c71339a31cce9604ddb4b`.
Scenario identity fingerprint: `6f431fbcb4e0b438c2909b2eb7def54226c99eb79092a2ed9be67c346fbaeb44`.

Parameters were not fitted. Calendar dates, session gaps, price level and volume units were not aligned or rescaled. Different row counts or timestamp spacing remain explicit.

| Metric | Reference | Synthetic | Synthetic − reference | Absolute tolerance | Within tolerance |
| --- | ---: | ---: | ---: | ---: | --- |
| log_return_mean | 9.6776766e-05 | 0.00010077334 | 3.9965713e-06 | not supplied | not assessed |
| log_return_std | 0.020994409 | 0.022448651 | 0.0014542425 | not supplied | not assessed |
| body_fraction_mean | 0.4407612 | 0.45897352 | 0.01821232 | not supplied | not assessed |
| volume_mean | 2902682.6 | 12832.492 | -2889850.1 | not supplied | not assessed |
| squared_return_acf_lag1 | 0.11287194 | 0.13067626 | 0.017804322 | not supplied | not assessed |
| volume_absolute_return_correlation | 0.35302455 | 0.13655005 | -0.2164745 | not supplied | not assessed |
| maximum_drawdown | 0.75422222 | 0.73467236 | -0.019549864 | not supplied | not assessed |

Undefined metrics retain reasons in the JSON summaries. Supplied tolerances apply only to the listed metrics; absent thresholds make no acceptance decision.

The JSON artifact includes full configuration, model/RNG/library identity, environment, source/window fingerprints, distribution tails and observation-lag dependence diagnostics.

Reproduce from the repository root:

```bash
python -m tools.compare_market tests/AFLT_day.csv --format aflt-day --timezone Europe/Moscow --config docs/evidence/reference-aflt-config.json --output docs/evidence/reference-aflt.json --markdown docs/evidence/reference-aflt.md
```
