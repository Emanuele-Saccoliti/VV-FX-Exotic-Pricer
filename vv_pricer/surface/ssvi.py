from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

import numpy as np
import numpy.typing as npt


FloatArray = npt.NDArray[np.float64]
ScalarOrArray = float | FloatArray


def _validated_real(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


@dataclass(frozen=True, slots=True)
class SsviPowerLawParameters:
    """Parameters for ``phi(theta) = eta * theta**(-gamma)``.

    ``rho`` controls skew and lies strictly between -1 and 1. ``eta`` is a
    positive scale and ``gamma`` lies in (0, 0.5]. These are parameter-domain
    checks only; surface-level no-arbitrage constraints belong to M05.
    """

    rho: float
    eta: float
    gamma: float

    def __post_init__(self) -> None:
        rho = _validated_real("rho", self.rho)
        eta = _validated_real("eta", self.eta)
        gamma = _validated_real("gamma", self.gamma)
        if not -1.0 < rho < 1.0:
            raise ValueError("rho must lie strictly between -1 and 1.")
        if eta <= 0.0:
            raise ValueError("eta must be positive.")
        if not 0.0 < gamma <= 0.5:
            raise ValueError("gamma must be greater than 0 and at most 0.5.")
        object.__setattr__(self, "rho", rho)
        object.__setattr__(self, "eta", eta)
        object.__setattr__(self, "gamma", gamma)


def _as_finite_array(name: str, values: npt.ArrayLike) -> FloatArray:
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must contain real numbers.") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    return array


def _positive_theta(theta: npt.ArrayLike) -> FloatArray:
    theta_array = _as_finite_array("theta", theta)
    if np.any(theta_array <= 0.0):
        raise ValueError("theta must contain only positive values.")
    return theta_array


def _broadcast_inputs(
    log_forward_moneyness: npt.ArrayLike,
    theta: npt.ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    k_array = _as_finite_array("log_forward_moneyness", log_forward_moneyness)
    theta_array = _positive_theta(theta)
    try:
        return np.broadcast_arrays(k_array, theta_array)
    except ValueError as exc:
        raise ValueError(
            "log_forward_moneyness and theta must be broadcast-compatible."
        ) from exc


def ssvi_power_law_phi(
    theta: npt.ArrayLike,
    parameters: SsviPowerLawParameters,
) -> ScalarOrArray:
    """Evaluate the power-law SSVI shape function for positive total variance."""
    if not isinstance(parameters, SsviPowerLawParameters):
        raise TypeError("parameters must be SsviPowerLawParameters.")
    theta_array = _positive_theta(theta)

    phi = parameters.eta * np.power(theta_array, -parameters.gamma)
    if not np.all(np.isfinite(phi)):
        raise ValueError("power-law phi is not finite for the supplied theta.")
    return float(phi) if phi.ndim == 0 else phi


def ssvi_total_variance(
    log_forward_moneyness: npt.ArrayLike,
    theta: npt.ArrayLike,
    parameters: SsviPowerLawParameters,
) -> ScalarOrArray:
    """Return SSVI total variance, broadcasting ``k`` and ``theta`` inputs.

    ``log_forward_moneyness`` is dimensionless ``log(K/F)`` and ``theta`` is
    positive ATM total variance. Scalar inputs produce a float; otherwise the
    result is a NumPy ``float64`` array with the broadcast shape.
    """
    if not isinstance(parameters, SsviPowerLawParameters):
        raise TypeError("parameters must be SsviPowerLawParameters.")
    k_values, theta_values = _broadcast_inputs(log_forward_moneyness, theta)

    phi = parameters.eta * np.power(theta_values, -parameters.gamma)
    scaled_moneyness = phi * k_values
    radicand = (
        np.square(scaled_moneyness + parameters.rho)
        + 1.0
        - parameters.rho**2
    )
    total_variance = 0.5 * theta_values * (
        1.0
        + parameters.rho * scaled_moneyness
        + np.sqrt(radicand)
    )
    if not np.all(np.isfinite(total_variance)):
        raise ValueError("SSVI total variance is not finite for the supplied inputs.")
    if np.any(total_variance <= 0.0):
        raise ValueError("SSVI total variance must be positive.")
    return (
        float(total_variance)
        if total_variance.ndim == 0
        else np.asarray(total_variance, dtype=np.float64)
    )
