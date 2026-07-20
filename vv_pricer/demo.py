from __future__ import annotations

from .application import build_application
from .conventions import DeltaConvention
from .domain import SmileQuote


def run_demo(convention: DeltaConvention, show_plots: bool = False) -> None:
    spot = 1.0850
    domestic_rate = 0.03
    foreign_rate = 0.02
    quote = SmileQuote(T=0.5, sigma_atm=0.10, rr25=-0.02, bf25=0.01)

    application = build_application(convention)
    market_slice = application.builder.build(
        spot,
        domestic_rate,
        foreign_rate,
        quote,
    )
    pricer = application.pricer

    print(f"C++ backend version: {application.engine.backend_version}")
    print(f"Delta convention: {convention}")
    print(f"MarketSlice(T={market_slice.maturity:.4f})")
    print(
        f"S={market_slice.spot:.6f} "
        f"rd={market_slice.domestic_rate:.4f} "
        f"rf={market_slice.foreign_rate:.4f}"
    )
    print(
        f"sigmaATM={market_slice.sigma_atm:.4f} "
        f"sigma25P={market_slice.sigma_25p:.4f} "
        f"sigma25C={market_slice.sigma_25c:.4f}"
    )
    print(
        f"K_ATM={market_slice.strike_atm:.6f} "
        f"K_25P={market_slice.strike_25p:.6f} "
        f"K_25C={market_slice.strike_25c:.6f}"
    )
    print()

    strike = 1.10
    weight_result = pricer.weights(market_slice, strike)
    weights_base = tuple(weight_result.atm_rr_bf)
    weights_pillars = tuple(weight_result.pillars)
    print(
        f"VV weights base @K={strike:.4f} -> "
        f"wATM={weights_base[0]:+.8f} "
        f"wRR={weights_base[1]:+.8f} "
        f"wBF={weights_base[2]:+.8f}"
    )
    print(
        f"VV weights pillars @K={strike:.4f} -> "
        f"w25P={weights_pillars[0]:+.8f} "
        f"wATM={weights_pillars[1]:+.8f} "
        f"w25C={weights_pillars[2]:+.8f}"
    )
    print(
        f"Greek matrix condition number: {weight_result.condition_number:.6e}; "
        f"solve residual: {weight_result.residual_inf_norm:.3e}; "
        f"backward error: {weight_result.backward_error:.3e}"
    )
    print()

    gk_call = application.engine.gk_price(
        True,
        spot,
        strike,
        quote.T,
        domestic_rate,
        foreign_rate,
        quote.sigma_atm,
    )
    gk_put = application.engine.gk_price(
        False,
        spot,
        strike,
        quote.T,
        domestic_rate,
        foreign_rate,
        quote.sigma_atm,
    )
    print(
        f"GKBS Call (K={strike:.4f}, sigma=ATM "
        f"{100.0 * quote.sigma_atm:.2f}%): {gk_call:.8f}"
    )
    print(
        f"GKBS Put  (K={strike:.4f}, sigma=ATM "
        f"{100.0 * quote.sigma_atm:.2f}%): {gk_put:.8f}"
    )
    print()

    print(
        f"VV Call (K={strike:.4f}): "
        f"{pricer.price_vanilla(market_slice, True, strike):.8f}"
    )
    print(
        f"VV Put  (K={strike:.4f}): "
        f"{pricer.price_vanilla(market_slice, False, strike):.8f}"
    )
    print(
        f"VV Digital Call (K={strike:.4f}): "
        f"{pricer.price_digital_call(market_slice, strike):.8f}"
    )
    print(
        f"VV Digital Put  (K={strike:.4f}): "
        f"{pricer.price_digital_put(market_slice, strike):.8f}"
    )

    diagnostic_strikes = [
        market_slice.strike_25p
        + index * (market_slice.strike_25c - market_slice.strike_25p) / 100.0
        for index in range(101)
    ]
    call_checks = pricer.check_arbitrage(
        market_slice,
        True,
        diagnostic_strikes,
    )
    put_checks = pricer.check_arbitrage(
        market_slice,
        False,
        diagnostic_strikes,
    )
    put_call_parity = pricer.check_put_call_parity(market_slice, strike)
    digital_parity = pricer.check_digital_parity(market_slice, strike)
    digital_call_bounds = pricer.check_digital_bounds(
        market_slice,
        True,
        [strike],
    )
    digital_put_bounds = pricer.check_digital_bounds(
        market_slice,
        False,
        [strike],
    )
    print()
    print(
        "Call strike checks: "
        f"bounds={call_checks.within_bounds} "
        f"monotonic={call_checks.monotonic} "
        f"convex={call_checks.convex} "
        f"violations={call_checks.monotonicity_violations + call_checks.convexity_violations}"
    )
    print(
        "Put strike checks:  "
        f"bounds={put_checks.within_bounds} "
        f"monotonic={put_checks.monotonic} "
        f"convex={put_checks.convex} "
        f"violations={put_checks.monotonicity_violations + put_checks.convexity_violations}"
    )
    print(
        "Parity checks:      "
        f"put-call={put_call_parity.passed} "
        f"digital={digital_parity.passed}"
    )
    print(
        "Digital bounds:     "
        f"call={digital_call_bounds.within_bounds} "
        f"put={digital_put_bounds.within_bounds}"
    )

    if show_plots:
        import matplotlib.pyplot as plt

        from .plotting import (
            plot_greek_profiles,
            plot_vv_smile,
            plot_vv_reconstructed_surface,
        )

        surface_quotes = [
            SmileQuote(T=0.25, sigma_atm=0.095, rr25=-0.012, bf25=0.006),
            SmileQuote(T=0.50, sigma_atm=0.100, rr25=-0.020, bf25=0.010),
            SmileQuote(T=1.00, sigma_atm=0.105, rr25=-0.018, bf25=0.012),
            SmileQuote(T=2.00, sigma_atm=0.110, rr25=-0.014, bf25=0.014),
        ]
        plot_vv_smile(pricer, market_slice)
        plot_vv_reconstructed_surface(
            pricer,
            application.builder,
            spot,
            domestic_rate,
            foreign_rate,
            surface_quotes,
        )
        plot_greek_profiles(
            pricer,
            application.builder,
            spot,
            domestic_rate,
            foreign_rate,
            surface_quotes,
        )
        plt.show()
