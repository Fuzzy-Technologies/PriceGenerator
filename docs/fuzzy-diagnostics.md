# Experimental fuzzy market diagnostics

Install the optional scalar backend in a Python 3.13 environment.

```bash
python -m pip install '.[fuzzy]'
```

The extra pins FuzzyRoutines 2.1.0. Generation and replay work on the existing
Python 3.10–3.13 core. The integration uses the scalar API because the
FuzzyRoutines NumPy extra requires NumPy `>=2.3.5,<3`, while PriceGenerator
currently requires `>=2.0,<2.3`.

```python
import json

from pricegenerator.fuzzy_diagnostics import DiagnoseRegime

report = DiagnoseRegime(volatility_ratio=1.75, activity_ratio=1.75)
print(json.dumps(report.ToDict(), allow_nan=False, indent=2))
```

## Inputs and rule profile

Use dimensionless ratios from an observed window and positive reference levels.
One choice is the population standard deviation of consecutive log close
returns divided by reference volatility, and mean candle volume divided by
reference mean volume. Use consistent cadence and a reference available at the
observation time. Keep the source window, reference window and feature
definitions with your experiment. The diagnostic receives the two already
computed ratios.

The `relative-market-stress-v1` profile evaluates both inputs on the closed
domain `[0, 2]`. For an evaluated coordinate `r`, the ordinary grade is
`1 - max(0, r - 1)` and the elevated grade is `max(0, r - 1)`. An observed
ratio above 2 evaluates at 2. The report retains the observed ratio and the
evaluated coordinate.

| Volatility | Activity | Consequent |
| --- | --- | --- |
| Ordinary | Ordinary | Calm |
| Ordinary | Elevated | Watch |
| Elevated | Ordinary | Watch |
| Elevated | Elevated | Stress |

Each rule uses minimum conjunction and weight 1. The consequent terms are
triangles on `[0, 1]` with left, peak and right coordinates
`(0, 0.25, 0.5)`, `(0.25, 0.5, 0.75)` and `(0.5, 0.75, 1)`.
Mamdani clips each triangle at its firing strength, takes the pointwise maximum
and computes the aggregate centroid numerically. In the example, the rule
strengths are 0.25, 0.25, 0.25 and 0.75. Integrating the piecewise linear
envelope gives area 23/64 and first moment 27/128. Their ratio is 27/46,
approximately 0.58696.

The report includes the profile and engine versions, input grades, all rules,
and the centroid method. The score is a descriptive index for these fixed,
illustrative thresholds. Empirical calibration and holdout validation belong
to a separate evaluation of the profile. Changes to thresholds, rules or
inference policy require a new profile identifier. Diagnostic calls consume no
RNG and are separate from generation parameters, manifests and replay.
