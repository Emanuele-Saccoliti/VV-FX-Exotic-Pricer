from __future__ import annotations

from typing import Any

import numpy as np

from .domain import SmileQuote
from .market import MarketSliceBuilder
from .pricer import VannaVolgaPricer


def _build_ordered_slices(
    builder: MarketSliceBuilder,
    spot: float,
    domestic_rate: float,
    foreign_rate: float,
    quotes: list[SmileQuote],
) -> list[Any]:
    if not quotes:
        raise ValueError("at least one smile quote is required")
    return sorted(
        (
            builder.build(spot, domestic_rate, foreign_rate, quote)
            for quote in quotes
        ),
        key=lambda market_slice: market_slice.maturity,
    )


def _pillar_log_moneyness_grid(
    market_slice: Any,
    n_points: int,
) -> np.ndarray:
    if n_points < 3:
        raise ValueError("at least three grid points are required")
    lower = np.log(market_slice.strike_25p / market_slice.strike_atm)
    upper = np.log(market_slice.strike_25c / market_slice.strike_atm)
    left_intervals = (n_points - 1) // 2
    right_intervals = n_points - 1 - left_intervals
    left = np.linspace(lower, 0.0, left_intervals + 1)
    right = np.linspace(0.0, upper, right_intervals + 1)
    return np.concatenate((left[:-1], right))


def plot_vv_smile(
    pricer: VannaVolgaPricer,
    market_slice: Any,
    n_points: int = 80,
) -> tuple[Any, Any]:
    import matplotlib.pyplot as plt

    strikes = np.linspace(
        market_slice.strike_25p,
        market_slice.strike_25c,
        n_points,
    )
    prices = pricer.price_vanilla_batch(market_slice, True, strikes)
    implied_vols = np.full(n_points, np.nan)

    for index, (strike, price) in enumerate(zip(strikes, prices, strict=True)):
        try:
            implied_vols[index] = pricer.implied_volatility(
                market_slice,
                True,
                float(strike),
                float(price),
            )
        except ValueError:
            pass

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(strikes, implied_vols, label="Vanna-Volga implied smile")
    ax.scatter(
        [
            market_slice.strike_25p,
            market_slice.strike_atm,
            market_slice.strike_25c,
        ],
        [
            market_slice.sigma_25p,
            market_slice.sigma_atm,
            market_slice.sigma_25c,
        ],
        label="Market pillars",
    )
    ax.set_xlabel("Strike")
    ax.set_ylabel("Implied volatility")
    ax.set_title("Vanna-Volga Reconstructed FX Volatility Smile")
    ax.grid(True)
    ax.legend()
    return fig, ax


def plot_vv_vol_surface(
    pricer: VannaVolgaPricer,
    builder: MarketSliceBuilder,
    spot: float,
    domestic_rate: float,
    foreign_rate: float,
    quotes: list[SmileQuote],
    n_strikes: int = 60,
) -> tuple[Any, Any]:
    import matplotlib.pyplot as plt

    market_slices = [
        builder.build(spot, domestic_rate, foreign_rate, quote)
        for quote in quotes
    ]
    strikes = np.linspace(
        min(market_slice.strike_25p for market_slice in market_slices),
        max(market_slice.strike_25c for market_slice in market_slices),
        n_strikes,
    )
    maturities = np.array(
        [market_slice.maturity for market_slice in market_slices],
        dtype=np.float64,
    )
    vol_surface = np.full((len(market_slices), n_strikes), np.nan)

    for row, market_slice in enumerate(market_slices):
        call_prices = pricer.price_vanilla_batch(market_slice, True, strikes)
        put_prices = pricer.price_vanilla_batch(market_slice, False, strikes)
        for column, strike in enumerate(strikes):
            is_call = strike >= market_slice.strike_atm
            target_price = call_prices[column] if is_call else put_prices[column]
            try:
                vol_surface[row, column] = pricer.implied_volatility(
                    market_slice,
                    is_call,
                    float(strike),
                    float(target_price),
                )
            except ValueError:
                pass

    strike_grid, maturity_grid = np.meshgrid(strikes, maturities)
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(strike_grid, maturity_grid, vol_surface, alpha=0.85)
    ax.set_xlabel("Strike")
    ax.set_ylabel("Maturity")
    ax.set_zlabel("Implied volatility")
    ax.set_title("Vanna-Volga FX Implied Volatility Surface")
    return fig, ax


