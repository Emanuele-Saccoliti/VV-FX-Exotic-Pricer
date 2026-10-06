from __future__ import annotations

from dataclasses import dataclass
from math import erfc, isfinite, sqrt
from numbers import Integral, Real

import numpy as np
import numpy.typing as npt

from .ssvi import SsviPowerLawParameters, ssvi_power_law_phi, ssvi_total_variance


FloatArray = npt.NDArray[np.float64]
_SQRT_TWO = sqrt(2.0)


def _validated_real(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


@dataclass(frozen=True, slots=True)
class SsviArbitrageGridConfig:
    """Numerical grid used to supplement the analytic SSVI constraints.

    Log-forward-moneyness is dimensionless. Convexity is checked against
    normalized undiscounted call prices as a function of ``K/F = exp(k)``.
    """

    log_moneyness_min: float = -2.0
    log_moneyness_max: float = 2.0
    point_count: int = 2001
    tolerance: float = 1e-10

    def __post_init__(self) -> None:
        lower = _validated_real("log_moneyness_min", self.log_moneyness_min)
        upper = _validated_real("log_moneyness_max", self.log_moneyness_max)
        tolerance = _validated_real("tolerance", self.tolerance)
        if lower >= upper:
            raise ValueError("log_moneyness_min must be less than log_moneyness_max.")
        if isinstance(self.point_count, bool) or not isinstance(
            self.point_count, Integral
        ):
            raise TypeError("point_count must be an integer.")
        point_count = int(self.point_count)
        if point_count < 3:
            raise ValueError("point_count must be at least 3.")
        if tolerance < 0.0:
            raise ValueError("tolerance must be nonnegative.")
        log_grid = np.linspace(lower, upper, point_count, dtype=np.float64)
        with np.errstate(over="ignore", under="ignore"):
            strike_grid = np.exp(log_grid)
        if not np.all(np.isfinite(strike_grid)) or np.any(np.diff(strike_grid) <= 0):
            raise ValueError(
                "log-moneyness grid must produce finite, strictly increasing "
                "strike ratios."
            )
        object.__setattr__(self, "log_moneyness_min", lower)
        object.__setattr__(self, "log_moneyness_max", upper)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "tolerance", tolerance)


@dataclass(frozen=True, slots=True)
class SsviConstraintSlack:
    """One analytic inequality written as a nonnegative slack."""

    name: str
    value: float
    strict: bool
    maturity: float | None = None

    @property
    def is_satisfied(self) -> bool:
        return self.value > 0.0 if self.strict else self.value >= 0.0


@dataclass(frozen=True, slots=True)
class SsviCallGridDiagnostics:
    """Finite-grid normalized call-price checks for one SSVI slice."""

    minimum_monotonicity_slack: float
    minimum_convexity_slack: float
    minimum_lower_bound_slack: float
    minimum_upper_bound_slack: float
    tolerance: float

    @property
    def is_monotone(self) -> bool:
        return self.minimum_monotonicity_slack >= -self.tolerance

    @property
    def is_convex(self) -> bool:
        return self.minimum_convexity_slack >= -self.tolerance

    @property
    def respects_price_bounds(self) -> bool:
        return (
            self.minimum_lower_bound_slack >= -self.tolerance
            and self.minimum_upper_bound_slack >= -self.tolerance
        )

    @property
    def is_admissible(self) -> bool:
        return self.is_monotone and self.is_convex and self.respects_price_bounds


@dataclass(frozen=True, slots=True)
class SsviSliceDiagnostics:
    """Analytic wing and butterfly diagnostics for one ATM variance level."""

    maturity: float
    theta: float
    phi: float
    left_wing_slope: float
    right_wing_slope: float
    butterfly_linear_slack: float
    butterfly_quadratic_slack: float
    call_grid: SsviCallGridDiagnostics

    @property
    def has_admissible_wings(self) -> bool:
        return self.left_wing_slope < 2.0 and self.right_wing_slope < 2.0

    @property
    def satisfies_butterfly_constraints(self) -> bool:
        return (
            self.butterfly_linear_slack > 0.0
            and self.butterfly_quadratic_slack >= 0.0
        )

    @property
    def is_admissible(self) -> bool:
        return (
            self.has_admissible_wings
            and self.satisfies_butterfly_constraints
            and self.call_grid.is_admissible
        )


