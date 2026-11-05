"""Verify optional backend boundaries and independent diagnostic oracles."""

from fractions import Fraction
from importlib.metadata import PackageNotFoundError
import json
from types import SimpleNamespace

import pytest

from pricegenerator import fuzzy_diagnostics
from pricegenerator.fuzzy_diagnostics import DiagnoseRegime


@pytest.fixture
def ScalarBackend():
    """Skip real inference only in environments without the optional engine."""

    pytest.importorskip("fuzzyroutines")


@pytest.mark.parametrize("invalid", (True, "1", None, -0.01, float("inf"), float("nan"), 10 ** 400))
@pytest.mark.parametrize("argument", ("volatility_ratio", "activity_ratio"))
def test_RejectInvalidRatioBeforeAccessingBackend(invalid, argument):
    """Reject malformed coordinates even in a core-only installation."""

    ratios = {"volatility_ratio": 1, "activity_ratio": 1}
    ratios[argument] = invalid

    with pytest.raises(ValueError, match=argument):
        DiagnoseRegime(**ratios)


def test_UnsupportedPythonRejectsBeforeResolvingDistribution(monkeypatch):
    """Report the optional interpreter boundary without importing FuzzyRoutines."""

    monkeypatch.setattr(fuzzy_diagnostics, "sys", SimpleNamespace(version_info=(3, 12)))

    def FailIfCalled(_):
        """Require the interpreter guard to precede dependency resolution."""

        pytest.fail("Unsupported Python attempted to resolve FuzzyRoutines")

    monkeypatch.setattr(fuzzy_diagnostics, "version", FailIfCalled)

    with pytest.raises(ImportError, match="require Python 3.13"):
        DiagnoseRegime(1, 1)


def test_MissingEngineProvidesInstallHint(monkeypatch):
    """Provide the install command when the optional distribution is absent."""

    monkeypatch.setattr(fuzzy_diagnostics, "sys", SimpleNamespace(version_info=(3, 13)))

    def Missing(distribution):
        """Simulate missing package metadata without stubbing inference."""

        raise PackageNotFoundError(distribution)

    monkeypatch.setattr(fuzzy_diagnostics, "version", Missing)

    with pytest.raises(ImportError, match=r"pricegenerator\[fuzzy\]"):
        DiagnoseRegime(1, 1)


def test_RejectUntestedEngineVersion(monkeypatch):
    """Prevent an untested backend from changing the diagnostic contract."""

    monkeypatch.setattr(fuzzy_diagnostics, "sys", SimpleNamespace(version_info=(3, 13)))
    monkeypatch.setattr(fuzzy_diagnostics, "version", lambda _: "2.0.0")

    with pytest.raises(ImportError, match=r"fuzzyroutines==2\.1\.0"):
        DiagnoseRegime(1, 1)


@pytest.mark.usefixtures("ScalarBackend")
@pytest.mark.parametrize(
    "ratios, expected_score, active_rule",
    (
        ((1, 1), 0.25, "both-ordinary"),
        ((0, 2), 0.5, "activity-elevated"),
        ((2, 0), 0.5, "volatility-elevated"),
        ((2, 2), 0.75, "both-elevated"),
    ),
)
def test_EndpointActivatesExactlyOneRule(ratios, expected_score, active_rule):
    """Use the symmetry of each full triangle as a centroid oracle."""

    report = DiagnoseRegime(*ratios)
    assert report.score == pytest.approx(expected_score, rel=0, abs=1e-12), "Single-rule centroid differs"
    assert [rule.name for rule in report.rules if rule.firing_strength == 1] == [active_rule], (
        "Endpoint activated the wrong rule"
    )
    assert sum(rule.firing_strength for rule in report.rules) == 1, "Inactive endpoint rules must remain at zero"


@pytest.mark.usefixtures("ScalarBackend")
def test_OverlappingOutputMatchesAnalyticalCentroidAndTrace():
    """Integrate the hand-derived upper envelope for the four active rules."""

    report = DiagnoseRegime(1.75, 1.75)

    # At y = 0, 1/16, 9/16, 11/16, 13/16, 1 the envelope heights are
    # 0, 1/4, 1/4, 3/4, 3/4, 0, with straight lines between knots.
    expected_area = Fraction(23, 64)
    expected_moment = Fraction(27, 128)
    assert report.score == pytest.approx(float(expected_moment / expected_area), rel=0, abs=1e-10), (
        "Mamdani centroid differs from the integrated max-min envelope"
    )
    assert tuple(term.grade for term in report.input_grades) == (0.25, 0.75, 0.25, 0.75), (
        "The trace lost the complementary memberships"
    )
    assert tuple(rule.firing_strength for rule in report.rules) == (0.25, 0.25, 0.25, 0.75), (
        "The trace lost min conjunction, multiplicative weights or rule ordering"
    )
    assert tuple(rule.consequent for rule in report.rules) == ("calm", "watch", "watch", "stress"), (
        "The trace must identify each rule's configured consequent"
    )


@pytest.mark.usefixtures("ScalarBackend")
def test_SaturationKeepsInputProvenanceAndResultsRepeatExactly():
    """Keep original ratios, evaluated coordinates and engine identity together."""

    report = DiagnoseRegime(5, 8)
    assert report.score == DiagnoseRegime(2, 2).score, "Saturation must evaluate exactly at the declared bound"
    assert report.volatility_ratio == 5 and report.activity_ratio == 8, "Saturation discarded observed inputs"
    assert all(grade.coordinate == 2 for grade in report.input_grades), "The trace must show saturated coordinates"
    assert report == DiagnoseRegime(5, 8), "Repeated scalar diagnostics must return equal reports"
    encoded = json.loads(json.dumps(report.ToDict(), allow_nan=False))
    assert encoded["profile_id"] == "relative-market-stress-v1", "Serialized evidence lost its profile identity"
    assert encoded["fuzzyroutines_version"] == "2.1.0", "Serialized evidence lost its exact engine version"
    assert encoded["method"] == "adaptive-simpson", "Composed centroid must identify the numerical method"
