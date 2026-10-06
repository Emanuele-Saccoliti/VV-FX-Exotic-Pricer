from __future__ import annotations

import numpy as np
import pytest

from vv_pricer import (
    SsviArbitrageGridConfig,
    SsviPowerLawParameters,
    diagnose_ssvi_no_arbitrage,
    require_ssvi_no_arbitrage,
)


ADMISSIBLE_PARAMETERS = SsviPowerLawParameters(rho=-0.35, eta=0.8, gamma=0.25)
MATURITIES = np.array([0.25, 0.5, 1.0, 2.0])
ATM_TOTAL_VARIANCES = np.array([0.0025, 0.0055, 0.012, 0.026])


def test_admissible_power_law_surface_reports_positive_slacks() -> None:
    diagnostics = diagnose_ssvi_no_arbitrage(
        MATURITIES,
        ATM_TOTAL_VARIANCES,
        ADMISSIBLE_PARAMETERS,
    )

    assert require_ssvi_no_arbitrage(
        MATURITIES,
        ATM_TOTAL_VARIANCES,
        ADMISSIBLE_PARAMETERS,
    ) == diagnostics
    assert diagnostics.is_admissible
    assert diagnostics.satisfies_analytic_constraints
    assert diagnostics.minimum_constraint_slack > 0.0
    assert diagnostics.calendar_theta_slacks == pytest.approx(
        (0.012, 0.013, 0.014)
    )
    assert diagnostics.calendar_shape_lower_slack == pytest.approx(0.75)
    assert all(slice_.has_admissible_wings for slice_ in diagnostics.slices)
    assert all(slice_.call_grid.is_monotone for slice_ in diagnostics.slices)
    assert all(slice_.call_grid.is_convex for slice_ in diagnostics.slices)
    assert all(
        slice_.call_grid.respects_price_bounds for slice_ in diagnostics.slices
    )


def test_flat_atm_total_variance_is_calendar_admissible() -> None:
    diagnostics = diagnose_ssvi_no_arbitrage(
        [0.5, 1.0],
        [0.01, 0.01],
        ADMISSIBLE_PARAMETERS,
    )

    assert diagnostics.calendar_theta_slacks == (0.0,)
    assert diagnostics.is_admissible


def test_decreasing_atm_total_variance_is_rejected() -> None:
    diagnostics = diagnose_ssvi_no_arbitrage(
        [0.5, 1.0],
        [0.02, 0.01],
        ADMISSIBLE_PARAMETERS,
    )

    assert not diagnostics.is_admissible
    assert diagnostics.calendar_theta_slacks == pytest.approx((-0.02,))
    assert diagnostics.violations == ("calendar_theta_slope[T=1]",)
    with pytest.raises(ValueError, match="calendar_theta_slope"):
        require_ssvi_no_arbitrage(
            [0.5, 1.0],
            [0.02, 0.01],
            ADMISSIBLE_PARAMETERS,
        )


def test_butterfly_violation_is_detected_analytically_and_on_call_grid() -> None:
    parameters = SsviPowerLawParameters(rho=0.0, eta=4.0, gamma=0.5)
    diagnostics = diagnose_ssvi_no_arbitrage([1.0], [0.5], parameters)
    slice_diagnostics = diagnostics.slices[0]

    assert slice_diagnostics.butterfly_linear_slack > 0.0
    assert slice_diagnostics.butterfly_quadratic_slack < 0.0
    assert not slice_diagnostics.call_grid.is_convex
    assert "butterfly_quadratic[T=1]" in diagnostics.violations
    assert "call_convexity[T=1]" in diagnostics.violations
    assert not diagnostics.is_admissible


def test_wing_slopes_match_ssvi_asymptotes() -> None:
    parameters = SsviPowerLawParameters(rho=-0.4, eta=1.0, gamma=0.5)
    diagnostics = diagnose_ssvi_no_arbitrage([1.0], [0.04], parameters)
    slice_diagnostics = diagnostics.slices[0]

    assert slice_diagnostics.phi == pytest.approx(5.0)
    assert slice_diagnostics.left_wing_slope == pytest.approx(0.14)
    assert slice_diagnostics.right_wing_slope == pytest.approx(0.06)
    assert slice_diagnostics.butterfly_linear_slack == pytest.approx(3.72)


@pytest.mark.parametrize(
    ("maturities", "theta", "message"),
    (
        ([], [], "must not be empty"),
        ([1.0, 0.5], [0.01, 0.02], "strictly increasing"),
        ([0.5, 1.0], [0.01], "equal length"),
        ([0.5], [0.0], "positive"),
        ([[0.5]], [[0.01]], "one-dimensional"),
    ),
)
def test_diagnostics_reject_invalid_term_structure_inputs(
    maturities: object,
    theta: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        diagnose_ssvi_no_arbitrage(maturities, theta, ADMISSIBLE_PARAMETERS)


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    (
        (
            {"log_moneyness_min": 1.0, "log_moneyness_max": 1.0},
            ValueError,
            "less than",
        ),
        ({"point_count": 2}, ValueError, "at least 3"),
        ({"point_count": 3.5}, TypeError, "integer"),
        ({"tolerance": -1e-12}, ValueError, "nonnegative"),
        (
            {"log_moneyness_min": -1000.0, "log_moneyness_max": 1000.0},
            ValueError,
            "finite, strictly increasing",
        ),
    ),
)
def test_grid_config_rejects_invalid_values(
    kwargs: dict[str, object],
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        SsviArbitrageGridConfig(**kwargs)  # type: ignore[arg-type]
