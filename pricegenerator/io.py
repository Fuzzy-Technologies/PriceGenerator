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


def WriteCSV(frame, destination, *, assume_timezone=None, timeframe_seconds=None, allow_gaps=True):
    """Write UTC nanosecond timestamps and exactly round-trippable float64 values."""

    canonical = ValidateOHLCV(
        frame, assume_timezone=assume_timezone,
        timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
    )

    with _TextStream(destination, "w") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(OHLCV_COLUMNS)

        for row in canonical.itertuples(index=False, name=None):
            timestamp = row[0]
            instant = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
            instant += f".{timestamp.value % 1_000_000_000:09d}Z"
            writer.writerow([instant, *(repr(value) for value in row[1:])])
