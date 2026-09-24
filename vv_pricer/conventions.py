from __future__ import annotations

from enum import Enum
from typing import Any


class DeltaConvention(Enum):
    SPOT_PREM_EXCLUDED = "SPOT_PREM_EXCLUDED"
    FWD_PREM_EXCLUDED = "FWD_PREM_EXCLUDED"
    SPOT_PREM_INCLUDED = "SPOT_PREM_INCLUDED"

    @classmethod
    def parse(cls, raw: str | None) -> "DeltaConvention":
        if raw is None or not raw.strip():
            return cls.SPOT_PREM_EXCLUDED

        normalized = raw.strip().upper().replace("-", "_")
        aliases = {
            "SPOT_PREM_EXCL": cls.SPOT_PREM_EXCLUDED,
            "FWD_PREM_EXCL": cls.FWD_PREM_EXCLUDED,
            "SPOT_PREM_INCL": cls.SPOT_PREM_INCLUDED,
        }
        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls[normalized]
        except KeyError as exc:
            supported = ", ".join(item.name for item in cls)
            raise ValueError(
                f"Unknown delta convention '{raw}'. Supported: {supported}."
            ) from exc

    def to_cpp(self, cpp_module: Any) -> Any:
        return getattr(cpp_module.DeltaConvention, self.value)

    def __str__(self) -> str:
        return self.name


class AtmConvention(Enum):
    """ATM-strike conventions supported by the market-data contract.

    The current Vanna-Volga engine defines ATM at the forward. Further FX ATM
    conventions require matching strike construction in the pricing engine.
    """

    FORWARD = "FORWARD"

    def __str__(self) -> str:
        return self.name
