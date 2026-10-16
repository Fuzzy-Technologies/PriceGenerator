"""Validate the portable v2 OHLCV schema independently of generation and I/O."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from numbers import Real
import re

import numpy as np
import pandas as pd


OHLCV_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")
VALUE_COLUMNS = OHLCV_COLUMNS[1:]
ISO_DATETIME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
    r"(?:Z|[+-]\d{2}:\d{2})?\Z"
)


class OHLCVError(ValueError):
    """Report an invalid OHLCV schema, value, timestamp, or continuity policy."""


def TimeframeNanoseconds(timeframe_seconds):
    """Return an exact positive nanosecond interval within pandas' range."""

    if isinstance(timeframe_seconds, (bool, np.bool_)) or not isinstance(
        timeframe_seconds, Real
    ):
        raise OHLCVError("timeframe_seconds must be a finite positive real number")

    try:
        nanoseconds = Decimal(str(timeframe_seconds)) * Decimal(1_000_000_000)

    except InvalidOperation as error:
        raise OHLCVError("timeframe_seconds must be finite") from error

    if not nanoseconds.is_finite() or not 0 < nanoseconds <= pd.Timedelta.max.value:
        raise OHLCVError("timeframe_seconds is outside the positive nanosecond range")

    if nanoseconds != nanoseconds.to_integral_value():
        raise OHLCVError("timeframe_seconds must have exact nanosecond precision")

    return int(nanoseconds)


def TimestampRange(start, periods, timeframe_seconds):
    """Build UTC nanosecond timestamps without overflowing interval arithmetic.

    Each absolute instant must fit pandas' timestamp domain; the total span
    need not fit a signed nanosecond duration. This avoids date_range's internal
    multiplication overflow for valid multi-century series.
    """

    if type(periods) is not int or periods < 0:
        raise OHLCVError("periods must be a nonnegative integer")

    step_ns = TimeframeNanoseconds(timeframe_seconds)

    try:
        timestamp = pd.Timestamp(start)

        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise OHLCVError("start must be a valid timezone-aware timestamp")

        start_ns = timestamp.tz_convert("UTC").as_unit("ns").value

    except (ValueError, TypeError, OverflowError) as error:
        raise OHLCVError("start exceeds the supported timezone-aware nanosecond domain") from error

    span_ns = (periods - 1) * step_ns if periods else 0

    if start_ns + span_ns > pd.Timestamp.max.value:
        raise OHLCVError("timestamp range exceeds the supported nanosecond domain")

    if span_ns <= np.iinfo(np.int64).max:
        instants = np.arange(periods, dtype=np.int64) * step_ns + start_ns

    else:
        instants = np.fromiter(
            (start_ns + index * step_ns for index in range(periods)),
            dtype=np.int64, count=periods,
        )

    return pd.to_datetime(instants, utc=True)


def _DatetimeColumn(values, assume_timezone):
    """Normalize explicit datetimes to UTC without guessing timezone or units."""

    if isinstance(values.dtype, pd.DatetimeTZDtype):
        try:
            normalized = pd.DatetimeIndex(values).tz_convert("UTC").as_unit("ns")

        except (ValueError, TypeError, OverflowError) as error:
            raise OHLCVError("datetime exceeds the supported nanosecond range") from error

        return _CheckedTimestamps(normalized)

    timestamps = []
    awareness = set()

    for value in values:
        if isinstance(value, str):
            if ISO_DATETIME_PATTERN.fullmatch(value) is None:
                raise OHLCVError("datetime strings must use ISO 8601 with seconds and at most nine fractional digits")

        elif not isinstance(value, (datetime, pd.Timestamp, np.datetime64)):
            raise OHLCVError("datetime values must be timestamps or ISO 8601 strings")

        if isinstance(value, np.datetime64) and np.datetime_data(value.dtype)[0] in {"ps", "fs", "as"}:
            raise OHLCVError("datetime precision finer than nanoseconds is unsupported")

        try:
            timestamp = pd.Timestamp(value)

            if pd.isna(timestamp):
                raise OHLCVError("datetime must not contain missing timestamps")

            awareness.add(timestamp.tzinfo is not None)
            timestamps.append(timestamp)

        except (ValueError, TypeError, OverflowError) as error:
            raise OHLCVError("datetime contains an invalid timestamp") from error

    if len(awareness) > 1:
        raise OHLCVError("datetime must not mix timezone-aware and timezone-naive values")

    if awareness == {False} and assume_timezone is None:
        raise OHLCVError("timezone-naive datetime requires explicit assume_timezone")

    try:
        if awareness == {False}:
            normalized = pd.DatetimeIndex(timestamps).tz_localize(
                assume_timezone, ambiguous="raise", nonexistent="raise"
            ).tz_convert("UTC")

        else:
            normalized = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True))

        normalized = normalized.as_unit("ns")

    except Exception as error:
        # Timezone providers expose different exception classes for DST failures.
        raise OHLCVError("datetime cannot be localized unambiguously or exceeds nanosecond range") from error

    return _CheckedTimestamps(normalized)


