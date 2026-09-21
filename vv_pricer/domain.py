from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from .conventions import AtmConvention, DeltaConvention


def _finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")


@dataclass(frozen=True)
class SmileQuote:
    T: float
    sigma_atm: float
    rr25: float
    bf25: float

    def __post_init__(self) -> None:
        _finite("T", self.T)
        _finite("sigma_atm", self.sigma_atm)
        _finite("rr25", self.rr25)
        _finite("bf25", self.bf25)
        if self.T <= 0.0:
            raise ValueError("T must be strictly positive.")
        if self.sigma_atm <= 0.0:
            raise ValueError("sigma_atm must be strictly positive.")


@dataclass(frozen=True)
class TenorMarketQuote:
    """One FX smile and its domestic/foreign continuously compounded rates."""

    quote: SmileQuote
    domestic_rate: float
    foreign_rate: float

    def __post_init__(self) -> None:
        if not isinstance(self.quote, SmileQuote):
            raise TypeError("quote must be a SmileQuote.")
        _finite("domestic_rate", self.domestic_rate)
        _finite("foreign_rate", self.foreign_rate)

    @property
    def maturity(self) -> float:
        return self.quote.T


@dataclass(frozen=True)
class FxMarketTermStructure:
    """Immutable FX ATM/RR/BF market inputs ordered by increasing maturity."""

    spot: float
    delta_convention: DeltaConvention
    atm_convention: AtmConvention
    tenors: tuple[TenorMarketQuote, ...]

    def __post_init__(self) -> None:
        _finite("spot", self.spot)
        if self.spot <= 0.0:
            raise ValueError("spot must be strictly positive.")
        if not isinstance(self.delta_convention, DeltaConvention):
            raise TypeError("delta_convention must be a DeltaConvention.")
        if not isinstance(self.atm_convention, AtmConvention):
            raise TypeError("atm_convention must be an AtmConvention.")

        try:
            supplied_tenors = tuple(self.tenors)
        except TypeError as exc:
            raise TypeError("tenors must be an iterable of TenorMarketQuote objects.") from exc
        if not supplied_tenors:
            raise ValueError("tenors must contain at least one maturity.")
        if any(not isinstance(tenor, TenorMarketQuote) for tenor in supplied_tenors):
            raise TypeError("tenors must contain only TenorMarketQuote objects.")

        ordered_tenors = tuple(
            sorted(supplied_tenors, key=lambda tenor: tenor.maturity)
        )

        maturities = tuple(tenor.maturity for tenor in ordered_tenors)
        if len(set(maturities)) != len(maturities):
            raise ValueError("tenors must have unique maturities.")
        object.__setattr__(self, "tenors", ordered_tenors)

    @classmethod
    def from_tenors(
        cls,
        spot: float,
        delta_convention: DeltaConvention,
        atm_convention: AtmConvention,
        tenors: Iterable[TenorMarketQuote],
    ) -> "FxMarketTermStructure":
        return cls(
            spot=spot,
            delta_convention=delta_convention,
            atm_convention=atm_convention,
            tenors=tuple(tenors),
        )
