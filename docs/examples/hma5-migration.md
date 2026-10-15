# HMA 5: historical shift and explicit correction

Calculated by the real TA backend: HMA(close, length=5, offset=None) and offset=3.
Legacy GetStatistics overwrites HMA 5 with Alligator lips, shifting both displayed lines.
BuildLegacyChart preserves that behavior by default; hma5_mode=&#x27;unshifted&#x27; corrects only HMA 5.
Warmup periods remain gaps. A shift is three candles, including across a session gap.
