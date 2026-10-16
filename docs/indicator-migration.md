# Modern indicators and chart analysis migration

`pricegenerator.indicators` implements the retained indicator set with NumPy
and pandas only. It has no pandas-ta import, compatibility switch, generator
instance, mutable statistics dictionary, or hidden analysis during rendering.
`Indicators(frame)` returns an immutable `IndicatorReport`; `.series` contains
aligned immutable values, labels, keys, and line/point metadata. `.ToJSON()`
uses standard JSON null for all warmup/domain gaps. Each report series includes
an aligned `reasons` tuple distinguishing warmup, inactive PSAR direction,
zero-volume windows, absent confirmed pivots, domain errors and overflow.

```python
from pricegenerator.analysis import Analyze
from pricegenerator.indicators import Indicators
from pricegenerator.rendering.adapters import FromDataFrame, MarketOverlays

analysis = Analyze(prices)
indicators = Indicators(prices)
chart = FromDataFrame(prices, series=MarketOverlays(prices), summary=analysis.Summary())
```

`FromDataFrame` remains a pure snapshot conversion. `MarketOverlays` is an
explicit calculation request; it combines the modern indicators and retained
nonindicator overlays. A modern chart entry point may offer `analysis=True`
to make these same explicit calculations. `BuildLegacyChart`, old statistics
calls and the TA backend fallback have been removed. Historical characterization
is evidence, not an executable compatibility mode.

## Retained capability mapping

| Historical capability | Modern route and deliberate convention |
| --- | --- |
| Statistics/report/Markdown | `Analyze(frame)` and `.Summary()`; `RenderMarkdown(spec)` / `SaveMarkdown(spec,path)`. See [estimator definitions](analysis.md). |
| SMA5/20/50/200 | `SMA(values,period)` and keys `sma5`, `sma20`, `sma50`, `sma200`; full trailing arithmetic windows. |
| HMA5/20 | `HMA(values,period)` and keys `hma5`, `hma20`; Hull WMA formula, half-period and square-root periods truncated to integers, both at least1. Always unshifted. |
| VWMA5/20 | `VWMA(values,volume,period)`; complete windows, `sum(price*volume)/sum(volume)`. Zero volume sums are null, never equal-weight substituted. |
| Bollinger lower/mid/upper | `Bollinger(values,20,2)` returns the three tuples; keys `bbands-lower`, `bbands-mid`, `bbands-upper`. Population window deviation (`ddof=0`), SMA center. |
| PSAR long/short points | `PSAR(high,low,step=.02,maximum=.2)`; keys `psar-long`, `psar-short`; each direction has separate nulls. Defined two-bar initialization below. |
| Historical HMA-based Alligator | Replaced deliberately by median-price SMMA Alligator, keys `alligator-jaw`, `alligator-teeth`, `alligator-lips`: periods13/8/5, forward row shifts8/5/3. It does not share or overwrite ordinary HMA arrays. |
| Zig-Zag | `ZigZag(close,deviation=.05)` confirms percentage-reversal extrema. Key `zigzag` is interpolated between confirmed pivots only by `MarketOverlays`, using elapsed UTC time. The evolving final extreme is omitted. Positive complete closes required; otherwise all values are null. This is not the historical filter's selected-point sequence. |
| Close maximum/minimum | `MarketOverlays`: keys `close-max`, `close-min`, complete unrounded close limits. |
| Full-horizon trend | `MarketOverlays`: `trend`, elapsed-time line connecting first/last closes. This is endpoint geometry, not fitted regression or a forecast. |
| Split trends | `MarketOverlays(frame,split_counts=(...))`: `trend-segment-N`; positive integer counts must sum exactly to candle count, no extrapolation outside each segment. |
| High/low average line + points | `MarketOverlays`: `midpoint-line` and `midpoint-points`, arithmetic `(high+low)/2`, no precision rounding or new canonical column. |
| Text markers and custom lines | `FromDataFrame(markers=...,lines=...)` aligns exact UTC timestamps, rejects absent/duplicate annotation timestamps, and preserves sparse gaps; no interpolation of custom lines. |
| Notebook display | `NotebookHTML(spec)` and explicit `DisplayChart(spec,format='html'/'svg')`; notebook display stays optional. |

Technical overlays start hidden, while close limits and endpoint trends are
visible. They remain ordinary `ChartSeries` objects and can be presented with
explicit visibility preferences. No canonical OHLCV frame gains indicator,
`avg`, `up`, `delta` or temporary calculation columns.

## Calculation and gap conventions

Period and displacement count observed rows. A timestamp gap is retained;
no calendar rows are inserted. Missing numeric values are supported by the
individual indicator functions (canonical OHLCV itself rejects them).
Rolling functions require complete windows. SMMA and PSAR restart after a
missing observation. Report notes identify null warmup, missing/domain input,
and arithmetic-overflow conventions. Outputs never contain Infinity or NaN.

SMMA seeds each contiguous run with an n-row arithmetic mean, then computes
`previous*(n-1)/n + current/n`. Alligator uses median price `(high+low)/2`,
not close or HMA; forward shifts move existing results to later existing rows
and omit those beyond the horizon. No future timestamp or backfill is created.

PSAR uses a documented deterministic variant because initialization differs
across packages. The first bar of a contiguous segment has no SAR. The first
two bars choose upward direction when upward high movement is at least
downward low movement (ties upward). Initial SAR is the minimum of both lows
for upward direction or maximum of both highs for downward direction; initial
extreme is the maximum high/minimum low. From the third bar onward:

1. Advance SAR toward the prior extreme using the current acceleration factor.
2. Clamp upward SAR to the prior two lows, downward SAR to prior two highs.
3. A strict low-below/high-above penetration reverses direction. Reversal SAR
   is the previous trend's extreme; new extreme is the current low/high and
   acceleration resets to step.
4. Otherwise a new extreme increases acceleration by step, capped at maximum.

Equal touches do not reverse. Step and cap require `0 < step <= maximum <= 1`.
The two-bar initialization and separate gaps are intentional contracts, not
assertions of bitwise equivalence to any historical backend.

## Independent formula evidence

`tests/test_indicators.py` fixes the conventions with hand arithmetic:
SMA/WMA on1..8, unshifted HMA5 with half2/sqrt2, unequal/zero activity VWMA,
Bollinger population deviation, SMA-seeded SMMA recursion, displaced median
Alligator, PSAR acceleration/clamps/two reversals, and confirmed Zig-Zag pivots.
It checks missing inputs, short windows, invalid policies, immutable reports,
strict JSON, canonical nonmutation and Python/NumPy RNG preservation.

Definitions were checked against [Alan Hull's original formula](https://alanhull.com/the-hull-moving-average/),
[MetaTrader's SMMA Alligator definition](https://www.metatrader5.com/en/terminal/help/indicators/bw_indicators/alligator),
and [MetaTrader's Parabolic SAR recurrence](https://www.metatrader5.com/en/terminal/help/indicators/trend_indicators/psar).
[John Bollinger's own construction notes](https://www.bollingerbands.com/bollinger-bands)
specify population standard deviation; this API explicitly fixes `ddof=0`
rather than relying on a package default.

Extreme-volume evidence also covers period-one identity across prices1e308 and
1e-308, a small-volume rolling window following a1e308 activity observation,
and opposing price/activity scales where both weighted products matter.
VWMA uses local windows; rare extreme-magnitude windows use standard-library
Decimal arithmetic with800 significant digits before returning float64 values.
It never normalizes an entire history by a distant price/volume extreme.
