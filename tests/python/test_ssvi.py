from __future__ import annotations

import numpy as np
import pytest

from vv_pricer import (
    SsviPowerLawParameters,
    ssvi_power_law_phi,
    ssvi_total_variance,
)


def test_scalar_atm_total_variance_equals_theta() -> None:
    parameters = SsviPowerLawParameters(rho=-0.4, eta=1.2, gamma=0.3)

    result = ssvi_total_variance(0.0, 0.04, parameters)

    assert isinstance(result, float)
    assert result == pytest.approx(0.04, abs=1e-15)


def test_symmetric_case_matches_closed_form() -> None:
    parameters = SsviPowerLawParameters(rho=0.0, eta=1.5, gamma=0.25)
    theta = 0.09
    log_moneyness = np.array([-0.3, -0.1, 0.0, 0.1, 0.3])
    phi = parameters.eta * theta ** (-parameters.gamma)
    expected = 0.5 * theta * (
        1.0 + np.sqrt(1.0 + np.square(phi * log_moneyness))
    )

    result = ssvi_total_variance(log_moneyness, theta, parameters)

    assert isinstance(result, np.ndarray)
    np.testing.assert_allclose(result, expected, rtol=1e-14, atol=0.0)
    np.testing.assert_allclose(result, result[::-1], rtol=0.0, atol=1e-15)


def test_array_inputs_broadcast_and_remain_positive() -> None:
    parameters = SsviPowerLawParameters(rho=-0.35, eta=1.1, gamma=0.2)
    log_moneyness = np.array([[-0.2, 0.0, 0.2]])
    theta = np.array([[0.01], [0.04], [0.09]])

    result = ssvi_total_variance(log_moneyness, theta, parameters)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)
    assert result.dtype == np.float64
    assert np.all(result > 0.0)
    np.testing.assert_allclose(result[:, 1], theta[:, 0], rtol=0.0, atol=1e-15)


def test_power_law_phi_scalar_and_array_behavior() -> None:
    parameters = SsviPowerLawParameters(rho=0.1, eta=2.0, gamma=0.5)

    scalar = ssvi_power_law_phi(0.25, parameters)
    array = ssvi_power_law_phi(np.array([0.25, 1.0]), parameters)

    assert scalar == pytest.approx(4.0)
    np.testing.assert_allclose(array, np.array([4.0, 2.0]))


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    (
        ({"rho": -1.0, "eta": 1.0, "gamma": 0.25}, ValueError, "rho"),
        ({"rho": 1.0, "eta": 1.0, "gamma": 0.25}, ValueError, "rho"),
        ({"rho": 0.0, "eta": 0.0, "gamma": 0.25}, ValueError, "positive"),
        ({"rho": 0.0, "eta": 1.0, "gamma": 0.0}, ValueError, "gamma"),
        ({"rho": 0.0, "eta": 1.0, "gamma": -0.1}, ValueError, "gamma"),
        ({"rho": 0.0, "eta": 1.0, "gamma": 0.6}, ValueError, "gamma"),
        ({"rho": 0.0, "eta": float("nan"), "gamma": 0.2}, ValueError, "finite"),
        ({"rho": True, "eta": 1.0, "gamma": 0.2}, TypeError, "real number"),
    ),
)
def test_parameters_reject_invalid_domains(
    kwargs: dict[str, object],
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        SsviPowerLawParameters(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("log_moneyness", "theta", "message"),
    (
        (0.0, 0.0, "positive"),
        (0.0, -0.01, "positive"),
        (0.0, float("inf"), "finite"),
        (float("nan"), 0.04, "finite"),
        (np.zeros(2), np.ones(3), "broadcast-compatible"),
    ),
)
def test_kernel_rejects_invalid_inputs(
    log_moneyness: object,
    theta: object,
    message: str,
) -> None:
    parameters = SsviPowerLawParameters(rho=0.0, eta=1.0, gamma=0.25)

    with pytest.raises(ValueError, match=message):
        ssvi_total_variance(log_moneyness, theta, parameters)
