"""Evaluate a frozen chronological BTC/USD holdout using a verified offline archive."""

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pricegenerator.calibration import ExtractProfile
from pricegenerator.config import GenerationConfig
from pricegenerator.evaluation import Compare
from pricegenerator.fuzzy_diagnostics import DiagnoseRegime
from pricegenerator.generation import Generate
from pricegenerator.market_data import ValidateOHLCV
from pricegenerator.scenario import CreateManifest, Environment, Fingerprint


SOURCE_COMMIT = "0bbc1f9f4dde50520e3ee2d1fba1b26fc3bb217e"
SOURCE_SHA256 = "1be152060b39327b669cbed236eeb283191fadaf3862f76c1e974be54ceb1a20"
START, SPLIT, END = pd.to_datetime(["2024-09-01", "2024-10-01", "2024-11-01"], utc=True)
SEEDS = tuple(range(16))
TOLERANCE_FRACTION = 0.25
HOURS_PER_WINDOW = 24
QUANTILES = (0.05, 0.5, 0.95)


def ReadHourlyBars(archive: Path) -> tuple[pd.DataFrame, int]:
    """Read the pinned source and aggregate archived minute bars without filling gaps."""

    with archive.open("rb") as source:
        digest = sha256()

        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)

        if digest.hexdigest() != SOURCE_SHA256:
            raise ValueError("Archive bytes do not match the pinned Bitstamp archive SHA-256")

        source.seek(0)
        lower, upper = (int(bound.timestamp()) for bound in (START, END))
        chunks = []

        with pd.read_csv(source, compression="gzip", chunksize=500_000, float_precision="round_trip") as reader:
            for chunk in reader:
                chunks.append(chunk.loc[chunk["timestamp"].between(lower, upper, inclusive="left")])

                if chunk["timestamp"].iloc[-1] >= upper:
                    break

    minutes = pd.concat(chunks, ignore_index=True)
    timestamps = minutes.pop("timestamp")

    if timestamps.isna().any() or timestamps.duplicated().any() or not timestamps.is_monotonic_increasing or (timestamps % 60 != 0).any():
        raise ValueError("Observed minute timestamps must be distinct, increasing UTC minute opens")

    minutes.insert(0, "datetime", pd.to_datetime(timestamps, unit="s", utc=True))
    minutes = ValidateOHLCV(minutes)
    hourly = minutes.groupby(minutes["datetime"].dt.floor("h")).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).reset_index()
    expected = pd.date_range(START, END, freq="h", inclusive="left")

    if not pd.DatetimeIndex(hourly["datetime"]).equals(expected):
        raise ValueError("Expected every declared hour to have at least one observed minute bar")

    return ValidateOHLCV(hourly), len(minutes)


def MeasureWindow(bars: pd.DataFrame) -> tuple[float, float]:
    """Calculate population log-close volatility and mean volume within one window."""

    close = bars["close"].to_numpy()

    if (close <= 0).any():
        raise ValueError("Holdout diagnostics require positive closes")

    returns = np.diff(np.log(close))

    return float(returns.std(ddof=0)), float(bars["volume"].mean())


def FreezeTraining(training: pd.DataFrame) -> tuple[GenerationConfig, dict, tuple[float, float], dict]:
    """Freeze the generation recipe, tolerances and fuzzy reference using training alone."""

    profile = ExtractProfile(training)
    volatility, activity = MeasureWindow(training)

    if volatility <= 0 or activity <= 0:
        raise ValueError("Training volatility and activity references must be positive")

    config = profile.ToConfig(GenerationConfig(model=profile.model,
        start=SPLIT.to_pydatetime(),
        horizon=int((END - SPLIT) / pd.Timedelta(hours=1)),
        initial_price=float(training["close"].iloc[-1]),
    ))
    tolerances = {
        "log_return_std": TOLERANCE_FRACTION * volatility,
        "volume_mean": TOLERANCE_FRACTION * activity,
    }

    return config, profile.ManifestMetadata(), (volatility, activity), tolerances


def AssessFuzzy(holdout: pd.DataFrame, reference: tuple[float, float]) -> dict:
    """Describe the installed scalar backend on disjoint complete UTC-day windows."""

    records = []

    for offset in range(0, len(holdout), HOURS_PER_WINDOW):
        window = holdout.iloc[offset:offset + HOURS_PER_WINDOW]

        if len(window) != HOURS_PER_WINDOW:
            raise ValueError("The fuzzy holdout requires complete, disjoint 24-hour windows")

        volatility, activity = MeasureWindow(window)
        report = DiagnoseRegime(volatility / reference[0], activity / reference[1])
        records.append({
            "start_utc": window["datetime"].iloc[0].isoformat(),
            "end_utc": window["datetime"].iloc[-1].isoformat(),
            **report.ToDict(),
        })

    scores = np.array([record["score"] for record in records])
    clipping = {
        name: sum(record[f"{name}_ratio"] > 2.0 for record in records)
        for name in ("volatility", "activity")
    }

    return {
        "training_reference": {"volatility": reference[0], "activity_btc": reference[1]},
        "hours_per_window": HOURS_PER_WINDOW,
        "windows": records,
        "observed_score_quantiles": np.quantile(scores, QUANTILES).tolist(),
        "clipping_counts": clipping,
        "decision": "descriptive only; no independent regime labels or acceptance threshold",
    }


def BuildEvidence(archive: Path) -> dict:
    """Keep every seeded holdout result, replay input and fuzzy window for independent review."""

    bars, minute_rows = ReadHourlyBars(archive)
    training = bars.loc[bars["datetime"] < SPLIT].reset_index(drop=True)
    holdout = bars.loc[bars["datetime"] >= SPLIT].reset_index(drop=True)
    base, profile, reference, tolerances = FreezeTraining(training)
    runs = []

    for seed in SEEDS:
        config = replace(base, seed=seed)
        synthetic = Generate(config)
        report = Compare(holdout, synthetic, tolerances=tolerances)
        runs.append({
            "manifest": CreateManifest(config, synthetic, metadata=profile),
            "metrics": [asdict(metric) for metric in report.metrics],
        })

    return {
        "recipe": "bitstamp-btcusd-hourly-holdout-v1",
        "recipe_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "environment": Environment(),
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "archive_minute_rows": minute_rows,
        "missing_archive_minute_slots": len(bars) * 60 - minute_rows,
        "training": {
            "start_utc": START.isoformat(), "end_utc_exclusive": SPLIT.isoformat(),
            "rows": len(training), "canonical_fingerprint": Fingerprint(training),
        },
        "holdout": {
            "start_utc": SPLIT.isoformat(), "end_utc_exclusive": END.isoformat(),
            "rows": len(holdout), "canonical_fingerprint": Fingerprint(holdout),
        },
        "tolerances": tolerances,
        "tolerance_method": "absolute gaps bounded by 25% of the corresponding training statistic",
        "runs": runs,
        "fuzzy": AssessFuzzy(holdout, reference),
        "quantile_levels": QUANTILES,
    }


def Main() -> None:
    """Write one machine-readable report to a new output file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = BuildEvidence(arguments.archive)

    with arguments.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    Main()
