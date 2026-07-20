from __future__ import annotations

from dataclasses import dataclass

from .conventions import DeltaConvention
from .cpp_engine import CppQuantitativeEngine
from .market import MarketSliceBuilder
from .pricer import VannaVolgaPricer


@dataclass(frozen=True)
class PricingApplication:
    engine: CppQuantitativeEngine
    builder: MarketSliceBuilder
    pricer: VannaVolgaPricer


def build_application(
    convention: DeltaConvention = DeltaConvention.SPOT_PREM_EXCLUDED,
) -> PricingApplication:
    engine = CppQuantitativeEngine(convention)
    return PricingApplication(
        engine=engine,
        builder=MarketSliceBuilder(engine),
        pricer=VannaVolgaPricer(engine),
    )
