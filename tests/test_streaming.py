"""Verify exact chunk equivalence and atomic streaming CSV failure semantics."""

from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest

from pricegenerator.config import GenerationConfig
from pricegenerator.generation import Generate
from pricegenerator.io import ReadCSV
from pricegenerator.market_data import OHLCV_COLUMNS, OHLCVError
from pricegenerator.streaming import GenerateChunks, WriteCSVChunks
import pricegenerator.streaming as streaming


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 20, 21, 100])
def test_ChunksPreserveExactStateAcrossEveryPartition(chunk_size):
    """Preserve regime, return, cached Gaussians, volume state, and time offsets."""

    config = GenerationConfig(
        horizon=21, seed=0,
        start=datetime(2024, 10, 1, 0, 0, 0, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        timeframe_seconds=7, regime_persistence=.4, shock_probability=.8,
        volume_persistence=.9, wick_outlier_probability=.7,
    )
    chunks = list(GenerateChunks(config, chunk_size=chunk_size))
    actual = pd.concat(chunks, ignore_index=True)
    pd.testing.assert_frame_equal(actual, Generate(config), check_exact=True)
    assert all(len(chunk) <= chunk_size for chunk in chunks)
    assert all(chunk.index.equals(pd.RangeIndex(len(chunk))) for chunk in chunks)


@pytest.mark.parametrize("chunk_size", [0, -1, True, False, 1.5, "10", None])
def test_RejectInvalidChunkSizes(chunk_size):
    """Reject booleans, nonintegers, and nonpositive chunk bounds."""

    with pytest.raises(ValueError, match="positive integer"):
        list(GenerateChunks(GenerationConfig(), chunk_size=chunk_size))


def test_ChunksAreLazyAndIndependentOfGlobalRandomState(monkeypatch):
    """Do not pre-generate future rows, and keep concurrent iterators independent."""

    real_rows = streaming.GenerateRows
    observed = []

    def ObservedRows(config, rng):
        """Count actual model steps instead of relying on allocation heuristics."""

        for row in real_rows(config, rng):
            observed.append(row)

            yield row

    monkeypatch.setattr(streaming, "GenerateRows", ObservedRows)
    config = GenerationConfig(horizon=11)
    iterator = GenerateChunks(config, chunk_size=3)
    assert observed == []
    first = next(iterator)
    assert len(first) == len(observed) == 3
    second = list(GenerateChunks(config, chunk_size=8))
    actual = pd.concat([first, *iterator], ignore_index=True)
    pd.testing.assert_frame_equal(actual, pd.concat(second, ignore_index=True), check_exact=True)


def test_PrematureModelTerminationIsExplicit(monkeypatch):
    """Detect a failed row model instead of silently returning fewer candles."""

    monkeypatch.setattr(streaming, "GenerateRows", Mock(return_value=iter([])))

    with pytest.raises(RuntimeError, match="stopped"):
        list(GenerateChunks(GenerationConfig()))


def test_AtomicChunkCSVMatchesCompleteGeneration(tmp_path):
    """Write exactly one header and preserve every generated scalar across chunks."""

    config = GenerationConfig(horizon=27)
    path = tmp_path / "scenario.csv"
    path.write_text("old")
    WriteCSVChunks(
        GenerateChunks(config, chunk_size=4), path,
        timeframe_seconds=config.timeframe_seconds, allow_gaps=False,
    )
    pd.testing.assert_frame_equal(ReadCSV(path), Generate(config), check_exact=True)
    assert path.read_text().count("datetime,open,high,low,close,volume") == 1
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("defect", ["overlap", "reverse", "gap", "invalid", "iterator"])
def test_FailedChunkLeavesDestinationAndCleansTemporaryFile(tmp_path, defect):
    """Preserve existing data on cross-boundary, numeric, and producer failures."""

    config = GenerationConfig(horizon=6)
    frame = Generate(config)
    first = frame.iloc[:3]
    second = frame.iloc[3:].copy()

    if defect == "overlap":
        second.loc[second.index[0], "datetime"] = first.datetime.iloc[-1]

    elif defect == "reverse":
        second["datetime"] -= pd.Timedelta(days=1)

    elif defect == "gap":
        second["datetime"] += pd.Timedelta(hours=1)

    elif defect == "invalid":
        second.loc[second.index[0], "volume"] = -1

    def Chunks():
        """Emit a valid prefix before exercising the selected failure branch."""

        yield first

        if defect == "iterator":
            raise RuntimeError("producer failed")

        yield second

    path = tmp_path / "existing.csv"
    path.write_text("preserved")

    with pytest.raises((OHLCVError, RuntimeError)):
        WriteCSVChunks(Chunks(), path, timeframe_seconds=config.timeframe_seconds, allow_gaps=False)

    assert path.read_text() == "preserved"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("operation", ["fsync", "replace", "serialize"])
def test_AtomicFilesystemAndSerializationFailuresCleanUp(tmp_path, monkeypatch, operation):
    """Preserve existing data when writing, flushing, or replacement fails."""

    path = tmp_path / "existing.csv"
    path.write_text("preserved")
    failure = Mock(side_effect=OSError("injected failure"))

    if operation == "serialize":
        monkeypatch.setattr(streaming, "_WriteCanonicalCSV", failure)

    else:
        monkeypatch.setattr(streaming.os, operation, failure)

    with pytest.raises(OSError, match="injected"):
        WriteCSVChunks(GenerateChunks(GenerationConfig(horizon=3)), path)

    assert path.read_text() == "preserved"
    assert list(tmp_path.iterdir()) == [path]


def test_EmptyChunksAndEmptyIteratorRetainCanonicalHeader(tmp_path):
    """Permit empty data, while validating declared policies even without rows."""

    path = tmp_path / "empty.csv"
    WriteCSVChunks([pd.DataFrame(columns=OHLCV_COLUMNS)], path)
    assert ReadCSV(path).empty

    with pytest.raises(OHLCVError):
        WriteCSVChunks([], path, timeframe_seconds=True)

    assert ReadCSV(path).empty


def test_InvalidConfigurationAndMissingParentFailClearly(tmp_path):
    """Reject foreign configs and unavailable destinations without side effects."""

    with pytest.raises(TypeError, match="GenerationConfig"):
        list(GenerateChunks({}))

    with pytest.raises(FileNotFoundError):
        WriteCSVChunks([], tmp_path / "absent" / "file.csv")

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 4])
@pytest.mark.parametrize("start", [
    datetime(1700, 1, 1, tzinfo=timezone.utc),
    datetime(1700, 1, 1, microsecond=123456, tzinfo=timezone.utc),
])
def test_MultiCenturyTimestampSpansPreserveEveryPartition(chunk_size, start):
    """Avoid date_range overflow when valid absolute instants span centuries."""

    config = GenerationConfig(horizon=3, start=start, timeframe_seconds=6_307_200_000)
    complete = Generate(config)
    partitioned = pd.concat(GenerateChunks(config, chunk_size=chunk_size), ignore_index=True)
    pd.testing.assert_frame_equal(partitioned, complete, check_exact=True)
    expected = [pd.Timestamp(start) + timedelta(seconds=index * config.timeframe_seconds) for index in range(3)]
    assert complete.datetime.tolist() == expected
    assert complete.datetime.iloc[2].year == 2099
