from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .cpp_engine import CppQuantitativeEngine


class VannaVolgaPricer:
    def __init__(self, engine: CppQuantitativeEngine) -> None:
        self.engine = engine

    def price_vanilla(self, market_slice: Any, is_call: bool, k: float) -> float:
        return self.engine.price_vanilla(market_slice, is_call, k)

    def price_vanilla_batch(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> np.ndarray:
        return self.engine.price_vanilla_batch(market_slice, is_call, strikes)

    def price_digital_call(self, market_slice: Any, k: float) -> float:
        return self.engine.price_digital(market_slice, True, k)

    def price_digital_put(self, market_slice: Any, k: float) -> float:
        return self.engine.price_digital(market_slice, False, k)

    def check_arbitrage(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> Any:
        return self.engine.check_arbitrage(market_slice, is_call, strikes)

    def check_digital_bounds(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> Any:
        return self.engine.check_digital_bounds(market_slice, is_call, strikes)

    def check_put_call_parity(self, market_slice: Any, k: float) -> Any:
        return self.engine.check_put_call_parity(market_slice, k)

    def check_digital_parity(self, market_slice: Any, k: float) -> Any:
        return self.engine.check_digital_parity(market_slice, k)

    def greeks(self, market_slice: Any, k: float, sigma: float) -> Any:
        return self.engine.greeks(market_slice, k, sigma)

    def greeks_batch(
        self,
        market_slice: Any,
        strikes: Sequence[float] | np.ndarray,
        sigma: float,
    ) -> np.ndarray:
        return self.engine.greeks_batch(market_slice, strikes, sigma)

    def weights(self, market_slice: Any, k: float) -> Any:
        return self.engine.weights(market_slice, k)

    def weights_atm_rr_bf(
        self,
        market_slice: Any,
        k: float,
    ) -> tuple[float, float, float]:
        values = self.weights(market_slice, k).atm_rr_bf
        return (float(values[0]), float(values[1]), float(values[2]))

    def weights_pillars(
        self,
        market_slice: Any,
        k: float,
    ) -> tuple[float, float, float]:
        values = self.weights(market_slice, k).pillars
        return (float(values[0]), float(values[1]), float(values[2]))

    def implied_volatility(
        self,
        market_slice: Any,
        is_call: bool,
        k: float,
        target_price: float,
        vol_low: float = 0.0,
        vol_high: float = 0.0,
    ) -> float:
        return self.engine.implied_volatility(
            market_slice,
            is_call,
            k,
            target_price,
            vol_low,
            vol_high,
        )
