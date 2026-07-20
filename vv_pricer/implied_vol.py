from __future__ import annotations

from typing import Any

from .pricer import VannaVolgaPricer


def implied_vol_from_price(
    pricer: VannaVolgaPricer,
    market_slice: Any,
    target_price: float,
    is_call: bool,
    k: float,
    vol_low: float = 0.0,
    vol_high: float = 0.0,
) -> float:
    return pricer.implied_volatility(
        market_slice,
        is_call,
        k,
        target_price,
        vol_low,
        vol_high,
    )
