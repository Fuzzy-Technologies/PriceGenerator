# Compare a declared market reference with an unfitted scenario

`python -m tools.compare_market` evaluates a caller-selected historical-data
window against one independently generated `regime_v2` scenario. It uses the
modern canonical reader, `Generate`, `Compare` and scenario manifest APIs.
No historical runtime, indicator backend, fitting, seed search, market-calendar
inference, gap filling, price adjustment or volume normalization is performed.

A canonical headered UTC OHLCV file is the default:

```bash
python -m tools.compare_market reference.csv --config config.json --output comparison.json --markdown comparison.md
```

`config.json` is a `GenerationConfig` JSON object. Omitted fields use library
defaults, never estimates from the reference. The complete effective
configuration, seed, model/RNG/library identity, environment, input-source
hashes and replayable scenario manifest are always recorded. With no config
file the complete library defaults apply, including its 150-row horizon.
Reference and synthetic row counts may differ and remain explicit.

Use `--start 2015-01-01T00:00:00Z --end 2016-01-01T00:00:00Z` for an inclusive
UTC reference window. Bounds require explicit offsets. The runner records both
requested and actual endpoints, source row positions, total/selected counts,
raw source-byte SHA-256 and the canonical selected-window fingerprint. It
parses exactly the bytes that it hashes. It does not interpolate missing rows.

Optional `--tolerances tolerances.json` accepts predeclared absolute thresholds
for the modern comparison metrics, for example:

```json
{"log_return_std": 0.005, "volume_absolute_return_correlation": 0.1}
```

Choose thresholds before inspecting the evaluation window. Unlisted metrics
receive no decision, and undefined statistics cannot pass. Defaults supply
no thresholds and make no acceptance claim. Exit status zero means the
comparison executed and reports were written; it is not a global model
acceptance result. Invalid schemas, unknown metrics, malformed/duplicate JSON
keys, nonfinite values, ambiguous window timestamps and aliased input/output
paths fail explicitly. Existing inputs are never overwritten by output aliases.

The JSON contains selected marginal distributions including tails/outlier
fractions, all ten return/absolute-return/squared-return ACF lags, activity
correlations and drawdown/path summaries. It omits observation-sized vectors.
The console and optional Markdown file show the same metric table and limits.
Both outputs retain the generating command. Source hashes identify explicitly
used modern implementation modules and the recipe, not every file present in
the working directory.

## Bundled AFLT fixture

The first recorded reference is the existing `tests/AFLT_day.csv`: 2,775 rows
from 2010-01-11 to 2021-01-25. It is a headerless seven-column file containing
`YYYY.MM.DD,HH:MM[:SS],open,high,low,close,volume`.
The tool-only `--format aflt-day` adapter is explicit and requires `--timezone`.
It does not change the canonical CSV API or expose a compatibility runtime.
No instrument, venue, timezone, volume-unit or adjusted-price assertion can be
verified from this file alone. `Europe/Moscow` below is a declared assumption,
not metadata inferred from its filename. Installed pandas/pytz/tzdata versions
are recorded with that assumption; the resulting UTC fingerprint is explicit.

Reproduce the committed [machine report](evidence/reference-aflt.json) and
[human report](evidence/reference-aflt.md):

```bash
python -m tools.compare_market tests/AFLT_day.csv --format aflt-day --timezone Europe/Moscow --config docs/evidence/reference-aflt-config.json --output docs/evidence/reference-aflt.json --markdown docs/evidence/reference-aflt.md
```

The declared [configuration](evidence/reference-aflt-config.json) fixes seed
20261016, 2,775 observations, one-day synthetic intervals and a UTC start.
Other parameters, including initial price100 and volume base1000, remain
library defaults; they were not fitted to AFLT. The reference retains trading
gaps and historical timezone-offset changes, while the synthetic path uses
uniform daily intervals. Consequently the synthetic and reference elapsed
calendar horizons differ. Return diagnostics measure successive observations,
not returns normalized to a common trading-session or wall-clock duration.
Volume units, price levels and adjustment policies are not harmonized.

For this one scenario the reference/synthetic log-return standard deviations
are about0.02099/0.02245, while mean volumes are about2,902,683/12,832 and
volume/absolute-return correlations are about0.353/0.137. Numerical closeness
of one statistic does not validate the remaining distributions or dynamics.
No tolerances were supplied: every decision is `not assessed`. The evidence
is an auditable descriptive comparison, not calibration or a realism claim.

Focused validation:

```bash
python -m pytest -q tests/test_compare_market.py
python -m ruff check --select E4,E7,E9,F,D --ignore D202,D203,D213 tools/compare_market.py tests/test_compare_market.py
```
