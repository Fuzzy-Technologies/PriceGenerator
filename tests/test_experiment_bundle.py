"""Exercise bundle generation and fail-closed integrity checks."""

import hashlib
import json

import pytest

from tools import experiment_bundle


def test_CreateBundleWritesPortableReplayEvidence(tmp_path):
    """Generate real artifacts and bind both synthetic inputs to the comparison."""

    directory = tmp_path / "experiment"
    experiment_bundle.CreateBundle(directory)
    experiment_bundle.VerifyBundle(directory)
    assert {path.name for path in directory.iterdir()} == {
        "SHA256SUMS", "comparison.json", "ensemble-manifest.json", "ensemble.json", "quantiles.html",
        "reference-manifest.json", "reference.csv", "scenario-manifest.json", "scenario.csv",
    }, "A complete bundle must contain exactly the documented files"

    comparison = json.loads((directory / "comparison.json").read_bytes())
    metrics = comparison["comparison"]

    for role, seed in (("reference", 43), ("synthetic", 42)):
        source = comparison["inputs"][role]
        manifest = json.loads((directory / source["manifest"]).read_bytes())
        assert source["origin"] == manifest["metadata"]["origin"] == "synthetic", "Both inputs are synthetic fixtures"
        assert manifest["seed"] == seed, "Fixture provenance must identify the independent seeds"
        assert metrics[f"{role}_rows"] == 120, "The comparison must cover each complete fixture"
        assert metrics[f"{role}_fingerprint"] == manifest["fingerprint"], "The comparison must identify the recorded OHLCV"

    assert all(item["within_tolerance"] is None for item in metrics["metrics"]), "Example metrics must be descriptive"
    ensemble = json.loads((directory / "ensemble.json").read_bytes())
    assert ensemble["path_count"] == 32, "The report must preserve the ensemble size"
    chart = (directory / "quantiles.html").read_text(encoding="utf-8")
    assert all(f"P{level} close" in chart for level in ("05", "50", "95")), "The chart must carry all three close quantiles"

    checksums = (directory / "SHA256SUMS").read_text(encoding="ascii")
    assert hashlib.sha256((directory / "scenario.csv").read_bytes()).hexdigest() + "  scenario.csv\n" in checksums
    (directory / "scenario.csv").write_bytes(b"changed")

    with pytest.raises(ValueError, match="do not match SHA256SUMS"):
        experiment_bundle.VerifyBundle(directory)


def test_CreateBundleRefusesExistingDestination(tmp_path):
    """Reject an existing directory before writing into it."""

    sentinel = tmp_path / "scenario.csv"
    sentinel.write_bytes(b"keep me")

    with pytest.raises(FileExistsError):
        experiment_bundle.CreateBundle(tmp_path)

    assert list(tmp_path.iterdir()) == [sentinel], "Existing destinations must remain untouched"
    assert sentinel.read_bytes() == b"keep me", "The bundle must never replace prior outputs"


def test_InterruptedBundleRemainsIncomplete(tmp_path, monkeypatch):
    """A partial write must leave a directory that verification rejects."""

    def Interrupt(directory, stem, config):
        """Simulate an I/O failure after an output appears."""

        (directory / f"{stem}.csv").write_bytes(b"partial")
        raise OSError("simulated write failure")

    directory = tmp_path / "interrupted"
    monkeypatch.setattr(experiment_bundle, "_WriteFixture", Interrupt)

    with pytest.raises(OSError, match="simulated write failure"):
        experiment_bundle.CreateBundle(directory)

    assert (directory / "scenario.csv").is_file(), "The fixture must exercise a genuine partial result"
    assert not (directory / "SHA256SUMS").exists(), "A partial result must lack the completion marker"

    with pytest.raises(ValueError, match="Incomplete bundle"):
        experiment_bundle.VerifyBundle(directory)
