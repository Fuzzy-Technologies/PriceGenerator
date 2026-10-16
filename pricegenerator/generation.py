"""Generate canonical market data using private random state and explicit inputs."""

from random import Random

import pandas as pd

from pricegenerator.config import GenerationConfig
from pricegenerator.models import GenerateRows


OHLCV_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def Generate(config: GenerationConfig) -> pd.DataFrame:
    """Return validated canonical OHLCV without consuming global random state."""

    from pricegenerator.market_data import TimestampRange, ValidateOHLCV

    if not isinstance(config, GenerationConfig):
        raise TypeError("Generate requires a GenerationConfig")

    prices = pd.DataFrame(GenerateRows(config, Random(config.seed)), columns=OHLCV_COLUMNS[1:], dtype="float64")
    timestamps = TimestampRange(config.start, config.horizon, config.timeframe_seconds)
    prices.insert(0, "datetime", timestamps)

    return ValidateOHLCV(prices, timeframe_seconds=config.timeframe_seconds, allow_gaps=False)
