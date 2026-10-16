# Descriptive statistical analysis

`pricegenerator.analysis.Analyze(frame, acf_lags=10)` validates canonical OHLCV
and returns a frozen `AnalysisReport`. It does not append columns, infer a
trading calendar, alter generator configuration, consume random numbers, or
load a technical-analysis backend. `ToDict()` returns a detached representation;
`ToJSON()` is deterministic strict JSON. Undefined scalar estimates have
`value=None` and a reason. Aligned return arrays have matching reason arrays.
`Summary()` exposes the report as plain text for charts and Markdown.

```python
from pricegenerator.analysis import Analyze

report = Analyze(prices)
print(report.ToJSON())
for marginal in report.distributions:
    print(marginal.name, marginal.standard_deviation.value)
```

The report is descriptive evidence. It is not a pass/fail realism score,
a trading signal, a guarantee of suitability, or evidence of sessions,
liquidity, execution, spreads or order-book mechanics (ADR-0005).

## Estimators and domains

| Capability | Explicit convention |
| --- | --- |
| Simple close returns | `close[t]/close[t-1]-1`; previous zero and overflow become aligned nulls. Signed nonzero prices are allowed by this algebraic definition. |
| Log close returns | `log(close[t])-log(close[t-1])`; both adjacent closes must be strictly positive. |
| Marginal distributions | Simple/log returns; signed/absolute body; upper/lower wick; range; body/wick fractions of range; volume. Zero-range candle fractions are excluded as undefined. |
| Mean and variance | Arithmetic mean; sample variance and standard deviation (`ddof=1`). Fewer than two observations makes variance undefined. |
| Skewness | Adjusted Fisher-Pearson standardized third moment, `sqrt(n*(n-1))/(n-2) * m3/m2**1.5`; requires n>=3 and nonzero variance. |
| Kurtosis | Adjusted Fisher excess kurtosis: `(n-1)/((n-2)*(n-3))*((n+1)*(m4/m2**2-3)+6)`; requires n>=4 and nonzero variance. Normal reference excess is zero. |
| Quantiles | NumPy `method="linear"` at 1%, 5%, 25%, 50%, 75%, 80%, 95%, 99%. No rounding of analysis values. |
| Tail means | Inclusive empirical observations <=5% and >=95% quantiles; not an interpolated expected-shortfall estimator. |
| Outliers | Fraction strictly outside `Q1-1.5*IQR, Q3+1.5*IQR`; and fraction strictly beyond three population standard deviations from the mean. These are descriptions, not normal-distribution probability claims. |
| ACF | Observation lags 1..k; global-mean centered numerator divided by the entire centered sum of squares. Returns, absolute returns and squared returns are reported separately. |
| Domain exclusions | Each marginal records valid and excluded counts. ACF rejects a return sequence containing domain gaps rather than connecting nonadjacent observations. First-candle return warmup is excluded before ACF. |
| Volatility dependence | Absolute/squared simple-return ACF; no claim that a positive value proves a market process. |
| Drawdown | Strictly positive close paths only; `1-close/running_max(close)`, positive loss fraction. Maximum and longest consecutive underwater bar count include unrecovered terminal drawdowns. |
| Cross-variable activity | Pearson correlation of volume[t] with abs(simple return[t]), and volume with high-low range, on valid pairs. Constants/fewer than two pairs are undefined. |
| Observed path | UTC horizon, elapsed seconds, endpoint close/change/return, close range, strict up/down/doji counts, longest directional runs, total volume. Doji breaks both directional runs. |
| Time gaps | `cadence_regular` describes equality of observed timestamp differences; no session/calendar inference or resampling. ACF lags measure rows, not fixed wall-clock time. |
| Numerical limits | Moments are scaled before powers. Unrepresentable results are null estimates with reasons. Overflowed candle-derived observations increase exclusion counts. |

Historical report precision was a mutable generator setting. Modern analysis
keeps floating-point results unrounded and presentation owns price precision.
The old trend-deviation string classification is replaced by explicit endpoint
change/return and endpoint trend overlays. Historical doji counted as an up
candle; modern reports give doji its own category. Historical range standard
deviation used population normalization; the modern marginal explicitly uses
sample normalization. The retained 80% range quantile is available alongside
new tail and interquartile quantiles.

