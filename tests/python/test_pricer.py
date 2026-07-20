from __future__ import annotations

import math

import numpy as np
import pytest

from vv_pricer import DeltaConvention, SmileQuote, build_application


@pytest.fixture
def quote() -> SmileQuote:
    return SmileQuote(T=0.5, sigma_atm=0.10, rr25=-0.02, bf25=0.01)


@pytest.mark.parametrize("convention", list(DeltaConvention))
def test_pricing_and_diagnostics(
    convention: DeltaConvention,
    quote: SmileQuote,
) -> None:
    application = build_application(convention)
    market_slice = application.builder.build(1.085, 0.03, 0.02, quote)
    pricer = application.pricer
    strike = 1.10

    call = pricer.price_vanilla(market_slice, True, strike)
    put = pricer.price_vanilla(market_slice, False, strike)
    digital_call = pricer.price_digital_call(market_slice, strike)
    digital_put = pricer.price_digital_put(market_slice, strike)

    assert all(
        math.isfinite(value)
        for value in (call, put, digital_call, digital_put)
    )
    assert pricer.check_put_call_parity(market_slice, strike).passed
    assert pricer.check_digital_parity(market_slice, strike).passed

    strikes = np.linspace(
        market_slice.strike_25p,
        market_slice.strike_25c,
        81,
    )
    call_checks = pricer.check_arbitrage(market_slice, True, strikes)
    put_checks = pricer.check_arbitrage(market_slice, False, strikes)
    assert call_checks.within_bounds and call_checks.monotonic
    assert call_checks.convex
    assert put_checks.within_bounds and put_checks.monotonic
    assert put_checks.convex

    digital_strikes = np.array([market_slice.strike_atm])
    assert pricer.check_digital_bounds(
        market_slice,
        True,
        digital_strikes,
    ).within_bounds
    assert pricer.check_digital_bounds(
        market_slice,
        False,
        digital_strikes,
    ).within_bounds


def test_pillar_repricing(quote: SmileQuote) -> None:
    application = build_application()
    market_slice = application.builder.build(1.085, 0.03, 0.02, quote)

    for strike, volatility in (
        (market_slice.strike_25p, market_slice.sigma_25p),
        (market_slice.strike_atm, market_slice.sigma_atm),
        (market_slice.strike_25c, market_slice.sigma_25c),
    ):
        for is_call in (True, False):
            vv_price = application.pricer.price_vanilla(
                market_slice,
                is_call,
                strike,
            )
            market_price = application.engine.gk_price(
                is_call,
                market_slice.spot,
                strike,
                market_slice.maturity,
                market_slice.domestic_rate,
                market_slice.foreign_rate,
                volatility,
            )
            assert vv_price == pytest.approx(market_price, abs=3e-12)


def test_cpp_analytic_greeks_against_cpp_fd_richardson() -> None:
    engine = build_application().engine
    scenarios = (
        (0.75, 0.70, 0.10, -0.005, 0.01, 0.07),
        (0.90, 1.00, 0.25, 0.02, 0.00, 0.12),
        (1.085, 1.10, 0.50, 0.03, 0.02, 0.10),
        (1.20, 1.20, 1.00, 0.05, 0.01, 0.18),
        (1.50, 1.35, 2.00, 0.08, 0.04, 0.25),
        (1.75, 2.00, 3.00, 0.10, -0.01, 0.35),
    )

    for scenario in scenarios:
        analytic = engine.analytic_greeks(*scenario)
        finite_difference = engine.finite_difference_greeks(*scenario)
        assert analytic.vega == pytest.approx(
            finite_difference.vega,
            abs=1e-9,
            rel=1e-7,
        )
        assert analytic.vanna == pytest.approx(
            finite_difference.vanna,
            abs=1e-6,
            rel=1e-5,
        )
        assert analytic.volga == pytest.approx(
            finite_difference.volga,
            abs=1e-6,
            rel=1e-5,
        )


def test_fixed_bump_richardson_digital_against_flat_smile_gk() -> None:
    application = build_application()
    quote = SmileQuote(T=0.75, sigma_atm=0.14, rr25=0.0, bf25=0.0)
    market_slice = application.builder.build(1.20, 0.04, 0.01, quote)
    domestic_df = math.exp(-market_slice.domestic_rate * quote.T)
    forward = market_slice.spot * math.exp(
        (market_slice.domestic_rate - market_slice.foreign_rate) * quote.T
    )

    for log_moneyness in (-0.15, 0.0, 0.15):
        strike = forward * math.exp(log_moneyness)
        vol_sqrt_t = quote.sigma_atm * math.sqrt(quote.T)
        d2 = (
            math.log(forward / strike)
            - 0.5 * quote.sigma_atm**2 * quote.T
        ) / vol_sqrt_t
        exact_call = domestic_df * 0.5 * math.erfc(-d2 / math.sqrt(2.0))
        exact_put = domestic_df - exact_call

        assert application.pricer.price_digital_call(
            market_slice,
            strike,
        ) == pytest.approx(exact_call, abs=1e-9)
        assert application.pricer.price_digital_put(
            market_slice,
            strike,
        ) == pytest.approx(exact_put, abs=1e-9)
