from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log
from typing import Any

from ..application import PricingApplication, build_application
from ..conventions import AtmConvention
from ..domain import FxMarketTermStructure, TenorMarketQuote
from .types import SmilePointProvenance, VvSmileSample, VvSmileSamplePoint


@dataclass(frozen=True, slots=True)
class _VvPillars:
    strikes: tuple[float, float, float]
    log_moneyness: tuple[float, float, float]
    volatilities: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class VvSmileSamplingConfig:
    """Deterministic grid configuration for the reliable VV region.

    The default extends each 25-delta pillar by half of its distance from ATM
    in forward log-moneyness. Each of the four resulting anchor intervals gets
    the requested number of synthetic interior observations.
    """

    synthetic_points_per_interval: int = 3
    wing_extension_fraction: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.synthetic_points_per_interval, bool) or not isinstance(
            self.synthetic_points_per_interval, int
        ):
            raise TypeError("synthetic_points_per_interval must be an integer.")
        if self.synthetic_points_per_interval < 0:
            raise ValueError(
                "synthetic_points_per_interval must be non-negative."
            )
        if not isfinite(self.wing_extension_fraction):
            raise ValueError("wing_extension_fraction must be finite.")
        if not 0.0 <= self.wing_extension_fraction <= 1.0:
            raise ValueError("wing_extension_fraction must be between 0 and 1.")


class VannaVolgaSmileSampler:
    """Reconstruct and sample every tenor in an FX market term structure."""

    def __init__(self, config: VvSmileSamplingConfig | None = None) -> None:
        self.config = config or VvSmileSamplingConfig()

    def sample(self, market: FxMarketTermStructure) -> tuple[VvSmileSample, ...]:
        """Return one strike-ordered VV sample for every market tenor."""
        if not isinstance(market, FxMarketTermStructure):
            raise TypeError("market must be an FxMarketTermStructure.")
        if market.atm_convention is not AtmConvention.FORWARD:
            raise ValueError("VV sampling currently requires forward ATM.")

        application = build_application(market.delta_convention)
        return tuple(
            self._sample_tenor(application, market.spot, tenor)
            for tenor in market.tenors
        )

    def _sample_tenor(
        self,
        application: PricingApplication,
        spot: float,
        tenor: TenorMarketQuote,
    ) -> VvSmileSample:
        market_slice = application.builder.build(
            spot,
            tenor.domestic_rate,
            tenor.foreign_rate,
            tenor.quote,
        )
        maturity = tenor.maturity
        forward = spot * exp(
            (tenor.domestic_rate - tenor.foreign_rate) * maturity
        )
        pillars = self._pillars(market_slice, forward)
        left_cutoff, right_cutoff = self._cutoffs(pillars.log_moneyness)
        grid = self._grid(
            (left_cutoff, *pillars.log_moneyness, right_cutoff)
        )
        pillar_by_log_moneyness = self._pillar_map(pillars)

        points = self._points(
            application,
            market_slice,
            maturity,
            forward,
            grid,
            pillar_by_log_moneyness,
        )
        return VvSmileSample(
            maturity=maturity,
            forward=forward,
            domestic_rate=tenor.domestic_rate,
            foreign_rate=tenor.foreign_rate,
            reliable_log_moneyness_min=left_cutoff,
            reliable_log_moneyness_max=right_cutoff,
            points=points,
        )

    def _points(
        self,
        application: PricingApplication,
        market_slice: Any,
        maturity: float,
        forward: float,
        grid: tuple[float, ...],
        pillars: dict[float, tuple[float, float, SmilePointProvenance]],
    ) -> tuple[VvSmileSamplePoint, ...]:
        return tuple(
            self._point(
                application,
                market_slice,
                maturity,
                forward,
                k,
                pillars.get(k),
            )
            for k in grid
        )

    @staticmethod
    def _pillars(market_slice: Any, forward: float) -> _VvPillars:
        strikes = (
            float(market_slice.strike_25p),
            float(market_slice.strike_atm),
            float(market_slice.strike_25c),
        )
        if not strikes[0] < strikes[1] < strikes[2]:
            raise ValueError("VV pillar strikes must be strictly increasing.")
        log_moneyness = (
            log(strikes[0] / forward),
            log(strikes[1] / forward),
            log(strikes[2] / forward),
        )
        if abs(log_moneyness[1]) > 1e-12:
            raise ValueError("forward-ATM strike does not match the tenor forward.")
        return _VvPillars(
            strikes=strikes,
            log_moneyness=log_moneyness,
            volatilities=(
                float(market_slice.sigma_25p),
                float(market_slice.sigma_atm),
                float(market_slice.sigma_25c),
            ),
        )

    def _cutoffs(
        self, log_moneyness: tuple[float, float, float]
    ) -> tuple[float, float]:
        put, atm, call = log_moneyness
        extension = self.config.wing_extension_fraction
        return (
            put - extension * (atm - put),
            call + extension * (call - atm),
        )

    @staticmethod
    def _pillar_map(
        pillars: _VvPillars,
    ) -> dict[float, tuple[float, float, SmilePointProvenance]]:
        provenances = (
            SmilePointProvenance.LIQUID_25P,
            SmilePointProvenance.LIQUID_ATM,
            SmilePointProvenance.LIQUID_25C,
        )
        return {
            k: (strike, volatility, provenance)
            for k, strike, volatility, provenance in zip(
                pillars.log_moneyness,
                pillars.strikes,
                pillars.volatilities,
                provenances,
                strict=True,
            )
        }

    def _grid(self, anchors: tuple[float, ...]) -> tuple[float, ...]:
        interior_count = self.config.synthetic_points_per_interval
        unique_anchors = tuple(dict.fromkeys(anchors))
        grid = [unique_anchors[0]]
        for left, right in zip(unique_anchors, unique_anchors[1:]):
            interval_count = interior_count + 1
            step = (right - left) / interval_count
            grid.extend(left + step * index for index in range(1, interval_count))
            grid.append(right)
        return tuple(grid)

    @staticmethod
    def _point(
        application: PricingApplication,
        market_slice: Any,
        maturity: float,
        forward: float,
        log_forward_moneyness: float,
        pillar: tuple[float, float, SmilePointProvenance] | None,
    ) -> VvSmileSamplePoint:
        if pillar is None:
            strike = forward * exp(log_forward_moneyness)
            is_call = strike >= forward
            price = application.pricer.price_vanilla(
                market_slice,
                is_call,
                strike,
            )
            implied_volatility = application.pricer.implied_volatility(
                market_slice,
                is_call,
                strike,
                price,
            )
            provenance = SmilePointProvenance.SYNTHETIC_VV
        else:
            strike, implied_volatility, provenance = pillar

        if not (isfinite(implied_volatility) and implied_volatility > 0.0):
            raise ValueError(
                "sampled VV implied volatility must be finite and positive."
            )
        return VvSmileSamplePoint(
            strike=strike,
            log_forward_moneyness=log_forward_moneyness,
            implied_volatility=implied_volatility,
            total_variance=implied_volatility**2 * maturity,
            provenance=provenance,
        )