## Finite-sample acceptance policy

`ProbabilityTolerance(n, confidence=.99)` gives
`sqrt(log(2/(1-confidence))/(2*n))`, clipped to one when needed.
`ProportionInterval(successes, trials, confidence=.99)` clips the corresponding
observed-rate interval to [0,1]. Hoeffding's inequality bounds a deviation of
this size by `1-confidence` for independent Bernoulli trials. It is a
conservative finite-sample bound and requires neither asymptotic normality
nor a fitted p-value.

Choose the event definition, model/version, parameter probability, sample size,
confidence, seeds and number of simultaneous checks before running the test.
If k checks require a joint confidence, allocate failure probabilities, for
example alpha/k by the union bound. Do not repeatedly try seeds or tune bounds
after observing failures. These intervals do not validate dependent observed
market bars, rate parameters distorted by conditional generation, or a whole
model's realism. For dependent diagnostics, a separately documented resampling
model or descriptive tolerance is required.

The deterministic event test uses `default_rng(20261016)`, n=10,000,
p=0.37 and confidence=0.999. This checks the declared rule reproducibly;
it is not an exact event-count or exact p-value assertion. Generation model
probabilities must be tested against their own independent event definitions,
not inferred from a post-processed price-direction count.

## Independent evidence

`tests/test_analysis.py` contains hand/reference vectors rather than snapshots
of previous analysis output:

- `[1,2,3,4,5]` has mean3, sample variance2.5, skew0, adjusted excess
  kurtosis-1.2, 5% quantile1.2, and ACF lags1..4 `[.4,-.1,-.4,-.4]`.
- Closes `[100,110,88,132,99]` have simple returns
  `[.1,-.2,.5,-.25]` and drawdowns `[0,0,.2,0,.25]`.
- Zero/negative prices, constants, small samples, irregular cadence,
  unrepresentable finite-input arithmetic, immutability and RNG preservation
  are explicit tests.

Reproduce the analysis/indicator evidence from the repository root:

```bash
python -m pytest -q tests/test_analysis.py tests/test_indicators.py tests/test_chart_migration.py
python -m ruff check --select E4,E7,E9,F,D --ignore D202,D203,D213 pricegenerator/analysis.py pricegenerator/indicators.py pricegenerator/rendering/adapters.py tests/test_analysis.py tests/test_indicators.py tests/test_chart_migration.py
```

Definitions were checked against primary references: [NIST skewness and
kurtosis](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35b.htm),
[NIST adjusted skewness](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/skewness.htm),
[NIST observation-lag ACF](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35c.htm),
and [Hoeffding's original bounded-sum inequality](https://doi.org/10.1080/01621459.1963.10500830).

UTC horizon differences are computed with Python integer nanoseconds, so
canonical dates spanning more than292 years do not overflow pandas Timedelta.
The regression vector1700-01-01 to2200-01-01 has elapsed15,778,454,400 seconds.

## Paired upper/lower event frequencies

`SummarizeOutlierEvents(upper_flags, lower_flags, definition=...)` is a separate,
pure helper for supplied paired boolean masks. It reports upper-tail,
lower-tail, either-tail and both-tail counts and frequencies. All rates use the
number of paired candles as denominator. Masks must be aligned strict boolean
values; numeric0/1, missing values and unaligned lengths fail. Empty masks
produce zero counts and explicitly undefined frequencies.

The mandatory `definition` describes the provenance and meaning of these
particular events. For example, flags from an instrumented generator branch
and flags from a predeclared observational wick threshold are different events.
The helper does not infer latent generator branches from OHLCV magnitudes,
modify the six-column canonical schema or claim that a large realized wick
must have used an outlier branch. It supplies no confidence interval or
independence claim; apply a finite-sample event policy only when its assumptions
are independently justified.

```python
from pricegenerator.analysis import SummarizeOutlierEvents

summary = SummarizeOutlierEvents(
    [True, False, True, False],
    [False, True, True, False],
    definition="Four fixture candles with explicitly observed upper/lower events",
)
assert summary.upper_count == summary.lower_count == 2
assert summary.either_count == 3
assert summary.both_count == 1
```

The fixture distinguishes per-tail rates0.5/0.5 from per-candle union0.75 and
intersection0.25. It is event-accounting evidence, not a market-realism test.
