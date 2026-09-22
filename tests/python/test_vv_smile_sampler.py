from __future__ import annotations

from math import exp

import pytest

from vv_pricer import (
    AtmConvention,
    DeltaConvention,
    FxMarketTermStructure,
    SmilePointProvenance,
    SmileQuote,
    TenorMarketQuote,
    VannaVolgaSmileSampler,
    VvSmileSamplingConfig,
    build_application,
)


def _term_structure(
    convention: DeltaConvention = DeltaConvention.SPOT_PREM_EXCLUDED,
) -> FxMarketTermStructure:
    return FxMarketTermStructure.from_tenors(
        spot=1.085,
        delta_convention=convention,
        atm_convention=AtmConvention.FORWARD,
        tenors=(
            TenorMarketQuote(SmileQuote(1.0, 0.11, -0.018, 0.007), 0.032, 0.021),
            TenorMarketQuote(SmileQuote(0.25, 0.095, -0.012, 0.004), 0.030, 0.020),
        ),
    )


@pytest.mark.parametrize("convention", list(DeltaConvention))
def test_sampler_returns_complete_ordered_smiles_with_pillar_provenance(
    convention: DeltaConvention,
) -> None:
    market = _term_structure(convention)
    samples = VannaVolgaSmileSampler().sample(market)

    assert tuple(sample.maturity for sample in samples) == (0.25, 1.0)
    for sample, tenor in zip(samples, market.tenors, strict=True):
        assert sample.forward == pytest.approx(
            market.spot
            * exp((tenor.domestic_rate - tenor.foreign_rate) * tenor.maturity)
        )
        assert sample.strikes == tuple(sorted(sample.strikes))
        assert len(sample.points) == 17
        assert len(sample.liquid_pillars) == 3
        assert len(sample.synthetic_points) == 14
        assert tuple(point.provenance for point in sample.liquid_pillars) == (
            SmilePointProvenance.LIQUID_25P,
            SmilePointProvenance.LIQUID_ATM,
            SmilePointProvenance.LIQUID_25C,
        )
        assert all(volatility > 0.0 for volatility in sample.implied_volatilities)
        assert sample.total_variances == pytest.approx(
            tuple(
                volatility**2 * sample.maturity
                for volatility in sample.implied_volatilities
            )
        )


def test_pillars_match_existing_single_slice_results_exactly() -> None:
    market = _term_structure()
    sample = VannaVolgaSmileSampler().sample(market)[0]
    tenor = market.tenors[0]
    existing_slice = build_application(market.delta_convention).builder.build(
        market.spot,
        tenor.domestic_rate,
        tenor.foreign_rate,
        tenor.quote,
    )

    assert tuple(point.strike for point in sample.liquid_pillars) == (
        existing_slice.strike_25p,
        existing_slice.strike_atm,
        existing_slice.strike_25c,
    )
    assert tuple(point.implied_volatility for point in sample.liquid_pillars) == (
        existing_slice.sigma_25p,
        existing_slice.sigma_atm,
        existing_slice.sigma_25c,
    )


def test_sampled_volatilities_reprice_the_complete_vv_smile() -> None:
    market = _term_structure()
    application = build_application(market.delta_convention)

    for sample, tenor in zip(
        VannaVolgaSmileSampler().sample(market), market.tenors, strict=True
    ):
        market_slice = application.builder.build(
            market.spot,
            tenor.domestic_rate,
            tenor.foreign_rate,
            tenor.quote,
        )
        for point in sample.points:
            is_call = point.strike >= sample.forward
            vv_price = application.pricer.price_vanilla(
                market_slice, is_call, point.strike
            )
            gk_price = application.engine.gk_price(
                is_call,
                market.spot,
                point.strike,
                sample.maturity,
                tenor.domestic_rate,
                tenor.foreign_rate,
                point.implied_volatility,
            )
            assert gk_price == pytest.approx(vv_price, abs=3e-12, rel=0.0)


def test_wing_cutoffs_are_explicit_and_configurable() -> None:
    market = _term_structure()
    without_extension = VannaVolgaSmileSampler(
        VvSmileSamplingConfig(
            synthetic_points_per_interval=0,
            wing_extension_fraction=0.0,
        )
    ).sample(market)[0]
    with_extension = VannaVolgaSmileSampler(
        VvSmileSamplingConfig(
            synthetic_points_per_interval=0,
            wing_extension_fraction=1.0,
        )
    ).sample(market)[0]

    assert len(without_extension.points) == 3
    assert without_extension.reliable_log_moneyness_min == pytest.approx(
        without_extension.liquid_pillars[0].log_forward_moneyness
    )
    assert without_extension.reliable_log_moneyness_max == pytest.approx(
        without_extension.liquid_pillars[-1].log_forward_moneyness
    )
    assert with_extension.reliable_log_moneyness_min < (
        without_extension.reliable_log_moneyness_min
    )
    assert with_extension.reliable_log_moneyness_max > (
        without_extension.reliable_log_moneyness_max
    )


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    (
        ({"synthetic_points_per_interval": -1}, ValueError, "non-negative"),
        ({"synthetic_points_per_interval": 1.5}, TypeError, "integer"),
        ({"wing_extension_fraction": -0.1}, ValueError, "between 0 and 1"),
        ({"wing_extension_fraction": float("nan")}, ValueError, "finite"),
    ),
)
def test_sampling_config_rejects_invalid_values(
    kwargs: dict[str, object],
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        VvSmileSamplingConfig(**kwargs)  # type: ignore[arg-type]
