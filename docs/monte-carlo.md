# Seeded Monte Carlo ensembles

The experimental Python API in `pricegenerator.monte_carlo` runs a bounded
ensemble with the same `regime_v2` engine used by `Generate`.

```python
from dataclasses import replace

from pricegenerator import Generate, GenerationConfig
from pricegenerator.monte_carlo import DerivePathSeed, RunEnsemble

config = GenerationConfig(seed=42, horizon=240)
report = RunEnsemble(config, path_count=256)
p05, median, p95 = report.close_quantiles
drawdown_p05, drawdown_median, drawdown_p95 = report.drawdown_quantiles

path_index = 17
path = Generate(replace(config, seed=DerivePathSeed(config.seed, path_index)))
```

The runner accepts 2 to 10,000 paths and up to 1,000,000 total candles across
those paths. It runs serially and retains the close matrix for exact sample
quantiles. Each path has the same start time, timeframe and horizon. Rebuilding
a single path requires only the original configuration and zero-based path
index.

## Seed derivation and run metadata

`pricegenerator-monte-carlo-path-seed-v1` hashes an ASCII payload made of the
scheme name, the root seed and the path index on separate lines, each ending
with LF. Both integers use lowercase hexadecimal without a `0x` prefix, and
a negative root seed retains its minus sign. The entire SHA-256 digest is
interpreted as an unsigned big-endian integer. Increasing the number of
paths leaves the derived seeds and generated data of earlier paths intact.

`report.ToDict()` records the configuration with its root seed, path count,
seed scheme, RNG, software environment and metric conventions. This metadata
describes a run. For exact replay verification of one path, use the existing
`CreateManifest` and `Replay` with that path's derived configuration.

## Quantile and drawdown conventions

- `close_quantiles` contains three series in order P05, P50 and P95. At
  each candle position the quantile is taken across the closes of all paths.
- `maximum_drawdowns` contains one fraction for every path in index order.
  For each close, calculate `1 - close / running_peak_close` and take the
  maximum over that path. The first close starts the running peak, so a
  one-candle path has zero drawdown. Wicks and the first open are excluded.
- `drawdown_quantiles` summarizes those per-path maxima at P05, P50 and
  P95. Both sets of quantiles use linear interpolation at rank
  `(path_count - 1) * quantile_level` in ascending sample order.

These quantiles describe synthetic outcomes conditional on the chosen model
and configuration. Pointwise P05 and P95 give a separate range at each
candle position. The range makes no claim about simultaneous coverage of
entire paths or real-market forecast accuracy.
