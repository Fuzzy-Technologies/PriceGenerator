"""Implement the fixed random-consumption contract of the regime_v2 model."""

import math
from random import Random
from typing import Iterator

from pricegenerator.config import GenerationConfig


MODEL_ID = "regime_v2"
RNG_ID = "python.random.Random/MT19937"


def _Reflect(value: float, lower: float, upper: float) -> float:
    """Reflect an arbitrary log-price proposal within two finite boundaries."""

    if lower <= value <= upper:
        return value

    width = upper - lower
    position = (value - lower) % (2 * width)

    return lower + (position if position <= width else 2 * width - position)


def GenerateRows(config: GenerationConfig, rng: Random) -> Iterator[tuple[float, float, float, float, float]]:
    """Yield OHLCV with continuous opens and independently sampled bounded wicks.

    Each candle consumes a regime uniform, Gaussian return, shock uniform and
    Gaussian shock (even when inactive), then independent upper/lower wick
    uniforms and Gaussian wicks, and Gaussian volume
    innovation, in that order. Changing consumption requires a new model ID.
    Activity uses the realized reflected return, normalized by current regime
    volatility and capped at ten, so extreme proposals cannot overflow volume.
    """

    lower, upper = math.log(config.price_floor), math.log(config.price_ceiling)
    log_close = math.log(config.initial_price)
    previous_close = config.initial_price
    stressed = False
    log_volume_noise = 0.0
    volume_innovation = config.volume_sigma * math.sqrt(1 - config.volume_persistence ** 2)
    log_volume_base, log_volume_ceiling = math.log(config.volume_base), math.log(config.volume_ceiling)

    for _ in range(config.horizon):
        if rng.random() >= config.regime_persistence:
            stressed = not stressed

        sigma = config.volatility * (config.regime_scale if stressed else 1)
        innovation = rng.gauss(0, 1)
        shock_active = rng.random() < config.shock_probability
        shock = rng.gauss(0, 1)
        proposed_return = config.drift + sigma * innovation + config.volatility * config.shock_scale * shock * shock_active
        log_open = log_close
        log_close = _Reflect(log_open + proposed_return, lower, upper)
        upper_outlier = rng.random() < config.wick_outlier_probability
        upper_wick = abs(rng.gauss(0, 1)) * sigma * config.wick_scale * (config.wick_outlier_scale if upper_outlier else 1)
        lower_outlier = rng.random() < config.wick_outlier_probability
        lower_wick = abs(rng.gauss(0, 1)) * sigma * config.wick_scale * (config.wick_outlier_scale if lower_outlier else 1)
        log_volume_noise = config.volume_persistence * log_volume_noise + volume_innovation * rng.gauss(0, 1)
        activity = min(abs(log_close - log_open) / sigma, 10.0) if sigma else 0.0
        volume_log = log_volume_base + log_volume_noise + config.volume_return_coupling * activity
        open_price = previous_close
        close_price = open_price if log_close == log_open else min(config.price_ceiling, max(config.price_floor, math.exp(log_close)))
        high = max(open_price, close_price) if upper_wick == 0 else min(config.price_ceiling, max(open_price, close_price, math.exp(min(upper, max(log_open, log_close) + upper_wick))))
        low = min(open_price, close_price) if lower_wick == 0 else max(config.price_floor, min(open_price, close_price, math.exp(max(lower, min(log_open, log_close) - lower_wick))))
        volume = min(config.volume_ceiling, math.exp(max(-700.0, min(log_volume_ceiling, volume_log))))
        previous_close = close_price

        yield open_price, high, low, close_price, volume
