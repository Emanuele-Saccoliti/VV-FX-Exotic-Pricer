from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vv_pricer import (
    AtmConvention,
    DeltaConvention,
    FxMarketTermStructure,
    SmileQuote,
    TenorMarketQuote,
)


def tenor(
    maturity: float,
    domestic_rate: float = 0.03,
    foreign_rate: float = 0.02,
) -> TenorMarketQuote:
    return TenorMarketQuote(
        quote=SmileQuote(T=maturity, sigma_atm=0.10, rr25=-0.02, bf25=0.01),
        domestic_rate=domestic_rate,
        foreign_rate=foreign_rate,
    )


def test_term_structure_sorts_maturities_and_retains_tenor_inputs() -> None:
    structure = FxMarketTermStructure.from_tenors(
        spot=1.085,
        delta_convention=DeltaConvention.FWD_PREM_EXCLUDED,
        atm_convention=AtmConvention.FORWARD,
        tenors=(tenor(1.0, 0.035, 0.021), tenor(0.25, 0.030, 0.020)),
    )

    assert tuple(item.maturity for item in structure.tenors) == (0.25, 1.0)
    assert structure.delta_convention is DeltaConvention.FWD_PREM_EXCLUDED
    assert structure.atm_convention is AtmConvention.FORWARD
    assert structure.tenors[1].domestic_rate == pytest.approx(0.035)
    assert structure.tenors[1].foreign_rate == pytest.approx(0.021)


def test_market_contracts_are_immutable() -> None:
    market = FxMarketTermStructure.from_tenors(
        spot=1.085,
        delta_convention=DeltaConvention.SPOT_PREM_EXCLUDED,
        atm_convention=AtmConvention.FORWARD,
        tenors=(tenor(0.5),),
    )

    with pytest.raises(FrozenInstanceError):
        market.spot = 1.10  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        market.tenors[0].domestic_rate = 0.04  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"spot": 0.0}, "spot must be strictly positive"),
        ({"spot": float("nan")}, "spot must be finite"),
        ({"delta_convention": "SPOT_PREM_EXCLUDED"}, "delta_convention must be"),
        ({"atm_convention": "FORWARD"}, "atm_convention must be"),
        ({"tenors": ()}, "at least one maturity"),
        ({"tenors": (tenor(0.5), tenor(0.5))}, "unique maturities"),
    ),
)
def test_term_structure_rejects_invalid_inputs(
    kwargs: dict[str, object],
    message: str,
) -> None:
    valid = {
        "spot": 1.085,
        "delta_convention": DeltaConvention.SPOT_PREM_EXCLUDED,
        "atm_convention": AtmConvention.FORWARD,
        "tenors": (tenor(0.5),),
    }
    valid.update(kwargs)

    with pytest.raises((TypeError, ValueError), match=message):
        FxMarketTermStructure(**valid)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"T": 0.0}, "T must be strictly positive"),
        ({"sigma_atm": 0.0}, "sigma_atm must be strictly positive"),
        ({"rr25": float("inf")}, "rr25 must be finite"),
    ),
)
def test_smile_quote_rejects_invalid_domains(
    kwargs: dict[str, float],
    message: str,
) -> None:
    valid = {"T": 0.5, "sigma_atm": 0.10, "rr25": -0.02, "bf25": 0.01}
    valid.update(kwargs)

    with pytest.raises(ValueError, match=message):
        SmileQuote(**valid)


@pytest.mark.parametrize("rate", (float("nan"), float("inf")))
def test_tenor_quote_rejects_non_finite_rates(rate: float) -> None:
    with pytest.raises(ValueError, match="domestic_rate must be finite"):
        TenorMarketQuote(quote=SmileQuote(0.5, 0.10, -0.02, 0.01), domestic_rate=rate, foreign_rate=0.02)
