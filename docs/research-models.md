# Model evidence, moment profiles and stress scenarios

These APIs implement the research workflows for Tasks #57, #59 and #81–#86.
All three modern models remain **experimental**. Metric tolerances are scoped
to a declared fixture and selected statistic. They do not establish general
market realism or forecast skill. Archived 1.x characterization remains in
`docs/baseline` and `docs/benchmarks`; it is evidence, never an executable model
choice in the v2 runtime.

## Reproduce the evidence

Use the locked modern environment, from the checkout root:

```bash
python -m tools.evaluate_models --output docs/evidence/research-v2.json
python -m pytest -q tests/test_research_models.py tests/test_calibration_evaluation.py
```

The committed report uses a generated training fixture with known parameters,
and a separate synthetic holdout with deliberately changed drift and volume.
It records complete inputs, fingerprints, selected independent training/evaluation
diagnostics, absolute tolerances and model manifests. Add `--full-analysis` to
include every analysis distribution and raw observation vector. The expected
held-out mismatch demonstrates that evaluation does not silently refit the
holdout. It does not demonstrate accuracy against real market data. No market
data is downloaded and no historical runtime is loaded by this command.

## Explicit profile contract

```python
from pricegenerator.calibration import ChronologicalSplit, ExtractProfile, Calibrate
from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.scenario import CreateManifest

training, holdout = ChronologicalSplit(reference, holdout_fraction=.25)
profile = ExtractProfile(training)
config = profile.ToConfig(GenerationConfig(seed=12, horizon=200))
data = Generate(config)
manifest = CreateManifest(config, data, metadata=profile.ManifestMetadata())
report = Calibrate(training, holdout, tolerances={"log_return_mean": .005})
```

`Profile.ToDict` / `Profile.FromDict` form a strict, versioned schema, including
the canonical source fingerprint, source window, regular timeframe, row count,
estimator and explicit training-only semantics. `Profile.Reference()` hashes
the entire profile; `ManifestMetadata()` records that reference, all fitted
values, fixed restrictions and unidentified parameters. The generation config
still contains every numerical input, so replay needs no opaque fitted state.

The estimator fits only candle-body log-return mean (drift), population standard
deviation (volatility), and arithmetic mean volume (volume base). Candle bodies
exclude price gaps between bars. The fitted submodel fixes regime scale to one,
shock/outlier probabilities to zero and volume noise, coupling and persistence
to zero. Wick scale, price/volume bounds and other unestimated base inputs stay
explicit assumptions. Bounds can change generated moments; calibration does
not compensate for their effect. Zero mean volume cannot fit the generator's
strictly positive volume base and is rejected.

This is an observable-moment fit under neutral restrictions, **not** an estimate
of regime transitions, shock probabilities, wick tails or volume dynamics.
Non-Gaussian body moments are summarized, not fully reproduced. Source gaps in
time are rejected. Profiles can describe subsecond data, but generation-based
calibration currently requires whole-second timeframes and microsecond-aligned
starting timestamps. Unsupported timeframe precision fails explicitly instead
of rounding provenance. Training must strictly
precede holdout, neither window may have fewer than three rows, and both must
use the same timeframe. Holdout data changes only diagnostics, its explicit
starting price and output time window; it never updates the fitted parameters.
The distinct training and evaluation seeds and manifests are in the report.

## Comparison and uncertainty

`Compare(reference, synthetic, tolerances=...)` independently analyzes each
frame and reports seven predefined metrics: log-return mean and standard
deviation, mean body fraction and volume, squared-return lag-one ACF,
volume/absolute-return correlation and maximum drawdown. Full distribution,
tail and temporal analyses remain in both independent reports. Each selected
metric reports its signed difference and absolute tolerance decision.
Undefined statistics retain analysis reasons and cannot pass a gate. Metrics
without a supplied tolerance receive no acceptance decision. There is no
aggregate score that hides failures or claims universal acceptance.

`BootstrapMeanInterval(values, seed=..., block_length=..., ...)` computes a
seeded percentile interval for the sample mean with non-circular overlapping
moving blocks. The final block is truncated to the observation count. Length
one assumes IID observations; larger blocks retain dependence only within
blocks. The report records observation count, confidence, resample count,
block length, seed and method. The interval is an approximate diagnostic, not
a finite-sample coverage guarantee. A full-length block produces the same
mean on every draw. Choosing a block length or a tolerance using holdout
results compromises evaluation independence; this utility does not automate
that choice. Independent-event proportion intervals live in `analysis.py`.

## Extended scenarios

```python
from pricegenerator.extended_models import (
    Bootstrap, BootstrapConfig, Scripted, ScriptedConfig, ScriptStep,
    CreateBootstrapManifest, ReplayBootstrap,
    CreateScriptedManifest, ReplayScripted,
)

sample = Bootstrap(reference, BootstrapConfig(seed=0, count=500, block_length=8))
manifest = CreateBootstrapManifest(reference, BootstrapConfig(seed=0, count=500, block_length=8), sample)
replayed = ReplayBootstrap(manifest, reference)

config = ScriptedConfig(count=100, drift=.001, steps=(
    ScriptStep(30, log_jump=-.2, drift=-.005, volume=5000),
    ScriptStep(60, drift=.002, volume=1000),
))
stress = Scripted(config)
stress_manifest = CreateScriptedManifest(config, stress)
```

Both functions return the same canonical OHLCV DataFrame shape as `Generate`.
They have independent immutable configurations and serializable replay
manifests. They never change the default `regime_v2` generation model.

The seeded empirical model samples source price gap, candle body, upper/lower
relative wick geometry and volume **jointly**. Blocks preserve their source
order without wrapping. The first reference row is excluded because its
previous close is unknown. Timestamp gaps are rejected; source price gaps are
sampled as part of geometry. Output timestamps follow the caller's regular
UTC cadence; session calendars are not inferred. Initial price rebases the
path. Blocks can break dependence at joins and cannot invent new empirical
tail geometry. The identical reference is required at replay and its digest
is checked, along with model, RNG, library/NumPy version and output digest.

The scripted model uses no RNG. A step's `log_jump` changes that bar's opening
price once; `drift` changes its and subsequent bars' body log return; `volume`
changes its and subsequent bars' volume. Unspecified settings persist. Steps
must have unique ascending indices inside the horizon. Relative wicks are
explicit and never invert OHLC. There is no endpoint target. Overflow or
nonpositive/nonfinite outputs fail instead of being clipped silently. Such
events have designed stress meaning, not an estimated market probability.

`registry.ListModels()` provides each model's version, RNG, supported model
parameters, suitable use cases, limitations, required evidence and current
experimental status. Core schema, time, bound, event-order and replay tests
are engineering admission checks. Stable statistical admission still needs a
declared use case, predeclared independent data windows, source licenses and
provenance, sample-size/dependence reasoning, tail/dependence checks and
review of failed metrics. These workflows provide those evidence surfaces;
they do not treat a familiar model name or a passing synthetic fixture as
scientific validation.
