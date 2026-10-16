"""Exercise schema, scientific invariants, and explicit time policy at the boundary."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from pricegenerator.market_data import (
    OHLCV_COLUMNS, OHLCVError, TimeframeNanoseconds, ToDatetimeIndex, ValidateOHLCV,
)


def Candles():
    """Return a small valid series independent of the machine timezone."""

    return pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=3, freq="s", tz="UTC"),
        "open": [1., 2., -1.], "high": [3., 4., 1.],
        "low": [0., 1., -3.], "close": [2., 3., -2.],
        "volume": [0., 10.5, 20.],
    })


def test_CanonicalSchemaIsDetachedAndColumnBased():
    """Detach values, discard incidental indexes, and normalize schema order."""

    original = Candles().iloc[:, ::-1]
    original.index = [9, 8, 7]
    canonical = ValidateOHLCV(original)
    assert tuple(canonical.columns) == OHLCV_COLUMNS
    assert canonical.index.equals(pd.RangeIndex(3))
    assert str(canonical.datetime.dtype) == "datetime64[ns, UTC]"
    assert all(str(canonical[name].dtype) == "float64" for name in OHLCV_COLUMNS[1:])
    canonical.loc[0, "close"] = 9
    assert original.iloc[0]["close"] == 2


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_RejectMalformedSchema(mutation):
    """Reject extra, missing, and duplicated wire fields."""

    frame = Candles()

    if mutation == "missing":
        frame = frame.drop(columns="close")

    elif mutation == "extra":
        frame["unused"] = 0

    else:
        frame.columns = ["datetime", "open", "high", "low", "close", "close"]

    with pytest.raises(OHLCVError, match="six unique"):
        ValidateOHLCV(frame)


@pytest.mark.parametrize("column,value", [
    ("close", np.nan), ("open", np.inf), ("volume", -np.inf),
    ("volume", -1), ("high", 0), ("low", 2), ("close", True),
    ("volume", "12"), ("open", 1 + 2j),
])
def test_RejectInvalidNumericAndGeometricValues(column, value):
    """Reject missing/nonfinite values, invalid geometry, and coerced scalar types."""

    frame = Candles()
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = value

    with pytest.raises(OHLCVError):
        ValidateOHLCV(frame)


@pytest.mark.parametrize("values", [
    ["2024-01-01T00:00:01Z", "2024-01-01T00:00:00Z", "2024-01-01T00:00:02Z"],
    ["2024-01-01T00:00:00Z"] * 3,
    ["2024-01-01T00:00:00Z", "2024-01-01T00:00:01", "2024-01-01T00:00:02Z"],
    ["2024-01-01T00:00:00.1234567891Z"] * 3,
    ["2500-01-01T00:00:00Z"] * 3,
    [0, 1, 2], [None] * 3, ["01/02/2024"] * 3,
])
def test_RejectAmbiguousOrUnorderedTimestamps(values):
    """Reject inferred units/formats, mixed awareness, bad precision and ordering."""

    frame = Candles()
    frame["datetime"] = values

    with pytest.raises(OHLCVError):
        ValidateOHLCV(frame, assume_timezone="UTC")


def test_NaiveTimestampsRequireAnExplicitTimezone():
    """Localize only when the caller supplies a timezone policy."""

    frame = Candles()
    frame["datetime"] = frame.datetime.dt.tz_localize(None)

    with pytest.raises(OHLCVError, match="assume_timezone"):
        ValidateOHLCV(frame)

    result = ValidateOHLCV(frame, assume_timezone="Europe/Berlin")
    assert result.datetime.iloc[0] == pd.Timestamp("2023-12-31T23:00:00Z")


@pytest.mark.parametrize("local_time", ["2024-03-10T02:30:00", "2024-11-03T01:30:00"])
def test_RejectDSTNonexistentAndAmbiguousLocalTimes(local_time):
    """Reject spring gaps and autumn folds instead of silently selecting an instant."""

    frame = Candles().iloc[:1].copy()
    frame["datetime"] = [local_time]

    with pytest.raises(OHLCVError, match="unambiguously"):
        ValidateOHLCV(frame, assume_timezone="America/New_York")


def test_MixedOffsetsPreserveInstantsAndNanoseconds():
    """Normalize offset-aware timestamps while retaining submillisecond precision."""

    frame = Candles()
    frame["datetime"] = [
        "2024-01-01T01:00:00.123456789+01:00",
        "2024-01-01T02:00:01.123456789+02:00",
        "2024-01-01T00:00:02.123456789Z",
    ]
    result = ValidateOHLCV(frame, timeframe_seconds=1, allow_gaps=False)
    assert result.datetime.iloc[0].nanosecond == 789
    assert result.datetime.iloc[0].microsecond == 123456


@pytest.mark.parametrize("timeframe", [0, -1, True, np.bool_(False), np.nan, np.inf, "1", 1e20, 1e-10])
def test_RejectInvalidTimeframes(timeframe):
    """Reject nonpositive, nonnumeric, nonfinite, overflowing and sub-ns intervals."""

    with pytest.raises(OHLCVError):
        ValidateOHLCV(Candles(), timeframe_seconds=timeframe)


def test_GapPolicyRequiresWholeIntervalsAndExplicitContinuity():
    """Allow skipped candles only on the declared regular time grid."""

    frame = Candles()
    frame.loc[2, "datetime"] += pd.Timedelta(seconds=1)
    ValidateOHLCV(frame, timeframe_seconds=1)

    with pytest.raises(OHLCVError, match="spacing"):
        ValidateOHLCV(frame, timeframe_seconds=1, allow_gaps=False)

    with pytest.raises(OHLCVError, match="spacing"):
        ValidateOHLCV(frame, timeframe_seconds=2)

    with pytest.raises(OHLCVError, match="requires"):
        ValidateOHLCV(frame, allow_gaps=False)

    assert TimeframeNanoseconds(.1) == 100_000_000


def test_TimeframeDifferencesDoNotOverflowSignedNanoseconds():
    """Allow widely separated timestamps without wrapping signed int64 subtraction."""

    frame = Candles().iloc[:2].copy()
    frame["datetime"] = [datetime(1700, 1, 1), datetime(2200, 1, 1)]
    result = ValidateOHLCV(frame, assume_timezone="UTC", timeframe_seconds=1)
    assert len(result) == 2


def test_EmptyTablesAndExplicitDatetimeIndexHelper():
    """Preserve a typed empty schema and expose index state only through a helper."""

    empty = ValidateOHLCV(pd.DataFrame(columns=OHLCV_COLUMNS))
    assert str(empty.datetime.dtype) == "datetime64[ns, UTC]"
    indexed = ToDatetimeIndex(Candles())
    assert isinstance(indexed.index, pd.DatetimeIndex)
    assert indexed.index.name == "datetime"
    assert list(indexed.columns) == list(OHLCV_COLUMNS[1:])

    with pytest.raises(OHLCVError):
        ValidateOHLCV(indexed)


def test_TimestampStorageIsDetachedAndSubNanosecondObjectsAreRejected():
    """Detach datetime storage and reject precision pandas would otherwise truncate."""

    original = Candles()
    canonical = ValidateOHLCV(original)
    canonical.loc[0, "datetime"] = pd.Timestamp("2025-01-01T00:00:00Z")
    assert original.datetime.iloc[0] == pd.Timestamp("2024-01-01T00:00:00Z")
    precise = original.iloc[:1].copy()
    precise["datetime"] = pd.Series([np.datetime64("1970-01-01T00:00:00.000000000001", "ps")], dtype=object)

    with pytest.raises(OHLCVError, match="finer"):
        ValidateOHLCV(precise)


def test_MultiCenturyContinuityFallbackRejectsOffGridAndContinuousClaims():
    """Retain exact policy checks when timestamp spans exceed signed int64."""

    frame = Candles().iloc[:2].copy()
    frame["datetime"] = pd.to_datetime(["1700-01-01T00:00:00Z", "2200-01-01T00:00:00Z"])

    with pytest.raises(OHLCVError, match="spacing"):
        ValidateOHLCV(frame, timeframe_seconds=1, allow_gaps=False)

    frame.loc[frame.index[1], "datetime"] += pd.Timedelta(nanoseconds=1)

    with pytest.raises(OHLCVError, match="spacing"):
        ValidateOHLCV(frame, timeframe_seconds=1)


@pytest.mark.parametrize("start,periods,step", [
    ("2024-01-01T00:00:00", 3, 1),
    ("2024-01-01T00:00:00Z", True, 1),
    ("2262-04-11T23:47:16Z", 2, 1),
])
def test_TimestampBuilderRejectsInvalidDomains(start, periods, step):
    """Keep invalid timezone, row-count, and absolute-range inputs explicit."""

    from pricegenerator.market_data import TimestampRange

    with pytest.raises(OHLCVError):
        TimestampRange(start, periods, step)
