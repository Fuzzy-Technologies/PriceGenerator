"""Characterize published 1.x behavior; this is not the future RNG API."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import random
import sys
from unittest.mock import patch


FIXTURE_PATH = Path(__file__).with_name("legacy_cases.json")
OHLCV_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


@contextmanager
def LegacyRuntime(seed):
    """Isolate the legacy global RNG, local timezone and logging side effects."""

    random_state = random.getstate()
    stderr = sys.stderr

    try:
        module = importlib.import_module("pricegenerator.PriceGenerator")

    finally:
        sys.stderr = stderr

    logger_level = module.uLogger.level
    module.uLogger.setLevel(50)

    try:
        # The old implementation forces tzlocal() in date_range, even for UTC inputs.
        with patch.object(module, "tzlocal", return_value=timezone.utc):
            random.seed(seed)
            yield module

    finally:
        random.setstate(random_state)
        module.uLogger.setLevel(logger_level)
        sys.stderr = stderr


def LoadCases():
    """Read immutable input configurations and independently captured golden rows."""

    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


def ConfigureLegacy(module, configuration):
    """Set every generation input explicitly after preserving constructor RNG draws."""

    configuration = deepcopy(configuration)
    model = module.PriceGenerator()
    model.dfHeaders = OHLCV_COLUMNS.copy()
    model.timeStart = datetime.fromisoformat(configuration.pop("timeStart"))
    model.timeframe = timedelta(seconds=configuration.pop("timeframeSeconds"))

    for attribute, value in configuration.items():
        setattr(model, attribute, value)

    return model


def GenerateLegacy(configuration, seed):
    """Run the real 1.x generator with replayable inputs and restored global state."""

    with LegacyRuntime(seed) as module:
        model = ConfigureLegacy(module, configuration)
        model.Generate()

    return model


def SerializePrices(prices, precision):
    """Use explicit decimal precision and ISO timestamps for portable golden rows."""

    rows = []

    for row in prices[OHLCV_COLUMNS].itertuples(index=False, name=None):
        rows.append([
            row[0].isoformat(),
            *[format(float(value), f".{precision}f") for value in row[1:5]],
            int(row[5]),
        ])

    return rows


def Fingerprint(rows):
    """Hash the documented canonical row representation rather than pandas internals."""

    serialized = json.dumps(rows, ensure_ascii=True, separators=(",", ":"))

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
