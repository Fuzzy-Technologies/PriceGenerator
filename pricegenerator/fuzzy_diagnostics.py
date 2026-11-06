"""Evaluate experimental relative-market diagnostics with optional scalar inference."""

from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
import math
from numbers import Real
import sys


PROFILE_ID = "relative-market-stress-v1"
FUZZYROUTINES_VERSION = "2.1.0"
_RATIO_MAXIMUM = 2.0
_RULES = (
    ("both-ordinary", "ordinary", "ordinary", "calm"),
    ("activity-elevated", "ordinary", "elevated", "watch"),
    ("volatility-elevated", "elevated", "ordinary", "watch"),
    ("both-elevated", "elevated", "elevated", "stress"),
)


@dataclass(frozen=True)
class RegimeTermGrade:
    """Record an input term, its evaluated coordinate and its membership degree."""

    variable: str
    term: str
    coordinate: float
    grade: float


@dataclass(frozen=True)
class RegimeRuleFiring:
    """Record one rule and its scalar activation in declaration order."""

    name: str
    consequent: str
    antecedent_grade: float
    weight: float
    firing_strength: float


@dataclass(frozen=True)
class RegimeDiagnostic:
    """Retain a descriptive score, its input evidence and the evaluated rules."""

    profile_id: str
    fuzzyroutines_version: str
    method: str
    volatility_ratio: float
    activity_ratio: float
    score: float
    input_grades: tuple[RegimeTermGrade, ...]
    rules: tuple[RegimeRuleFiring, ...]

    def ToDict(self) -> dict:
        """Return a detached, JSON-compatible view of the diagnostic."""

        return asdict(self)


def _ValidateRatio(value: float, name: str) -> float:
    """Require a finite nonnegative binary64 scalar."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite nonnegative real scalar")

    try:
        ratio = float(value)

    except OverflowError as error:
        raise ValueError(f"{name} must be a finite nonnegative real scalar") from error

    if not math.isfinite(ratio) or ratio < 0:
        raise ValueError(f"{name} must be a finite nonnegative real scalar")

    return ratio


def _BackendVersion() -> str:
    """Require the supported interpreter and the exact tested inference engine."""

    if sys.version_info < (3, 13):
        raise ImportError("Fuzzy diagnostics require Python 3.13 or later")

    try:
        installed = version("fuzzyroutines")

    except PackageNotFoundError as error:
        raise ImportError("Install the pricegenerator[fuzzy] extra to use fuzzy diagnostics") from error

    if installed != FUZZYROUTINES_VERSION:
        raise ImportError(
            f"Fuzzy diagnostics require fuzzyroutines=={FUZZYROUTINES_VERSION}, found {installed}"
        )

    return installed


def DiagnoseRegime(volatility_ratio: float, activity_ratio: float) -> RegimeDiagnostic:
    """Describe already-observed conditions with a versioned max-min Mamdani profile.

    Ratios use positive, caller-declared baselines. Coordinates above 2
    saturate at 2 while the diagnostic retains the original observations.
    The centroid is a descriptive index on the unit interval.
    """

    volatility_ratio = _ValidateRatio(volatility_ratio, "volatility_ratio")
    activity_ratio = _ValidateRatio(activity_ratio, "activity_ratio")
    installed = _BackendVersion()

    from fuzzyroutines import (
        ContinuousUniverse,
        IntegrationDomain,
        LinguisticTerm,
        NegationPolicy,
        ScalarFuzzySet,
        SNormPolicy,
        TNormPolicy,
        Trapezoid,
        Triangle,
    )
    from fuzzyroutines.inference import AllOf, FuzzyVariable, InferencePolicy, MamdaniModel, MamdaniRule, TermCondition

    ratio_domain = ContinuousUniverse(0, _RATIO_MAXIMUM, True, True)
    output_domain = ContinuousUniverse(0, 1, True, True)
    input_terms = (
        LinguisticTerm("ordinary", ScalarFuzzySet(ratio_domain, Trapezoid(-1, 0, 1, 2))),
        LinguisticTerm("elevated", ScalarFuzzySet(ratio_domain, Trapezoid(1, 2, 3, 4))),
    )
    output_terms = (
        LinguisticTerm("calm", ScalarFuzzySet(output_domain, Triangle(0, 0.25, 0.5))),
        LinguisticTerm("watch", ScalarFuzzySet(output_domain, Triangle(0.25, 0.5, 0.75))),
        LinguisticTerm("stress", ScalarFuzzySet(output_domain, Triangle(0.5, 0.75, 1))),
    )
    inputs = (FuzzyVariable("volatility", input_terms), FuzzyVariable("activity", input_terms))
    rules = tuple(
        MamdaniRule(name, AllOf((TermCondition("volatility", vol), TermCondition("activity", act))), consequent)
        for name, vol, act, consequent in _RULES
    )
    minimum, maximum = TNormPolicy("logic"), SNormPolicy("logic")
    policy = InferencePolicy(minimum, maximum, NegationPolicy("standard"))
    model = MamdaniModel(inputs, FuzzyVariable("stress_index", output_terms), rules, policy, minimum, maximum)
    result = model.Evaluate(
        {
            "volatility": min(volatility_ratio, _RATIO_MAXIMUM),
            "activity": min(activity_ratio, _RATIO_MAXIMUM),
        },
        IntegrationDomain(0, 1),
    )

    if result.value is None:
        raise RuntimeError("The diagnostic did not return the requested centroid")

    return RegimeDiagnostic(
        PROFILE_ID, installed, result.method, volatility_ratio, activity_ratio, float(result.value),
        tuple(
            RegimeTermGrade(grade.variable, grade.term, float(grade.coordinate), float(grade.grade))
            for grade in result.inputGrades
        ),
        tuple(
            RegimeRuleFiring(trace.name, rule.consequent, float(trace.antecedentGrade),
                             float(trace.weight), float(trace.firingStrength))
            for rule, trace in zip(rules, result.rules, strict=True)
        ),
    )
