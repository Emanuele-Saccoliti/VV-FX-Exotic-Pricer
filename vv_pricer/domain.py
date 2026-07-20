from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmileQuote:
    T: float
    sigma_atm: float
    rr25: float
    bf25: float
