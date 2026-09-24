from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SmilePointProvenance(str, Enum):
    """Origin of a point in a sampled Vanna-Volga smile."""

    LIQUID_25P = "liquid_25p"
    LIQUID_ATM = "liquid_atm"
    LIQUID_25C = "liquid_25c"
    SYNTHETIC_VV = "synthetic_vv"

    @property
    def is_liquid_pillar(self) -> bool:
        return self is not SmilePointProvenance.SYNTHETIC_VV


@dataclass(frozen=True, slots=True)
class VvSmileSamplePoint:
    """One sampled VV observation in forward-moneyness coordinates."""

    strike: float
    log_forward_moneyness: float
    implied_volatility: float
    total_variance: float
    provenance: SmilePointProvenance


@dataclass(frozen=True, slots=True)
class VvSmileSample:
    """A complete sampled VV smile for one maturity.

    The reliable-region cutoffs are recorded in forward log-moneyness. Points
    are ordered by increasing strike and include the three liquid pillars.
    """

    maturity: float
    forward: float
    domestic_rate: float
    foreign_rate: float
    reliable_log_moneyness_min: float
    reliable_log_moneyness_max: float
    points: tuple[VvSmileSamplePoint, ...]

    @property
    def strikes(self) -> tuple[float, ...]:
        return tuple(point.strike for point in self.points)

    @property
    def implied_volatilities(self) -> tuple[float, ...]:
        return tuple(point.implied_volatility for point in self.points)

    @property
    def total_variances(self) -> tuple[float, ...]:
        return tuple(point.total_variance for point in self.points)

    @property
    def provenances(self) -> tuple[SmilePointProvenance, ...]:
        return tuple(point.provenance for point in self.points)

    @property
    def liquid_pillars(self) -> tuple[VvSmileSamplePoint, ...]:
        return tuple(
            point for point in self.points if point.provenance.is_liquid_pillar
        )

    @property
    def synthetic_points(self) -> tuple[VvSmileSamplePoint, ...]:
        return tuple(
            point
            for point in self.points
            if point.provenance is SmilePointProvenance.SYNTHETIC_VV
        )
