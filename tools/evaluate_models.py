"""Generate auditable synthetic-only profile, holdout and scenario evidence."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pricegenerator.calibration import Calibrate
from pricegenerator.config import GenerationConfig
from pricegenerator.evaluation import BootstrapMeanInterval, Compare
from pricegenerator.extended_models import (
    Bootstrap, BootstrapConfig, CreateBootstrapManifest, CreateScriptedManifest,
    Scripted, ScriptedConfig, ScriptStep,
)
from pricegenerator.generation import Generate
from pricegenerator.registry import ListModels


def _ComparisonEvidence(report, full_analysis: bool) -> dict:
    """Keep reviewable selected diagnostics while allowing complete raw reports."""

    result = report.ToDict()

    if full_analysis:
        return result

    for name in ("reference_analysis", "synthetic_analysis"):
        analysis = result[name]
        selected = {key: analysis[key] for key in ("candle_count", "cadence_regular", "path", "maximum_drawdown",
                                                  "volume_range_correlation", "volume_absolute_return_correlation", "notes")}
        selected["distributions"] = []

        for distribution in analysis["distributions"]:
            if distribution["name"] not in ("log_returns", "body_fraction", "range", "volume"):
                continue

            summary = {key: distribution[key] for key in ("name", "count", "excluded", "mean", "standard_deviation",
                                                          "excess_kurtosis", "lower_tail_mean", "upper_tail_mean")}
            summary["quantiles"] = [item for item in distribution["quantiles"] if item[0] in (.01, .5, .99)]
            selected["distributions"].append(summary)

        selected["first_three_squared_return_acf"] = analysis["squared_return_acf"][:3]
        result[name] = selected

    result["analysis_scope"] = "Selected independent diagnostics; --full-analysis includes all distributions and observation vectors"

    return result


def BuildEvidence(*, full_analysis: bool = False) -> dict:
    """Run predefined metrics on purposeful fixtures with known held-out shifts."""

    reference_config = GenerationConfig(seed=812, horizon=192, regime_scale=1, shock_probability=0,
                                        wick_outlier_probability=0, volume_base=1000, volume_sigma=0,
                                        volume_return_coupling=0, volume_persistence=0)
    training = Generate(reference_config)
    holdout_config = replace(reference_config, seed=981, horizon=64, drift=.03, volume_base=4000,
                             start=training["datetime"].iloc[-1].to_pydatetime() + pd.Timedelta(hours=1),
                             initial_price=float(training["close"].iloc[-1]))
    holdout = Generate(holdout_config)
    tolerances = {"log_return_mean": .005, "log_return_std": .005, "volume_mean": 10}
    calibration = Calibrate(training, holdout, base=GenerationConfig(seed=74), tolerances=tolerances)
    bootstrap_config = BootstrapConfig(count=192, seed=20, block_length=8,
                                       initial_price=float(training["close"].iloc[0]))
    bootstrap = Bootstrap(training, bootstrap_config)
    scripted_config = ScriptedConfig(count=80, drift=.001, steps=(
        ScriptStep(20, log_jump=-.25, volume=5000),
        ScriptStep(40, drift=-.01), ScriptStep(60, drift=.005, volume=1000),
    ))
    scripted = Scripted(scripted_config)
    training_returns = np.log(training["close"].to_numpy() / training["open"].to_numpy())
    calibration_evidence = calibration.ToDict()
    calibration_evidence["training"] = _ComparisonEvidence(calibration.training, full_analysis)
    calibration_evidence["holdout"] = _ComparisonEvidence(calibration.holdout, full_analysis)

    return {
        "evidence_version": 1,
        "command": "python -m tools.evaluate_models --output docs/evidence/research-v2.json" + (" --full-analysis" if full_analysis else ""),
        "source": "Purposeful synthetic fixtures only; no historical market dataset or future observations",
        "predeclared_tolerances": tolerances,
        "fixture_configurations": {"training": reference_config.ToDict(), "holdout": holdout_config.ToDict()},
        "calibration": calibration_evidence,
        "training_body_log_return_mean_interval": BootstrapMeanInterval(training_returns, seed=42,
                                                                          resamples=2000, block_length=8).ToDict(),
        "bootstrap_manifest": CreateBootstrapManifest(training, bootstrap_config, bootstrap),
        "bootstrap_comparison": _ComparisonEvidence(Compare(training, bootstrap, tolerances=tolerances), full_analysis),
        "scripted_manifest": CreateScriptedManifest(scripted_config, scripted),
        "registry": [model.ToDict() for model in ListModels()],
        "historical_evidence": {
            "status": "archived characterization only; no legacy model was executed or admitted",
            "paths": ["docs/baseline/source-test-results.json", "docs/benchmarks/legacy-baseline-2026-10-15.json"],
            "comparison_limit": "Historical tests use a different schema and model; no statistical equivalence is asserted",
        },
        "interpretation": "The withheld drift/volume change is deliberately detectable; passing a listed tolerance validates only that fixture metric, not market realism, forecast quality or all parameters",
    }


def Main() -> None:
    """Write the reproducible report to an explicit caller-selected file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--full-analysis", action="store_true", help="Include every metric and raw observation vector")
    arguments = parser.parse_args()
    evidence = BuildEvidence(full_analysis=arguments.full_analysis)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    Main()
