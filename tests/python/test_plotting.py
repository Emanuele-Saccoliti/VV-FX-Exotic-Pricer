from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from vv_pricer import SmileQuote, build_application
from vv_pricer.plotting import (
    plot_greek_profiles,
    plot_vv_reconstructed_surface,
    plot_vv_smile,
)


def test_smile_and_surface_render() -> None:
    application = build_application()
    quote = SmileQuote(T=0.5, sigma_atm=0.10, rr25=-0.02, bf25=0.01)
    market_slice = application.builder.build(1.085, 0.03, 0.02, quote)

    smile_figure, _ = plot_vv_smile(
        application.pricer,
        market_slice,
        n_points=12,
    )
    quotes = [
        SmileQuote(T=0.25, sigma_atm=0.095, rr25=-0.012, bf25=0.006),
        quote,
        SmileQuote(T=1.0, sigma_atm=0.105, rr25=-0.018, bf25=0.012),
    ]
    surface_figure, surface_axis = plot_vv_reconstructed_surface(
        application.pricer,
        application.builder,
        1.085,
        0.03,
        0.02,
        quotes,
        n_points=9,
    )
    greek_figure, greek_axes = plot_greek_profiles(
        application.pricer,
        application.builder,
        1.085,
        0.03,
        0.02,
        quotes,
        n_points=9,
    )

    smile_figure.canvas.draw()
    surface_figure.canvas.draw()
    greek_figure.canvas.draw()
    assert smile_figure.axes
    assert len(surface_figure.axes) == 1
    assert len(greek_axes) == 3
    assert surface_axis.get_zlabel() == "Implied volatility (%)"
    assert surface_axis.get_title().startswith("Vanna-Volga Reconstructed")
    assert [axis.get_title() for axis in greek_axes] == ["Vega", "Vanna", "Volga"]
