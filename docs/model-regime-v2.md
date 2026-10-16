# Regime v2 model and reproducibility

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

Volume is a positive continuous activity measure, not integer trade count.
Its noise follows an AR(1) log state starting at zero, with persistence
`volume_persistence` and innovation standard deviation
`volume_sigma*sqrt(1-persistence^2)`. Log volume adds `log(volume_base)` and
`volume_return_coupling` times the absolute realized log return divided by the
current sigma, capped at ten. At zero sigma this activity term is zero. Log
volume is bounded below at -700 for numerical safety and above by
`log(volume_ceiling)`; the final volume is also capped explicitly. With
persistence one the initially zero volume-noise state stays zero.

Configurations reject nonfinite inputs, naive timestamps, unknown model names,
timestamps finer than microseconds, invalid domains, horizons outside 1–1,000,000, and timestamps outside
1678–2262 UTC. Prices and volume bases/bounds lie in the positive binary64-safe
range 1e-100–1e100. Volatility and volume sigma are limited to 0–2, regime scale to
1–100, shock/wick scales to 0–100, coupling to 0–10, and drift to -2–2. These are
numerical admission limits, not empirical market estimates.

## Exact replay contract

Model ID `regime_v2` fixes draw order: regime uniform, Gaussian return, shock
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

## Evidence and limitations

`tests/test_generation_v2.py` fixes a seed-zero output fingerprint; checks schema,
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
