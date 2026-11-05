"""Check the research recipe's aggregation, split and leakage controls offline."""

from gzip import compress
from hashlib import sha256

import pandas as pd
import pytest

from pricegenerator import Generate, GenerationConfig
from tools import evaluate_bitstamp_holdout as experiment


def test_ObservedMinutesAreAggregatedWithoutFillingGaps(tmp_path, monkeypatch):
    """Preserve observed minute OHLCV and reject archives with different bytes."""

    start = experiment.START
    end = start + pd.Timedelta(hours=2)
    instant = int(start.timestamp())
    rows = (
        "timestamp,open,high,low,close,volume\n"
        f"{instant},10,12,9,11,5\n"
        f"{instant + 180},11,16,10,15,7\n"
        f"{instant + 3660},12,15,10,11,8\n"
    )
    archive = tmp_path / "minutes.csv.gz"
    archive.write_bytes(compress(rows.encode("ascii")))
    monkeypatch.setattr(experiment, "END", end)
    monkeypatch.setattr(experiment, "SOURCE_SHA256", sha256(archive.read_bytes()).hexdigest())

    bars, observed = experiment.ReadHourlyBars(archive)

    assert observed == 3, "The recipe must count observations without filling gaps"
    assert bars["datetime"].tolist() == [start, start + pd.Timedelta(hours=1)]
    assert bars.drop(columns="datetime").to_numpy().tolist() == [
        [10.0, 16.0, 9.0, 15.0, 12.0],
        [12.0, 15.0, 10.0, 11.0, 8.0],
    ], "Hourly OHLCV must summarize only the observed minute rows"

    archive.write_bytes(compress(rows.replace(",11,8", ",11,9").encode("ascii")))

    with pytest.raises(ValueError, match="pinned Bitstamp archive SHA-256"):
        experiment.ReadHourlyBars(archive)


def test_HoldoutChangesDoNotChangeTheFrozenRecipe(monkeypatch, tmp_path):
    """A withheld shock must change comparison evidence without refitting the recipe."""

    start = experiment.START
    split = start + pd.Timedelta(hours=24)
    end = split + pd.Timedelta(hours=24)
    bars = Generate(GenerationConfig(start=start.to_pydatetime(), horizon=48, seed=42))
    monkeypatch.setattr(experiment, "SPLIT", split)
    monkeypatch.setattr(experiment, "END", end)
    monkeypatch.setattr(experiment, "SEEDS", (0,))

    def ReadFixture(archive):
        """Supply an isolated input fixture without contacting the source archive."""

        return bars.copy(), 48 * 60

    def CaptureFuzzyReference(holdout, reference):
        """Capture the scoring boundary without requiring the optional extra."""

        return {"first_scored_bar": holdout["datetime"].iloc[0].isoformat(), "reference": reference}

    monkeypatch.setattr(experiment, "ReadHourlyBars", ReadFixture)
    monkeypatch.setattr(experiment, "AssessFuzzy", CaptureFuzzyReference)

    before = experiment.BuildEvidence(tmp_path / "unused.csv.gz")
    bars.loc[24:, "volume"] *= 100
    bars.loc[24:, ["open", "high", "low", "close"]] *= 2
    after = experiment.BuildEvidence(tmp_path / "unused.csv.gz")

    assert before["training"] == after["training"], "Withheld observations must not change training identity"
    assert before["tolerances"] == after["tolerances"], "Withheld observations must not change tolerances"
    assert before["fuzzy"] == after["fuzzy"], "Fuzzy references must be frozen at the chronological boundary"
    assert before["runs"][0]["manifest"] == after["runs"][0]["manifest"], "Withheld prices must not seed generation"
    assert before["runs"][0]["metrics"] != after["runs"][0]["metrics"], "Withheld changes must reach the comparison"