@dataclass(frozen=True, slots=True)
class SsviArbitrageDiagnostics:
    """Executable Gatheral-Jacquier diagnostics for a power-law SSVI surface."""

    maturities: tuple[float, ...]
    atm_total_variances: tuple[float, ...]
    calendar_theta_slacks: tuple[float, ...]
    calendar_shape_lower_slack: float
    calendar_shape_upper_slack: float
    slices: tuple[SsviSliceDiagnostics, ...]
    constraint_slacks: tuple[SsviConstraintSlack, ...]

    @property
    def minimum_constraint_slack(self) -> float:
        return min(slack.value for slack in self.constraint_slacks)

    @property
    def satisfies_analytic_constraints(self) -> bool:
        return all(slack.is_satisfied for slack in self.constraint_slacks)

    @property
    def is_admissible(self) -> bool:
        return self.satisfies_analytic_constraints and all(
            slice_diagnostics.call_grid.is_admissible
            for slice_diagnostics in self.slices
        )

    @property
    def violations(self) -> tuple[str, ...]:
        violations = [
            slack.name for slack in self.constraint_slacks if not slack.is_satisfied
        ]
        for slice_diagnostics in self.slices:
            if not slice_diagnostics.call_grid.is_monotone:
                violations.append(
                    f"call_monotonicity[T={slice_diagnostics.maturity:g}]"
                )
            if not slice_diagnostics.call_grid.is_convex:
                violations.append(f"call_convexity[T={slice_diagnostics.maturity:g}]")
            if not slice_diagnostics.call_grid.respects_price_bounds:
                violations.append(f"call_bounds[T={slice_diagnostics.maturity:g}]")
        return tuple(violations)