def _CheckedTimestamps(normalized):
    """Check chronological invariants after UTC nanosecond normalization."""

    if normalized.hasnans:
        raise OHLCVError("datetime must not contain missing timestamps")

    if not normalized.is_monotonic_increasing or not normalized.is_unique:
        raise OHLCVError("datetime must be strictly increasing and unique")

    return pd.Series(normalized, name="datetime")


def _NumericColumn(values, name):
    """Copy real finite numeric values to the canonical float64 dtype."""

    if pd.api.types.is_bool_dtype(values.dtype) or pd.api.types.is_complex_dtype(values.dtype):
        raise OHLCVError(f"{name} must contain real numbers, never booleans or complex values")

    if not pd.api.types.is_numeric_dtype(values.dtype):
        if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) for value in values):
            raise OHLCVError(f"{name} must contain real numeric values")

    try:
        converted = values.to_numpy(dtype=np.float64, copy=True, na_value=np.nan)

    except (ValueError, TypeError, OverflowError) as error:
        raise OHLCVError(f"{name} cannot be represented as float64") from error

    if not np.isfinite(converted).all():
        raise OHLCVError(f"{name} must contain only finite values")

    return converted


def ValidateOHLCV(frame, *, assume_timezone=None, timeframe_seconds=None, allow_gaps=True):
    """Return detached canonical UTC OHLCV data or raise ``OHLCVError``.

    Timestamps support pandas' nanosecond range. Naive values require a named
    timezone or explicit tzinfo; ambiguous and nonexistent local times fail.
    A declared timeframe requires whole-interval spacing; disallowing gaps
    additionally requires exactly one interval between successive candles.
    """

    if not isinstance(frame, pd.DataFrame):
        raise OHLCVError("OHLCV input must be a pandas DataFrame")

    if not frame.columns.is_unique or len(frame.columns) != len(OHLCV_COLUMNS) or set(frame.columns) != set(OHLCV_COLUMNS):
        raise OHLCVError("OHLCV requires exactly six unique columns: datetime, open, high, low, close, volume")

    if not isinstance(allow_gaps, bool):
        raise OHLCVError("allow_gaps must be a boolean")

    if not allow_gaps and timeframe_seconds is None:
        raise OHLCVError("allow_gaps=False requires timeframe_seconds")

    timeframe_ns = None if timeframe_seconds is None else TimeframeNanoseconds(timeframe_seconds)
    timestamps = _DatetimeColumn(frame["datetime"], assume_timezone)
    numeric = {name: _NumericColumn(frame[name], name) for name in VALUE_COLUMNS}

    if (numeric["volume"] < 0).any():
        raise OHLCVError("volume must be nonnegative")

    if ((numeric["high"] < np.maximum(numeric["open"], numeric["close"])) | (numeric["low"] > np.minimum(numeric["open"], numeric["close"])) | (numeric["high"] < numeric["low"])).any():
        raise OHLCVError("OHLC values violate high/low geometric bounds")

    if timeframe_ns is not None:
        instants = timestamps.array.asi8

        if len(instants) > 1 and int(instants[-1]) - int(instants[0]) <= np.iinfo(np.int64).max:
            # Monotonicity bounds every difference by this overflow-safe span.
            differences = np.diff(instants)
            invalid = differences % timeframe_ns != 0 if allow_gaps else differences != timeframe_ns

            if invalid.any():
                raise OHLCVError("datetime spacing violates the declared timeframe/gap policy")

        elif len(instants) > 1:
            # Rare multi-century series exceed signed-int64 subtraction's domain.
            for previous, current in zip(instants[:-1], instants[1:]):
                difference = int(current) - int(previous)

                if difference % timeframe_ns != 0 or (not allow_gaps and difference != timeframe_ns):
                    raise OHLCVError("datetime spacing violates the declared timeframe/gap policy")

    return pd.DataFrame({"datetime": timestamps, **numeric}, columns=OHLCV_COLUMNS)


def ToDatetimeIndex(frame, *, assume_timezone=None, timeframe_seconds=None, allow_gaps=True):
    """Return a validated detached pandas view with an explicit UTC DatetimeIndex."""

    canonical = ValidateOHLCV(
        frame, assume_timezone=assume_timezone,
        timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
    )

    return canonical.set_index("datetime")
