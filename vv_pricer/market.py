from __future__ import annotations

from typing import Any

from .cpp_engine import CppQuantitativeEngine
from .domain import SmileQuote


class MarketSliceBuilder:
    def __init__(self, engine: CppQuantitativeEngine) -> None:
        self.engine = engine

    def build(
        self,
        spot: float,
        domestic_rate: float,
        foreign_rate: float,
        quote: SmileQuote,
    ) -> Any:
        return self.engine.build_slice(
            spot,
            domestic_rate,
            foreign_rate,
            quote,
        )
