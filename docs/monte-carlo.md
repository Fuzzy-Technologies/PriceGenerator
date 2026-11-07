# Seeded Monte Carlo ensembles

The CLI and the module-qualified Python API in `pricegenerator.monte_carlo`
run bounded ensembles with the same selected regime model as `Generate`.
The default `regime_v3` uses whole synthetic volume counts.

```bash
pricegenerator monte-carlo --seed 42 --horizon 240 --paths 256 --workers 2 --output ensemble.json --manifest experiment.json --chart quantiles.html
pricegenerator replay-ensemble experiment.json --workers 1 --output replayed.json --chart quantiles.svg
```

The report goes to stdout if `--output` is omitted. The chart uses a real
sample path, path 0, for the candles and volume. The P05, P50 and P95 overlays
aggregate closes across all 256 paths. Select offline HTML or static SVG by
extension, or use `.png` or `.jpeg` with `pricegenerator[export]`. The existing
chart adapters accept timestamps with up to millisecond precision. CLI chart
exports leave the browser closed.

```python
from dataclasses import replace

from pricegenerator import Generate, GenerationConfig
from pricegenerator.monte_carlo import ChartEnsemble, CreateEnsembleManifest, DerivePathSeed, ReplayEnsemble, RunEnsemble

config = GenerationConfig(seed=42, horizon=240)
report = RunEnsemble(config, path_count=256)
p05, median, p95 = report.close_quantiles
drawdown_p05, drawdown_median, drawdown_p95 = report.drawdown_quantiles
manifest = CreateEnsembleManifest(report)
assert ReplayEnsemble(manifest) == report
ChartEnsemble(report, "quantiles.svg")

path_index = 17
path = Generate(replace(config, seed=DerivePathSeed(config.seed, path_index)))
```

The runner accepts 2 to 10,000 paths and up to 1,000,000 total candles across
those paths. It defaults to serial execution and retains the close matrix for
exact sample quantiles. Set `workers` to 2–8 to use spawned processes. Call
parallel Python runs from an importable script with an `if __name__ == "__main__":`
entry guard. The CLI handles this itself. For a notebook or interactive Python
session, use `workers=1`. Each worker generates one full OHLCV path at a time
and returns only the closes. Worker count has no effect on the reported values
or fingerprints. Startup overhead may dominate small jobs.

Each path has the same start time, timeframe and horizon. Rebuilding one path
requires the original configuration and zero-based path index.

## Seed derivation and run metadata

`pricegenerator-monte-carlo-path-seed-v1` hashes an ASCII payload made of the
scheme name, the root seed and the path index on separate lines, each ending
with LF. Both integers use lowercase hexadecimal without a `0x` prefix, and
a negative root seed retains its minus sign. The entire SHA-256 digest is
interpreted as an unsigned big-endian integer. Increasing the number of
paths leaves the derived seeds and generated data of earlier paths intact.

`report.ToDict()` records the configuration with its root seed, path count,
seed scheme, RNG, software environment and metric conventions alongside the
numeric summary. The separate `CreateEnsembleManifest` payload records these
inputs plus versioned SHA-256 fingerprints for the input identity and numeric
summary. The output fingerprint hashes little-endian binary64 values in this
order: all close quantile series in level order, path-indexed drawdown maxima,
then drawdown quantiles. It covers the reported results. For verification of
every OHLCV value in one path, use `CreateManifest` and `Replay` with that path's
derived configuration.

`ReplayEnsemble` verifies the complete manifest and matches its result
fingerprint against the regenerated summary. An environment change requires
`strict_environment=False` in Python or `--allow-environment-change` on the
CLI. Either still requires exact equality of the result fingerprint. The
manifest schema, library version and metric version must match.

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
