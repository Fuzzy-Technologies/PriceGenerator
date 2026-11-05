# Bitstamp BTC/USD chronological holdout

The question is how a restricted moment fit of `regime_v2` transfers across
one chronological split and how the fixed fuzzy profile behaves on the same
unseen market window. The comparison summarizes simulated and observed
distributions and the score on unlabeled data.

## Source

Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle, version 706,
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
The [archival snapshot](https://github.com/ff137/bitstamp-btcusd-minute-data/tree/0bbc1f9f4dde50520e3ee2d1fba1b26fc3bb217e)
records the [data terms](https://github.com/ff137/bitstamp-btcusd-minute-data/blob/0bbc1f9f4dde50520e3ee2d1fba1b26fc3bb217e/DATA_LICENSE)
and [acquisition manifest](https://github.com/ff137/bitstamp-btcusd-minute-data/blob/0bbc1f9f4dde50520e3ee2d1fba1b26fc3bb217e/data/original/source-manifest.json).
The archived portion comes from the Kaggle dataset, with normalized headers
and a cutoff before the maintainer's separate API updates. Prices are
unadjusted USD per BTC from Bitstamp, and volume is BTC.

Download the [gzip archive](https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/0bbc1f9f4dde50520e3ee2d1fba1b26fc3bb217e/data/historical/btcusd_bitstamp_1min_2012-2025.csv.gz)
from the pinned source commit. Its SHA-256 is
`1be152060b39327b669cbed236eeb283191fadaf3862f76c1e974be54ceb1a20`.
The raw archive and individual OHLCV observations are kept outside this
repository. Aggregate derived evidence is provided with the source attribution
and under CC BY-SA 4.0. Code remains under the project license.

## Frozen recipe

- Treat source Unix timestamps as UTC minute opens. Aggregate each UTC hour
  as first open, highest high, lowest low, last close and sum of archived BTC
  volume. Require a regular hourly timeline across both windows with at least
  one source row per hour. Count missing minute slots and preserve the source
  gaps.
- Fit on `[2024-09-01, 2024-10-01)` UTC. Score
  `[2024-10-01, 2024-11-01)` UTC at the same hourly cadence, with each
  synthetic trajectory starting at the last training close.
- Use the existing restricted moment profile. Fit body log-return drift and
  population volatility and mean hourly volume from training. The profile
  disables regime scaling, jumps, wick outliers and volume noise/coupling.
  Wick scale and price bounds retain the base configuration's defaults.
  Evaluate seeds 0 through 15 without selection or adjustment.
- For the seven `comparison_v1` metrics, set only two illustrative
  per-seed absolute tolerances. Set 25% of the training population standard
  deviation of log close-to-close returns as the tolerance for the held-out
  sample standard deviation. For mean hourly volume, use 25% of the training
  mean. The thresholds illustrate the procedure. The other five metrics
  remain descriptive, and degenerate metrics retain their undefined status.
- Freeze fuzzy reference levels to the same training close-to-close
  population standard deviation and arithmetic mean hourly volume. For each
  disjoint 24-hour UTC holdout window, compute those statistics using only
  its 24 bars and 23 returns. Record the full trace from the real
  FuzzyRoutines 2.1.0 scalar backend, the count of input ratios clipped above
  2 and empirical score quantiles at 5%, 50% and 95% using linear
  interpolation. The dataset is unlabeled, so evaluate scores descriptively.

## Reproduce

In Python 3.13 with the scalar extra installed, run the frozen recipe from
the checkout root with the pinned archive and a new output file:

```bash
python -m pip install -c requirements/modern.txt '.[fuzzy]'
python -m tools.evaluate_bitstamp_holdout btcusd_bitstamp_1min_2012-2025.csv.gz --output bitstamp-holdout.json
```

The report records exact data and recipe hashes, canonical window fingerprints,
environment versions, all seed manifests and metric decisions, and the
holdout fuzzy traces. Exact replay uses the recorded numerical environment.

## Results

The archive supplied 87,840 minute rows for these dates, with no absent
minute slots in the file. The source project notes that flat zero-volume
minute bars can represent either no trading or upstream data gaps. The hourly
transformation preserves the source rows as provided.

The September fit used 720 hourly bars. October supplied 744 hourly bars
and 743 close-to-close returns. Each of the 16 simulated paths has the
same 744 bars and 743 returns. These are the observed holdout statistic
and empirical percentiles across the 16 synthetic statistics.

| Metric                                        | Observed | Synthetic P05 | Median    | P95       | Absolute tolerance | Runs within |
| --------------------------------------------- | -------: | ------------: | --------: | --------: | -----------------: | ----------: |
| Log-return mean                               | 0.000135 | −0.000132     | 0.000175  | 0.000307  | —                  | —           |
| Log-return sample standard deviation          | 0.004368 | 0.004572      | 0.004683  | 0.004892  | 0.001173           | 16/16       |
| Mean candle body fraction                     | 0.4832   | 0.4603        | 0.4650    | 0.4812    | —                  | —           |
| Mean hourly volume (BTC)                      | 67.45    | 71.93         | 71.93     | 71.93     | 17.98              | 16/16       |
| Squared simple-return ACF at lag one          | 0.3345   | −0.0497       | −0.0089   | 0.0395    | —                  | —           |
| Volume and absolute simple-return correlation | 0.5219   | Undefined     | Undefined | Undefined | —                  | —           |
| Maximum close-based drawdown                  | 0.0720   | 0.0565        | 0.0959    | 0.1555    | —                  | —           |

The restricted fit keeps synthetic volume constant, so its volume/return
correlation is undefined in every seed. The observed squared-return ACF
also lies outside the simulated P05–P95 range. The two tolerance results
therefore describe only the selected marginal statistics. The percentiles
summarize the distribution across these 16 runs.

The 31 complete UTC days had fuzzy score P05, median and P95 of 0.250,
0.250 and 0.490. Exactly one day exceeded the input clipping point of 2
for volatility and exactly one for activity. These are separate counts.
The fuzzy profile ran separately as a descriptive diagnostic, with no
external labels for evaluating regime detection.

The [machine report](reference-bitstamp-holdout.json) records every seed,
metric and fuzzy trace. It was generated with PriceGenerator 2.0.0 from the
2.1 development branch, CPython 3.13.17, pandas 2.2.3, NumPy 2.2.6 and the
scalar FuzzyRoutines 2.1.0 backend. The separate
[AFLT comparison](../reference-comparison.md#bundled-aflt-fixture)
remains an unfitted, single-seed description with weaker source provenance.
