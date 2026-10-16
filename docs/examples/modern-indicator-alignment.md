# Modern indicator alignment: HMA and Alligator

Seeded regime_v2 fixture: seed20261016, 96 half-hour observations; no realism claim.
A deliberate two-day session gap and four zero-volume observations were added after generation.
The UTC axis preserves the session gap. Indicators count observations without resampling.
HMA5 is unshifted: WMA(2WMA(close,2)-WMA(close,5),2). Warmup values remain gaps.
Alligator uses median-price SMMA: jaw13 shifted8, teeth8 shifted5, lips5 shifted3 observations.
Each SMMA starts from its complete SMA seed. Forward shifts use existing rows across the gap.
These are independent calculations; Alligator never overwrites HMA5.