def plot_vv_reconstructed_surface(
    pricer: VannaVolgaPricer,
    builder: MarketSliceBuilder,
    spot: float,
    domestic_rate: float,
    foreign_rate: float,
    quotes: list[SmileQuote],
    n_points: int = 81,
) -> tuple[Any, tuple[Any, Any]]:
    import matplotlib.pyplot as plt

    market_slices = _build_ordered_slices(
        builder,
        spot,
        domestic_rate,
        foreign_rate,
        quotes,
    )
    if len(market_slices) < 2:
        raise ValueError("surface plots require at least two maturities")

    maturities = np.array(
        [market_slice.maturity for market_slice in market_slices],
        dtype=np.float64,
    )
    moneyness_grid = np.empty((len(market_slices), n_points), dtype=np.float64)
    maturity_grid = np.repeat(maturities[:, np.newaxis], n_points, axis=1)
    vv_surface = np.full((len(market_slices), n_points), np.nan)

    for row, market_slice in enumerate(market_slices):
        log_moneyness = _pillar_log_moneyness_grid(market_slice, n_points)
        moneyness_grid[row] = log_moneyness
        strikes = market_slice.strike_atm * np.exp(log_moneyness)
        call_prices = pricer.price_vanilla_batch(market_slice, True, strikes)
        put_prices = pricer.price_vanilla_batch(market_slice, False, strikes)

        for column, (moneyness, strike) in enumerate(
            zip(log_moneyness, strikes, strict=True)
        ):
            is_call = moneyness >= 0.0
            vv_price = call_prices[column] if is_call else put_prices[column]
            try:
                vv_surface[row, column] = 100.0 * pricer.implied_volatility(
                    market_slice,
                    is_call,
                    float(strike),
                    float(vv_price),
                )
            except (RuntimeError, ValueError):
                pass

    figure = plt.figure(figsize=(11, 7.5), constrained_layout=True)
    vv_axis = figure.add_subplot(111, projection="3d")

    vv_axis.plot_surface(
        moneyness_grid,
        maturity_grid,
        vv_surface,
        cmap="viridis",
        alpha=0.9,
    )
    for index, market_slice in enumerate(market_slices):
        pillar_moneyness = np.log(
            np.array(
                [
                    market_slice.strike_25p,
                    market_slice.strike_atm,
                    market_slice.strike_25c,
                ]
            )
            / market_slice.strike_atm
        )
        vv_axis.scatter(
            pillar_moneyness,
            np.full(3, market_slice.maturity),
            100.0
            * np.array(
                [
                    market_slice.sigma_25p,
                    market_slice.sigma_atm,
                    market_slice.sigma_25c,
                ]
            ),
            color="black",
            s=18,
            label="Market pillars" if index == 0 else None,
        )

    x_limits = (float(np.min(moneyness_grid)), float(np.max(moneyness_grid)))
    vv_axis.set_xlabel("Log-moneyness ln(K/F)")
    vv_axis.set_ylabel("Maturity (years)")
    vv_axis.set_zlabel("Implied volatility (%)")
    vv_axis.set_xlim(*x_limits)
    vv_axis.view_init(elev=25, azim=-135)
    vv_axis.set_box_aspect((1.3, 1.0, 0.9))
    vv_axis.set_title("Vanna-Volga Reconstructed Volatility Surface")
    vv_axis.legend(loc="upper left")
    return figure, vv_axis


def plot_greek_profiles(
    pricer: VannaVolgaPricer,
    builder: MarketSliceBuilder,
    spot: float,
    domestic_rate: float,
    foreign_rate: float,
    quotes: list[SmileQuote],
    n_points: int = 81,
) -> tuple[Any, Any]:
    import matplotlib.pyplot as plt

    market_slices = _build_ordered_slices(
        builder,
        spot,
        domestic_rate,
        foreign_rate,
        quotes,
    )
    if n_points < 3:
        raise ValueError("at least three grid points are required")
    figure, axes = plt.subplots(
        1,
        3,
        figsize=(16, 5),
        sharex=True,
        constrained_layout=True,
    )
    greek_names = ("Vega", "Vanna", "Volga")

    for market_slice in market_slices:
        log_moneyness = _pillar_log_moneyness_grid(market_slice, n_points)
        strikes = market_slice.strike_atm * np.exp(log_moneyness)
        greek_values = pricer.greeks_batch(
            market_slice,
            strikes,
            market_slice.sigma_atm,
        )
        pillar_strikes = np.array(
            [
                market_slice.strike_25p,
                market_slice.strike_atm,
                market_slice.strike_25c,
            ]
        )
        pillar_moneyness = np.log(pillar_strikes / market_slice.strike_atm)
        pillar_greeks = pricer.greeks_batch(
            market_slice,
            pillar_strikes,
            market_slice.sigma_atm,
        )

        for index, axis in enumerate(axes):
            (line,) = axis.plot(
                log_moneyness,
                greek_values[:, index],
                label=f"T={market_slice.maturity:g}y",
            )
            axis.scatter(
                pillar_moneyness,
                pillar_greeks[:, index],
                color=line.get_color(),
                s=20,
                zorder=3,
            )

    for name, axis in zip(greek_names, axes, strict=True):
        axis.axvline(0.0, color="black", linewidth=0.8, alpha=0.5)
        axis.set_title(name)
        axis.set_xlabel("Log-moneyness ln(K/F)")
        axis.set_ylabel(name)
        axis.grid(True, alpha=0.3)

    axes[0].legend(title="Maturity")
    figure.suptitle("Analytic Greek Profiles at ATM Volatility")
    return figure, axes