def _finite_vector(name: str, values: npt.ArrayLike) -> FloatArray:
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must contain real numbers.") from exc
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional.")
    if array.size == 0:
        raise ValueError(f"{name} must not be empty.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    return array


def _validated_term_structure(
    maturities: npt.ArrayLike,
    atm_total_variances: npt.ArrayLike,
) -> tuple[FloatArray, FloatArray]:
    maturity_values = _finite_vector("maturities", maturities)
    theta_values = _finite_vector("atm_total_variances", atm_total_variances)
    if maturity_values.shape != theta_values.shape:
        raise ValueError("maturities and atm_total_variances must have equal length.")
    if np.any(maturity_values <= 0.0):
        raise ValueError("maturities must contain only positive values.")
    if np.any(np.diff(maturity_values) <= 0.0):
        raise ValueError("maturities must be strictly increasing.")
    if np.any(theta_values <= 0.0):
        raise ValueError("atm_total_variances must contain only positive values.")
    return maturity_values, theta_values


def _normal_cdf(values: FloatArray) -> FloatArray:
    flat_values = values.ravel()
    cdf = np.fromiter(
        (0.5 * erfc(-float(value) / _SQRT_TWO) for value in flat_values),
        dtype=np.float64,
        count=flat_values.size,
    )
    return cdf.reshape(values.shape)


def _normalized_call_prices(
    log_moneyness: FloatArray,
    total_variance: FloatArray,
) -> FloatArray:
    standard_deviation = np.sqrt(total_variance)
    d_plus = -log_moneyness / standard_deviation + 0.5 * standard_deviation
    d_minus = d_plus - standard_deviation
    return _normal_cdf(d_plus) - np.exp(log_moneyness) * _normal_cdf(d_minus)


def _call_grid_diagnostics(
    theta: float,
    parameters: SsviPowerLawParameters,
    config: SsviArbitrageGridConfig,
) -> SsviCallGridDiagnostics:
    log_moneyness = np.linspace(
        config.log_moneyness_min,
        config.log_moneyness_max,
        config.point_count,
        dtype=np.float64,
    )
    strikes_over_forward = np.exp(log_moneyness)
    total_variance = np.asarray(
        ssvi_total_variance(log_moneyness, theta, parameters),
        dtype=np.float64,
    )
    call_prices = _normalized_call_prices(log_moneyness, total_variance)
    call_differences = call_prices[:-1] - call_prices[1:]
    secant_slopes = np.diff(call_prices) / np.diff(strikes_over_forward)
    convexity_slacks = np.diff(secant_slopes)
    intrinsic_values = np.maximum(1.0 - strikes_over_forward, 0.0)

    return SsviCallGridDiagnostics(
        minimum_monotonicity_slack=float(np.min(call_differences)),
        minimum_convexity_slack=float(np.min(convexity_slacks)),
        minimum_lower_bound_slack=float(np.min(call_prices - intrinsic_values)),
        minimum_upper_bound_slack=float(np.min(1.0 - call_prices)),
        tolerance=config.tolerance,
    )


def _calendar_shape_slacks(
    parameters: SsviPowerLawParameters,
) -> tuple[float, float]:
    calendar_shape_ratio = 1.0 - parameters.gamma
    if parameters.rho == 0.0:
        return calendar_shape_ratio, float("inf")
    upper_bound = (
        1.0 + sqrt(1.0 - parameters.rho**2)
    ) / parameters.rho**2
    return calendar_shape_ratio, upper_bound - calendar_shape_ratio


def _calendar_constraints(
    maturities: FloatArray,
    theta_values: FloatArray,
) -> tuple[FloatArray, list[SsviConstraintSlack]]:
    theta_slacks = np.diff(theta_values) / np.diff(maturities)
    constraints = [
        SsviConstraintSlack(
            name=f"calendar_theta_slope[T={maturity:g}]",
            value=float(slack),
            strict=False,
            maturity=float(maturity),
        )
        for maturity, slack in zip(maturities[1:], theta_slacks, strict=True)
    ]
    return theta_slacks, constraints


def _slice_diagnostics(
    maturity: float,
    theta: float,
    parameters: SsviPowerLawParameters,
    grid_config: SsviArbitrageGridConfig,
) -> tuple[SsviSliceDiagnostics, tuple[SsviConstraintSlack, ...]]:
    phi = float(ssvi_power_law_phi(theta, parameters))
    theta_phi = theta * phi
    rho_factor = 1.0 + abs(parameters.rho)
    linear_slack = 4.0 - theta_phi * rho_factor
    quadratic_slack = 4.0 - theta * phi * phi * rho_factor
    constraints = (
        SsviConstraintSlack(
            f"butterfly_linear[T={maturity:g}]", linear_slack, True, maturity
        ),
        SsviConstraintSlack(
            f"butterfly_quadratic[T={maturity:g}]",
            quadratic_slack,
            False,
            maturity,
        ),
    )
    diagnostics = SsviSliceDiagnostics(
        maturity=maturity,
        theta=theta,
        phi=phi,
        left_wing_slope=0.5 * theta_phi * (1.0 - parameters.rho),
        right_wing_slope=0.5 * theta_phi * (1.0 + parameters.rho),
        butterfly_linear_slack=linear_slack,
        butterfly_quadratic_slack=quadratic_slack,
        call_grid=_call_grid_diagnostics(theta, parameters, grid_config),
    )
    return diagnostics, constraints


def _surface_diagnostics(
    maturity_values: FloatArray,
    theta_values: FloatArray,
    parameters: SsviPowerLawParameters,
    grid_config: SsviArbitrageGridConfig,
) -> SsviArbitrageDiagnostics:
    calendar_theta_slacks, constraint_slacks = _calendar_constraints(
        maturity_values, theta_values
    )
    shape_lower, shape_upper = _calendar_shape_slacks(parameters)
    constraint_slacks.extend(
        (
            SsviConstraintSlack("calendar_shape_lower", shape_lower, False),
            SsviConstraintSlack("calendar_shape_upper", shape_upper, False),
        )
    )
    slices: list[SsviSliceDiagnostics] = []
    for maturity, theta in zip(maturity_values, theta_values, strict=True):
        slice_diagnostics, slice_constraints = _slice_diagnostics(
            float(maturity), float(theta), parameters, grid_config
        )
        slices.append(slice_diagnostics)
        constraint_slacks.extend(slice_constraints)

    return SsviArbitrageDiagnostics(
        maturities=tuple(float(value) for value in maturity_values),
        atm_total_variances=tuple(float(value) for value in theta_values),
        calendar_theta_slacks=tuple(
            float(value) for value in calendar_theta_slacks
        ),
        calendar_shape_lower_slack=shape_lower,
        calendar_shape_upper_slack=shape_upper,
        slices=tuple(slices),
        constraint_slacks=tuple(constraint_slacks),
    )


def diagnose_ssvi_no_arbitrage(
    maturities: npt.ArrayLike,
    atm_total_variances: npt.ArrayLike,
    parameters: SsviPowerLawParameters,
    *,
    grid_config: SsviArbitrageGridConfig | None = None,
) -> SsviArbitrageDiagnostics:
    """Diagnose sufficient SSVI static no-arbitrage conditions.

    ``maturities`` are year fractions and ``atm_total_variances`` are annualized
    implied variances multiplied by maturity. The analytic inequalities are
    those of Gatheral and Jacquier (2014), Theorems 4.1 and 4.2. Finite-grid
    call checks supplement, but do not replace, the sufficient conditions.
    """
    if not isinstance(parameters, SsviPowerLawParameters):
        raise TypeError("parameters must be SsviPowerLawParameters.")
    if grid_config is None:
        grid_config = SsviArbitrageGridConfig()
    elif not isinstance(grid_config, SsviArbitrageGridConfig):
        raise TypeError("grid_config must be SsviArbitrageGridConfig.")
    maturity_values, theta_values = _validated_term_structure(
        maturities, atm_total_variances
    )
    return _surface_diagnostics(
        maturity_values, theta_values, parameters, grid_config
    )


def require_ssvi_no_arbitrage(
    maturities: npt.ArrayLike,
    atm_total_variances: npt.ArrayLike,
    parameters: SsviPowerLawParameters,
    *,
    grid_config: SsviArbitrageGridConfig | None = None,
) -> SsviArbitrageDiagnostics:
    """Return diagnostics or raise when the supplied SSVI surface is inadmissible."""
    diagnostics = diagnose_ssvi_no_arbitrage(
        maturities,
        atm_total_variances,
        parameters,
        grid_config=grid_config,
    )
    if not diagnostics.is_admissible:
        violations = ", ".join(diagnostics.violations)
        message = f"SSVI surface violates no-arbitrage conditions: {violations}."
        raise ValueError(message)
    return diagnostics
