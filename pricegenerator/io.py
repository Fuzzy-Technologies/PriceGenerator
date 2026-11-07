"""Read and write strict headered v2 OHLCV CSV without locale or timezone guesses."""

import csv
from contextlib import nullcontext
import os
import re

import pandas as pd

from pricegenerator.market_data import OHLCV_COLUMNS, OHLCVError, ValidateOHLCV


NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


def _TextStream(source, mode):
    """Own path-based UTF-8 streams and leave caller-owned text streams open."""

    if isinstance(source, (str, bytes, os.PathLike)):
        return open(source, mode, encoding="utf-8", newline="")

    return nullcontext(source)


def ReadCSV(source, *, assume_timezone=None, timeframe_seconds=None, allow_gaps=True):
    """Read exact headered OHLCV CSV from a path or caller-owned text stream."""

    rows = []

    try:
        with _TextStream(source, "r") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)

            if header != list(OHLCV_COLUMNS):
                raise OHLCVError("CSV header must be datetime,open,high,low,close,volume")

            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(OHLCV_COLUMNS):
                    raise OHLCVError(f"CSV row {line_number} must contain exactly six fields")

                if any(NUMBER_PATTERN.fullmatch(value) is None for value in row[1:]):
                    raise OHLCVError(f"CSV row {line_number} contains an invalid numeric field")

                rows.append([row[0], *(float(value) for value in row[1:])])

    except (csv.Error, UnicodeError) as error:
        raise OHLCVError("CSV is not valid UTF-8 comma-separated text") from error

    return ValidateOHLCV(
        pd.DataFrame(rows, columns=OHLCV_COLUMNS),
        assume_timezone=assume_timezone, timeframe_seconds=timeframe_seconds,
        allow_gaps=allow_gaps,
    )


def WriteCSV(frame, destination, *, assume_timezone=None, timeframe_seconds=None, allow_gaps=True, volume_as_count=False):
    """Write exact OHLCV values, with optional integer spelling for whole volumes."""

    canonical = ValidateOHLCV(
        frame, assume_timezone=assume_timezone,
        timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
    )

    if volume_as_count and canonical.volume.mod(1).ne(0).any():
        raise OHLCVError("count volume output requires whole volume values")

    with _TextStream(destination, "w") as stream:
        _WriteCanonicalCSV(canonical, stream, volume_as_count=volume_as_count)


def _WriteCanonicalCSV(canonical, stream, *, header=True, volume_as_count=False):
    """Serialize already validated rows to an open stream with an optional header."""

    writer = csv.writer(stream, lineterminator="\n")

    if header:
        writer.writerow(OHLCV_COLUMNS)

    for row in canonical.itertuples(index=False, name=None):
        # The canonical UTC nanosecond dtype makes NumPy emit all nine digits.
        instant = str(row[0].asm8) + "Z"
        volume = int(row[-1]) if volume_as_count else row[-1]
        writer.writerow((instant, *row[1:-1], volume))
