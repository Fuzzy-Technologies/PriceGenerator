# Regime models and reproducibility

`Generate(GenerationConfig(...))` returns a new canonical OHLCV DataFrame. The
configuration is frozen, JSON serializable through `ToDict`/`FromDict`, and has
fixed defaults: seed zero and 2000-01-01 00:00 UTC. Construction and generation
neither draw from nor seed the process-global RNG. Each call owns a fresh
`random.Random(seed)` MT19937 engine, including its Gaussian cache.

## Declared stochastic semantics

All parameters are per candle; changing the timeframe does not rescale them.
A scenario begins in the calm volatility regime. Before each candle, a symmetric
two-state Markov chain changes state with probability `1-regime_persistence`.
The current return standard deviation is `volatility` in calm state and
`volatility*regime_scale` in stressed state. Drift is constant, not a latent drift
regime or a promise about the final endpoint.

The proposed log return is
`drift + current_sigma*Z + volatility*shock_scale*B*Z_shock`, where the two normals
are independent and `B` is an independent Bernoulli draw with
`shock_probability`. That probability counts return-shock events per candle.

Prices are strictly positive and remain within `price_floor`/`price_ceiling`.
Proposals outside the log-price interval reflect at its boundaries (repeatedly
when necessary). In-domain proposals are left alone. Opens equal the previous
close exactly; the first open is `initial_price`. No final candle is replaced to
force a trend endpoint. Near boundaries, reflected realized returns differ from
the unbounded proposal distribution.

Each wick extends from the body by `current_sigma*wick_scale*abs(Z_wick)` in log
price. Independent upper and lower Bernoulli draws each have
`wick_outlier_probability`; an active draw multiplies that tail's extent by
`wick_outlier_scale`. This is a **per-tail probability**, separate from return
shocks. Before boundary clipping, the chance of either tail receiving the
multiplier is `1-(1-p)^2`, and the chance of both is `p^2`. Wick prices stop at the
configured price bounds. There is no fixed candle-body-size parameter.

The volume calculation starts with a continuous activity level. Its noise
follows an AR(1) log state starting at zero, with persistence
`volume_persistence` and innovation standard deviation
`volume_sigma*sqrt(1-persistence^2)`. Log volume adds `log(volume_base)` and
`volume_return_coupling` times the absolute realized log return divided by the
current sigma, capped at ten. At zero sigma this activity term is zero. Log
volume is bounded below at -700 for numerical safety and above by
`log(volume_ceiling)`; the final volume is also capped explicitly. With
persistence one the initially zero volume-noise state stays zero.

The default `regime_v3` rounds that bounded level to the nearest integer
(ties to even) and limits the result to `[1, volume_ceiling]`. The base is a
scale of at least 1 and can be fractional. The ceiling must be a whole
number up to `2**53 - 1`, so each count is exact in the canonical binary64
column. The CLI writes the count as an integer in generated and replayed
CSV files. It is a synthetic activity count with no observed ticks, trade
events or instrument units behind it. Imported asset quantities can be
fractional and retain their source units and values.

Explicit `model="regime_v2"` retains the prior continuous output. The two
models use the same random draws and produce identical timestamps and OHLC
for the same configuration within their shared domain.

Configurations reject nonfinite inputs, naive timestamps, unknown model names,
timestamps finer than microseconds, invalid domains, horizons outside 1–1,000,000, and timestamps outside
1678–2262 UTC. Prices and continuous-model volume bases/bounds lie in the positive
binary64-safe range 1e-100–1e100. Volatility and volume sigma are limited to 0–2, regime scale to
1–100, shock/wick scales to 0–100, coupling to 0–10, and drift to -2–2. These are
numerical admission limits, not empirical market estimates.

## Exact replay contract

Both model IDs fix the draw order: regime uniform, Gaussian return, shock
uniform, Gaussian shock, upper-tail uniform and Gaussian wick, lower-tail uniform
and Gaussian wick, then Gaussian volume innovation. Inactive events still consume
their prescribed draws. Changed stochastic formulas or random consumption require
a new model identifier.

`CreateManifest(config, data=None, metadata=None)` records complete inputs, seed,
model, private RNG identity, library version, Python implementation/version,
platform, pandas/NumPy versions, optional JSON provenance, and two SHA-256 hashes.
`scenario_fingerprint` identifies the complete deterministic inputs plus an
optional fitted `profile_reference`; `fingerprint` identifies canonical output.
Different seeds/configurations can produce the same flat output while retaining
distinct scenario identities. Free-form metadata notes are not generation inputs.
Supplying data avoids generating twice; `Replay` verifies that its recorded hash
actually matches the declared generation inputs. The output fingerprint encodes
UTC nanosecond integers and `float.hex` binary64 values in a versioned compact JSON
row stream; the incidental pandas index is excluded.

`Replay(manifest)` requires matching environment and library identity by default.
`strict_environment=False` explicitly permits a different environment while still
requiring both the original scenario identity hash and exact output hash. The
recorded environment remains immutable; only the execution environment may differ.
This is verification of portability, not a claim
that all Python/libm/platform combinations produce bit-identical floating values.

## How this differs from 1.4.93

In [the 1.4.93 source](https://github.com/Fuzzy-Technologies/PriceGenerator/blob/v1.4.93/pricegenerator/PriceGenerator.py),
`upCandlesProb` selects the body direction. The close is sampled uniformly
within its side's allowed body size and close bounds. Each wick is sampled
uniformly up to half the body or the configured outlier distance. The code
rounds prices to the configured decimal precision. Volume is an integer
draw from a range based on the previous volume and capped by `maxVolume`.
A configured up/down/flat segment can change direction probabilities and
rewrite its final close to enforce the requested outcome.

The regime models use log returns with drift, two volatility states and
occasional shocks. Opens still equal the previous close. Prices respect
bounds and the final close is left to the model. Volatility state describes
the size of price moves rather than an up/down trend. Display precision is
independent of an instrument's tick size. The generator has no exchange
session calendar, bid/ask spread, order book or intrabar tick sequence.

## Evidence and limitations

The [scripted numerical oracles](../tests/test_regime_v2_oracles.py) check three
candles across two scenarios against hand-derived OHLCV values with relative
tolerance `1e-12`. The first scenario switches from calm to stressed and back,
exercises the return-shock and wick-outlier thresholds, and checks AR(1) volume.
The second reflects a price proposal twice and checks that volume uses the
realized return while both wicks clip at the configured bounds. Both tests
check draw order and consumption, including inactive events.

`tests/test_generation_v2.py` fixes a seed-zero output fingerprint for each model; checks schema,
continuity, extreme positive bounds, flat/drift-only dynamics and noninterference;
records 100,000 actual private-engine event traces and checks all four Bernoulli
rates with predeclared six-standard-deviation binomial bounds; and tests
upper/lower tail independence. Reproducible Gaussian-mixture wick exceedances use
30,000 candles with the same six-sigma rule. A 40,000-candle return-shock test
checks the analytical mean and mixture variance (8% relative variance tolerance).
A separate 30,000-candle scenario checks positive absolute-return clustering and
volume/activity association.

These tests establish structural validity and the implemented statistical
semantics. They do not establish similarity to any exchange, asset class,
liquidity process, session calendar, or empirical return distribution. Price
reflection and volume caps are explicit test-scenario boundary policies.
Historical 1.x golden rows and known defects are archived evidence only; no
legacy generator is selectable through this runtime.

Use the [independent holdout protocol](reference-comparison.md#independent-holdout-protocol)
for claims about observed market data.
