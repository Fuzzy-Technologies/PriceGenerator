"""Verify strict portable CSV exchange and exact floating-point/time round trips."""

from io import StringIO

import numpy as np
import pandas as pd
import pytest

from pricegenerator.io import ReadCSV, WriteCSV
from pricegenerator.market_data import OHLCV_COLUMNS, OHLCVError, ValidateOHLCV


HEADER = "datetime,open,high,low,close,volume\n"
ROW = "2024-01-01T00:00:00Z,1,3,0,2,0\n"


def test_RoundTripRetainsEveryFloatBitAndNanosecond(tmp_path):
    """Retain extremes, signed zero, UTC instants, and nanoseconds across CSV."""

    values = [np.nextafter(1., 2.), np.finfo(float).tiny, np.finfo(float).max, -0.]
    frame = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01T00:00:00.123456789", periods=4, freq="ns", tz="Asia/Kolkata"),
        **{name: values for name in ("open", "high", "low", "close")},
        "volume": [0., .1, np.nextafter(0., 1.), np.finfo(float).max],
    })
    path = tmp_path / "candles.csv"
    WriteCSV(frame, path)
    restored = ReadCSV(path)
    expected = ValidateOHLCV(frame)
    pd.testing.assert_frame_equal(restored, expected, check_exact=True)
    assert restored.close.to_numpy().view(np.uint64).tolist() == expected.close.to_numpy().view(np.uint64).tolist()
    assert ".123456789Z" in path.read_text()
    assert path.read_text().startswith(HEADER)


def test_CallerOwnedStreamsRemainOpenAndEmptyTablesRoundTrip():
    """Support text streams without taking ownership and preserve empty schemas."""

    stream = StringIO()
    WriteCSV(pd.DataFrame(columns=OHLCV_COLUMNS), stream)
    assert not stream.closed
    stream.seek(0)
    assert ReadCSV(stream).empty
    assert not stream.closed


@pytest.mark.parametrize("content", [
    "", ROW, HEADER.replace("volume", "close") + ROW,
    HEADER.replace("datetime", "date") + ROW,
    "close,open,high,low,datetime,volume\n" + ROW,
    HEADER + ROW.rstrip(",0\n") + "\n", HEADER + ROW.rstrip("\n") + ",0\n",
    HEADER + ROW.replace(",1,", ",True,"), HEADER + ROW.replace(",1,", ",nan,"),
    HEADER + ROW.replace(",1,", ", 1,"), HEADER + ROW.replace(",1,", ",1_000,"),
    HEADER + ROW.replace("00:00:00Z", "00:00:00"),
    HEADER + '\"unterminated', HEADER + "\n",
])
def test_RejectMalformedHeadersRowsAndValues(content):
    """Reject legacy headerless files, corrupted headers, malformed rows and guesses."""

    with pytest.raises(OHLCVError):
        ReadCSV(StringIO(content))


def test_ExplicitTimezoneCanLocalizeNaiveCSV():
    """Apply the same explicit naive-time policy to CSV and in-memory tables."""

    frame = ReadCSV(StringIO(HEADER + ROW.replace("00:00:00Z", "00:00:00")), assume_timezone="UTC")
    assert frame.datetime.iloc[0] == pd.Timestamp("2024-01-01T00:00:00Z")


def test_ReadFailuresPreserveFilesystemCauseAndDecodeErrorsAreExplicit(tmp_path):
    """Expose file I/O failures and wrap malformed UTF-8 as invalid CSV."""

    with pytest.raises(FileNotFoundError):
        ReadCSV(tmp_path / "missing.csv")

    invalid = tmp_path / "invalid.csv"
    invalid.write_bytes(b"\xff\xfe")

    with pytest.raises(OHLCVError, match="UTF-8"):
        ReadCSV(invalid)


def test_InvalidFrameDoesNotTruncateExistingDestination(tmp_path):
    """Validate completely before opening a destination for writing."""

    path = tmp_path / "existing.csv"
    path.write_text("keep")

    with pytest.raises(OHLCVError):
        WriteCSV(pd.DataFrame(), path)

    assert path.read_text() == "keep"
