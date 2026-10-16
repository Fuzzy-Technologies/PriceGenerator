# Canonical OHLCV data

PriceGenerator v2 exchanges one explicit six-column table, in this order:

| Column | Canonical pandas dtype | Domain |
| --- | --- | --- |
| `datetime` | `datetime64[ns, UTC]` | Unique, strictly increasing UTC instants |
| `open`, `high`, `low`, `close` | `float64` | Finite real values satisfying candle geometry |
| `volume` | `float64` | Finite, nonnegative values, including fractional volume |

`pricegenerator.market_data.ValidateOHLCV(frame, *, assume_timezone=None,
timeframe_seconds=None, allow_gaps=True)` returns a detached canonical frame
with a fresh RangeIndex. Input must contain exactly these six unique columns;
input column order is normalized. Empty frames are supported. Invalid inputs
raise `OHLCVError`, a `ValueError` subclass. Numeric strings, booleans, complex
numbers, missing values and infinities are rejected. Prices may be zero or
negative. Geometry requires `high >= max(open, close)`,
`low <= min(open, close)` and `high >= low`.

Datetime inputs accept Python/pandas/NumPy timestamps and ISO 8601 strings with
seconds, up to nine fractional digits, and an optional explicit `Z` or `±HH:MM`
offset. Numeric epoch values and locale-dependent date strings are rejected.
Canonical timestamps use pandas' nanosecond range, from
`1677-09-21T00:12:43.145224193Z` through
`2262-04-11T23:47:16.854775807Z`; higher precision and out-of-range values fail.
Offset-aware inputs normalize to UTC without changing their instant. Inputs
must not mix aware and naive timestamps. Naive timestamps require explicit
`assume_timezone`, such as `"UTC"` or `"America/New_York"`. Ambiguous DST folds
and nonexistent DST local times fail; no machine-local timezone is consulted.

No timeframe is inferred. When `timeframe_seconds` is supplied, it must be a
finite positive real number exactly representable in whole nanoseconds and no
larger than pandas' maximum Timedelta. Booleans are rejected. Timestamp gaps
must be whole multiples of the declared interval. `allow_gaps=False` requires
a timeframe and exactly one interval between adjacent rows. This validates a
regular grid, not exchange sessions or a holiday calendar. With the default
`allow_gaps=True` and no timeframe, only strict chronological order is required.

`ToDatetimeIndex(frame, *, assume_timezone=None, timeframe_seconds=None,
allow_gaps=True)` applies the same validation and returns the five numeric
columns with a UTC DatetimeIndex named `datetime`. This is an explicit pandas
helper; the index is not the portable data schema. Put it back in a column with
`reset_index()` before passing it to canonical APIs.

# CSV exchange

`pricegenerator.io.ReadCSV(source, *, assume_timezone=None,
timeframe_seconds=None, allow_gaps=True)` and
`WriteCSV(frame, destination, *, assume_timezone=None,
timeframe_seconds=None, allow_gaps=True)` share the validation policy above.
Paths use UTF-8. Caller-owned text streams are supported and remain open.
Filesystem I/O errors propagate as `OSError` subclasses; malformed CSV,
decoding failures and invalid data raise `OHLCVError`.

CSV requires the exact header `datetime,open,high,low,close,volume`, in that
order, followed by exactly six fields per record. Headerless 1.x files and
alternative delimiters are unsupported. Numeric fields use decimal notation
with an optional sign and exponent; whitespace and locale-specific formatting
are rejected. Date formats, timezone and numeric timestamp units are never
guessed. Reading validates every row through the same canonical boundary.
Writing validates before opening the destination, emits timestamps with nine
fractional digits and `Z`, and uses round-trippable float64 representations.
All finite float64 values, including subnormals and signed zero, round-trip
exactly. The writer does not retain a source timezone's presentation offset;
its UTC instant is retained.

The v2 APIs replace the historical mutable loader/saver methods and their
headerless CSV format. Historical datasets must be converted deliberately to
the six headered fields with an explicit timezone policy. No legacy runtime or
command alias is retained. This follows [ADR-0002](adr/0002-canonical-ohlcv-market-data-contract.md)
and [ADR-0007](adr/0007-v2-breaking-change-and-migration-policy.md).
