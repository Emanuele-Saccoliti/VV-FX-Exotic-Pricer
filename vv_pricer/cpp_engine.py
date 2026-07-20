from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .conventions import DeltaConvention
from .domain import SmileQuote

try:
    import vv_cpp as _cpp
except ImportError as exc:
    raise ImportError(
        "The mandatory vv_cpp extension is not installed. From the Hybrid "
        "directory run: python -m pip install -e ."
    ) from exc

import numpy as np


class CppQuantitativeEngine:
    """Python facade over the mandatory ``vv_cpp`` quantitative engine."""

    def __init__(
        self,
        convention: DeltaConvention,
    ) -> None:
        self.convention = convention
        self._engine = _cpp.VannaVolgaEngine(convention.to_cpp(_cpp))

    @property
    def backend_version(self) -> str:
        return str(_cpp.__version__)

    def build_slice(
        self,
        spot: float,
        domestic_rate: float,
        foreign_rate: float,
        quote: SmileQuote,
    ) -> Any:
        cpp_quote = _cpp.SmileQuote(
            quote.T,
            quote.sigma_atm,
            quote.rr25,
            quote.bf25,
        )
        return self._engine.build_slice(
            spot,
            domestic_rate,
            foreign_rate,
            cpp_quote,
        )

    @staticmethod
    def option_type(is_call: bool) -> Any:
        return _cpp.OptionType.CALL if is_call else _cpp.OptionType.PUT

    def greeks(self, market_slice: Any, strike: float, volatility: float) -> Any:
        return self._engine.greeks(market_slice, strike, volatility)

    @staticmethod
    def analytic_greeks(
        spot: float,
        strike: float,
        maturity: float,
        domestic_rate: float,
        foreign_rate: float,
        volatility: float,
    ) -> Any:
        return _cpp.analytic_greeks(
            spot,
            strike,
            maturity,
            domestic_rate,
            foreign_rate,
            volatility,
        )

    @staticmethod
    def finite_difference_greeks(
        spot: float,
        strike: float,
        maturity: float,
        domestic_rate: float,
        foreign_rate: float,
        volatility: float,
    ) -> Any:
        return _cpp.finite_difference_greeks(
            spot,
            strike,
            maturity,
            domestic_rate,
            foreign_rate,
            volatility,
        )

    def greeks_batch(
        self,
        market_slice: Any,
        strikes: Sequence[float] | np.ndarray,
        volatility: float,
    ) -> np.ndarray:
        strike_array = np.ascontiguousarray(strikes, dtype=np.float64)
        return self._engine.greeks_batch(market_slice, strike_array, volatility)

    def weights(self, market_slice: Any, strike: float) -> Any:
        return self._engine.weights(market_slice, strike)

    def price_vanilla(
        self,
        market_slice: Any,
        is_call: bool,
        strike: float,
    ) -> float:
        return float(
            self._engine.price_vanilla(
                market_slice,
                self.option_type(is_call),
                strike,
            )
        )

    def price_vanilla_batch(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> np.ndarray:
        strike_array = np.ascontiguousarray(strikes, dtype=np.float64)
        return self._engine.price_vanilla_batch(
            market_slice,
            self.option_type(is_call),
            strike_array,
        )

    def price_digital(
        self,
        market_slice: Any,
        is_call: bool,
        strike: float,
    ) -> float:
        return float(
            self._engine.price_digital(
                market_slice,
                self.option_type(is_call),
                strike,
            )
        )

    def check_arbitrage(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> Any:
        strike_array = np.ascontiguousarray(strikes, dtype=np.float64)
        return self._engine.check_arbitrage(
            market_slice,
            self.option_type(is_call),
            strike_array,
        )

    def check_digital_bounds(
        self,
        market_slice: Any,
        is_call: bool,
        strikes: Sequence[float] | np.ndarray,
    ) -> Any:
        strike_array = np.ascontiguousarray(strikes, dtype=np.float64)
        return self._engine.check_digital_bounds(
            market_slice,
            self.option_type(is_call),
            strike_array,
        )

    def check_put_call_parity(
        self,
        market_slice: Any,
        strike: float,
    ) -> Any:
        return self._engine.check_put_call_parity(market_slice, strike)

    def check_digital_parity(
        self,
        market_slice: Any,
        strike: float,
    ) -> Any:
        return self._engine.check_digital_parity(market_slice, strike)

    def implied_volatility(
        self,
        market_slice: Any,
        is_call: bool,
        strike: float,
        target_price: float,
        vol_low: float = 0.0,
        vol_high: float = 0.0,
    ) -> float:
        return float(
            self._engine.implied_volatility(
                market_slice,
                self.option_type(is_call),
                strike,
                target_price,
                vol_low,
                vol_high,
            )
        )

    @staticmethod
    def gk_price(
        is_call: bool,
        spot: float,
        strike: float,
        maturity: float,
        domestic_rate: float,
        foreign_rate: float,
        volatility: float,
    ) -> float:
        return float(
            _cpp.gk_price(
                CppQuantitativeEngine.option_type(is_call),
                spot,
                strike,
                maturity,
                domestic_rate,
                foreign_rate,
                volatility,
            )
        )
