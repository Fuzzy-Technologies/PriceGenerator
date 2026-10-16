"""Generate bounded-memory chunks and atomically exchange validated OHLCV CSV."""

from datetime import timedelta
from itertools import islice
import os
from pathlib import Path
from random import Random
import tempfile

import pandas as pd

from pricegenerator.config import GenerationConfig
from pricegenerator.io import _WriteCanonicalCSV
from pricegenerator.market_data import OHLCV_COLUMNS, TimestampRange, ValidateOHLCV
from pricegenerator.models import GenerateRows


def GenerateChunks(config, *, chunk_size=10_000):
    """Yield canonical chunks preserving the exact complete-generation sequence.

    A single row iterator owns all model and RNG state for this invocation.
    Chunk size changes memory use, never stochastic consumption or timestamps.
    Validation occurs when iteration begins, before the first chunk is emitted.
    """

    if not isinstance(config, GenerationConfig):
        raise TypeError("GenerateChunks requires a GenerationConfig")

    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer, never a boolean")

    rows = GenerateRows(config, Random(config.seed))
    offset = 0

    while offset < config.horizon:
        values = list(islice(rows, min(chunk_size, config.horizon - offset)))

        if not values:
            raise RuntimeError("The generation model stopped before the configured horizon")

        frame = pd.DataFrame(values, columns=OHLCV_COLUMNS[1:], dtype="float64")
        start = config.start + timedelta(seconds=offset * config.timeframe_seconds)
        frame.insert(0, "datetime", TimestampRange(start, len(values), config.timeframe_seconds))
        offset += len(values)

        yield ValidateOHLCV(frame, timeframe_seconds=config.timeframe_seconds, allow_gaps=False)


def WriteCSVChunks(chunks, destination, *, timeframe_seconds=None, allow_gaps=True):
    """Atomically replace a CSV path after validating every chunk and boundary.

    An existing destination survives iteration, validation, writing, flushing,
    and replacement failures. A temporary file in the destination directory is
    removed on failure. The destination's parent directory must already exist.
    """

    path = Path(destination)
    temporary_path = None
    previous_timestamp = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            _WriteCanonicalCSV(ValidateOHLCV(pd.DataFrame(columns=OHLCV_COLUMNS)), stream)

            for chunk in chunks:
                canonical = ValidateOHLCV(
                    chunk, timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
                )

                if canonical.empty:
                    continue

                if previous_timestamp is not None:
                    boundary = canonical.iloc[:1].copy()
                    previous = boundary.copy()
                    previous.loc[previous.index[0], "datetime"] = previous_timestamp
                    ValidateOHLCV(
                        pd.concat([previous, boundary], ignore_index=True),
                        timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
                    )

                previous_timestamp = canonical.datetime.iloc[-1]
                _WriteCanonicalCSV(canonical, stream, header=False)

            # Reject invalid policies even when the supplied iterator is empty.
            ValidateOHLCV(
                pd.DataFrame(columns=OHLCV_COLUMNS),
                timeframe_seconds=timeframe_seconds, allow_gaps=allow_gaps,
            )
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, path)
        temporary_path = None

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
