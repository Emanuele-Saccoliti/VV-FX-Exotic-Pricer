from __future__ import annotations

import math
import sys
import numpy as np
from scipy.stats import norm
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence
import matplotlib.pyplot as plt



# Conventions ============================================================
class DeltaConvention(Enum):
    SPOT_PREM_EXCLUDED = "SPOT_PREM_EXCLUDED"
    FWD_PREM_EXCLUDED = "FWD_PREM_EXCLUDED"
    SPOT_PREM_INCLUDED = "SPOT_PREM_INCLUDED"

    @classmethod
    def parse(cls, raw: str | None) -> "DeltaConvention":
        if raw is None or not raw.strip():
            return cls.SPOT_PREM_EXCLUDED

        normalized = raw.strip().upper().replace("-", "_")
        aliases = {
            "SPOT_PREM_EXCL": cls.SPOT_PREM_EXCLUDED,
            "FWD_PREM_EXCL": cls.FWD_PREM_EXCLUDED,
            "SPOT_PREM_INCL": cls.SPOT_PREM_INCLUDED,
        }
        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls[normalized]
        except KeyError as exc:
            supported = ", ".join(item.name for item in cls)
            raise ValueError(f"Unknown delta convention '{raw}'. Supported: {supported}.") from exc

    def __str__(self) -> str:
        return self.name



# Numericals ============================================================
@dataclass(frozen=True)
class BisectionRootFinder:
    max_iter: int = 100
    tol: float = 1e-12

    def solve(self, f: Callable[[float], float], lo: float, hi: float) -> float:
        flo = f(lo)
        fhi = f(hi)

        if math.isnan(flo) or math.isnan(fhi):
            raise ValueError("RootFinder: f(lo) or f(hi) is NaN.")
        if flo * fhi > 0.0:
            raise ValueError("RootFinder: root not bracketed.")

        a = lo
        b = hi
        fa = flo

        for _ in range(self.max_iter):
            m = 0.5 * (a + b)
            fm = f(m)

            if abs(fm) < self.tol or (b - a) < self.tol:
                return m

            if fa * fm <= 0.0:
                b = m
            else:
                a = m
                fa = fm

        return 0.5 * (a + b)


class GaussianElimination3:
    def solve(
        self,
        a_matrix: Sequence[Sequence[float]],
        b_vector: Sequence[float],
    ) -> tuple[float, float, float]:
        if len(a_matrix) != 3 or any(len(row) != 3 for row in a_matrix) or len(b_vector) != 3:
            raise ValueError("LinearSolver3 expects 3x3 matrix and length-3 vector.")

        matrix = [[float(a_matrix[i][j]) for j in range(3)] for i in range(3)]
        y = [float(b_vector[i]) for i in range(3)]

        for col in range(3):
            pivot = col
            best = abs(matrix[col][col])
            for row in range(col + 1, 3):
                value = abs(matrix[row][col])
                if value > best:
                    best = value
                    pivot = row

            if best < 1e-14:
                raise ArithmeticError("LinearSolver3: singular/ill-conditioned matrix.")

            if pivot != col:
                matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
                y[col], y[pivot] = y[pivot], y[col]

            for row in range(col + 1, 3):
                factor = matrix[row][col] / matrix[col][col]
                for c_idx in range(col, 3):
                    matrix[row][c_idx] -= factor * matrix[col][c_idx]
                y[row] -= factor * y[col]

        x = [0.0, 0.0, 0.0]
        for i in range(2, -1, -1):
            subtotal = y[i]
            for j in range(i + 1, 3):
                subtotal -= matrix[i][j] * x[j]
            x[i] = subtotal / matrix[i][i]

        return (x[0], x[1], x[2])



# Garman-Kohlhagen Black-Scholes ===============================
class GKBlackScholes:
    @staticmethod
    def forward(s: float, rd: float, rf: float, t: float) -> float:
        return s * math.exp((rd - rf) * t)

    @staticmethod
    def df(rate: float, t: float) -> float:
        return math.exp(-rate * t)

    def price(
        self,
        is_call: bool,
        s: float,
        k: float,
        t: float,
        rd: float,
        rf: float,
        sigma: float,
    ) -> float:
        if t <= 0.0:
            return max(s - k, 0.0) if is_call else max(k - s, 0.0)

        fwd = self.forward(s, rd, rf, t)
        dfd = self.df(rd, t)
        vol_sqrt_t = sigma * math.sqrt(t)
        d1 = (math.log(fwd / k) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t

        if is_call:
            return dfd * (fwd * norm.cdf(d1) - k * norm.cdf(d2))
        return dfd * (k * norm.cdf(-d2) - fwd * norm.cdf(-d1))

    def delta(
        self,
        convention: DeltaConvention,
        is_call: bool,
        s: float,
        k: float,
        t: float,
        rd: float,
        rf: float,
        sigma: float,
    ) -> float:
        if t <= 0.0:
            if is_call:
                return 1.0 if s > k else 0.0
            return -1.0 if s < k else 0.0

        fwd = self.forward(s, rd, rf, t)
        vol_sqrt_t = sigma * math.sqrt(t)
        d1 = (math.log(fwd / k) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        dff = self.df(rf, t)
        dfd = self.df(rd, t)

        if convention == DeltaConvention.SPOT_PREM_EXCLUDED:
            return dff * norm.cdf(d1) if is_call else -dff * norm.cdf(-d1)

        if convention == DeltaConvention.FWD_PREM_EXCLUDED:
            return norm.cdf(d1) if is_call else - norm.cdf(-d1)

        if convention == DeltaConvention.SPOT_PREM_INCLUDED:
            scale = dfd * (k / s)
            return scale * norm.cdf(d2) if is_call else -scale * norm.cdf(-d2)

        raise ValueError("Unknown delta convention.")




# Finite-difference Greeks ============================================================
MIN_SIGMA = 1e-8
MIN_SPOT = 1e-12
MIN_STEP = 1e-8
MAX_REFINEMENTS = 5
REL_TOL = 5e-4
ABS_TOL = 1e-10


def vega_fd(
    bs: GKBlackScholes,
    is_call: bool,
    s: float,
    k: float,
    t: float,
    rd: float,
    rf: float,
    sigma: float,
) -> float:
    safe_sigma = max(MIN_SIGMA, sigma)

    def by_sigma(x_value: float) -> float:
        return bs.price(is_call, s, k, t, rd, rf, x_value)

    h0 = max(5e-6, abs(safe_sigma) * 5e-3)
    return first_derivative_adaptive(by_sigma, safe_sigma, h0, MIN_SIGMA)


def volga_fd(
    bs: GKBlackScholes,
    is_call: bool,
    s: float,
    k: float,
    t: float,
    rd: float,
    rf: float,
    sigma: float,
) -> float:
    safe_sigma = max(MIN_SIGMA, sigma)

    def by_sigma(x_value: float) -> float:
        return bs.price(is_call, s, k, t, rd, rf, x_value)

    h0 = max(5e-6, abs(safe_sigma) * 5e-3)
    return second_derivative_adaptive(by_sigma, safe_sigma, h0, MIN_SIGMA)


def vanna_fd(
    bs: GKBlackScholes,
    is_call: bool,
    s: float,
    k: float,
    t: float,
    rd: float,
    rf: float,
    sigma: float,
) -> float:
    safe_spot = max(MIN_SPOT, s)

    def vega_by_spot(x_value: float) -> float:
        return vega_fd(bs, is_call, x_value, k, t, rd, rf, sigma)

    h_s = max(1e-6, abs(safe_spot) * 1e-4)
    return first_derivative_adaptive(vega_by_spot, safe_spot, h_s, MIN_SPOT)


def first_derivative_adaptive(
    f: Callable[[float], float],
    x_value: float,
    h0: float,
    lower_bound: float,
) -> float:
    h = bounded_step(x_value, h0, lower_bound)
    prev = first_derivative(f, x_value, h, lower_bound)
    prev_richardson = prev

    for _ in range(MAX_REFINEMENTS):
        h_next = bounded_step(x_value, h * 0.5, lower_bound)
        if h_next >= h:
            break
        curr = first_derivative(f, x_value, h_next, lower_bound)
        curr_richardson = richardson_extrapolate(prev, curr, order=2)
        if is_stable(prev_richardson, curr_richardson):
            return curr_richardson
        prev = curr
        prev_richardson = curr_richardson
        h = h_next

    return prev_richardson


def second_derivative_adaptive(
    f: Callable[[float], float],
    x_value: float,
    h0: float,
    lower_bound: float,
    ) -> float:

    h = bounded_step(x_value, h0, lower_bound)
    prev = second_derivative(f, x_value, h, lower_bound)
    prev_order = second_derivative_order(x_value, h, lower_bound)
    prev_richardson = prev

    for _ in range(MAX_REFINEMENTS):
        h_next = bounded_step(x_value, h * 0.5, lower_bound)
        if h_next >= h:
            break
        curr = second_derivative(f, x_value, h_next, lower_bound)
        curr_order = second_derivative_order(x_value, h_next, lower_bound)
        order = min(prev_order, curr_order)
        curr_richardson = richardson_extrapolate(prev, curr, order=order)
        if is_stable(prev_richardson, curr_richardson):
            return curr_richardson
        prev = curr
        prev_order = curr_order
        prev_richardson = curr_richardson
        h = h_next
    return prev_richardson


def richardson_extrapolate(derivative_h: float, derivative_h_half: float, order: int) -> float:
    factor = 2.0**order
    return (factor * derivative_h_half - derivative_h) / (factor - 1.0)


def first_derivative(
    f: Callable[[float], float],
    x_value: float,
    h: float,
    lower_bound: float,
) -> float:
    if x_value - h > lower_bound:
        return (f(x_value + h) - f(x_value - h)) / (2.0 * h)
    return (-3.0 * f(x_value) + 4.0 * f(x_value + h) - f(x_value + 2.0 * h)) / (2.0 * h)


def second_derivative(
    f: Callable[[float], float],
    x_value: float,
    h: float,
    lower_bound: float,
) -> float:
    if x_value - h > lower_bound:
        return (f(x_value + h) - 2.0 * f(x_value) + f(x_value - h)) / (h * h)
    return (f(x_value) - 2.0 * f(x_value + h) + f(x_value + 2.0 * h)) / (h * h)


def second_derivative_order(x_value: float, h: float, lower_bound: float) -> int:
    return 2 if x_value - h > lower_bound else 1


def bounded_step(x_value: float, h: float, lower_bound: float) -> float:
    candidate = max(MIN_STEP, h)
    if x_value > lower_bound:
        max_symmetric_step = 0.5 * (x_value - lower_bound)
        if max_symmetric_step > 0.0:
            candidate = min(candidate, max_symmetric_step)
    return max(MIN_STEP, candidate)


def is_stable(a_value: float, b_value: float) -> bool:
    scale = max(1.0, abs(a_value), abs(b_value))
    return abs(a_value - b_value) <= ABS_TOL + REL_TOL * scale



# Market data and delta-to-strike conversion ============================================================
@dataclass(frozen=True)
class SmileQuote:
    T: float
    sigma_atm: float
    rr25: float
    bf25: float

    @property
    def sigma_25p(self) -> float:
        return clamp_vol(self.sigma_atm + self.bf25 - 0.5 * self.rr25)

    @property
    def sigma_25c(self) -> float:
        return clamp_vol(self.sigma_atm + self.bf25 + 0.5 * self.rr25)


@dataclass(frozen=True)
class MarketSlice:
    s: float
    rd: float
    rf: float
    t: float
    sigma_atm: float
    sigma_25p: float
    sigma_25c: float
    k_atm: float
    k_25p: float
    k_25c: float


class MarketSliceBuilder:
    BRACKET_SCAN_STEPS = 240

    def __init__(
        self,
        bs: GKBlackScholes,
        root_finder: BisectionRootFinder,
        delta_convention: DeltaConvention,
    ) -> None:
        self.bs = bs
        self.root_finder = root_finder
        self.delta_convention = delta_convention

    def build(self, s: float, rd: float, rf: float, quote: SmileQuote) -> MarketSlice:
        forward = GKBlackScholes.forward(s, rd, rf, quote.T)
        k_atm = forward
        k_25c = self.strike_from_delta(s, rd, rf, quote.T, quote.sigma_25c, True, 0.25)
        k_25p = self.strike_from_delta(s, rd, rf, quote.T, quote.sigma_25p, False, -0.25)

        return MarketSlice(
            s=s,
            rd=rd,
            rf=rf,
            t=quote.T,
            sigma_atm=quote.sigma_atm,
            sigma_25p=quote.sigma_25p,
            sigma_25c=quote.sigma_25c,
            k_atm=k_atm,
            k_25p=k_25p,
            k_25c=k_25c,
        )

    def strike_from_delta(
        self,
        s: float,
        rd: float,
        rf: float,
        t: float,
        sigma: float,
        is_call: bool,
        target_delta: float,
    ) -> float:
        forward = GKBlackScholes.forward(s, rd, rf, t)

        def objective(k_value: float) -> float:
            return self.bs.delta(
                self.delta_convention,
                is_call,
                s,
                k_value,
                t,
                rd,
                rf,
                sigma,
            ) - target_delta

        lo, hi = self.scan_range(forward, is_call)
        bracket = self.find_bracket_by_scan(objective, lo, hi, target_delta)
        return self.root_finder.solve(objective, bracket[0], bracket[1])

    def scan_range(self, forward: float, is_call: bool) -> tuple[float, float]:
        min_k = 0.05 * forward
        max_k = 20.0 * forward

        if self.delta_convention == DeltaConvention.SPOT_PREM_INCLUDED:
            if is_call:
                return (max(forward, min_k), max_k)
            return (min_k, min(forward, max_k))

        return (min_k, max_k)

    def find_bracket_by_scan(
        self,
        f: Callable[[float], float],
        lo: float,
        hi: float,
        target_delta: float,
    ) -> tuple[float, float]:
        prev_k = lo
        prev_v = f(prev_k)

        if math.isnan(prev_v):
            raise ValueError(f"Delta inversion produced NaN at K={prev_k}")

        for i in range(1, self.BRACKET_SCAN_STEPS + 1):
            scan_t = i / self.BRACKET_SCAN_STEPS
            k_value = lo * math.pow(hi / lo, scan_t)
            value = f(k_value)

            if math.isnan(value):
                continue
            if prev_v == 0.0:
                return (prev_k, prev_k)
            if prev_v * value <= 0.0:
                return (prev_k, k_value)

            prev_k = k_value
            prev_v = value

        raise ValueError(
            "Could not bracket delta->strike root for "
            f"convention={self.delta_convention}, targetDelta={target_delta}, "
            f"strikeRange=[{lo}, {hi}]"
        )


def clamp_vol(value: float) -> float:
    return max(1e-6, min(3.0, value))



# Vanna-Volga pricer ============================================================
@dataclass
class SliceCache:
    atm_rr_bf_greek_matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    weights_by_strike: OrderedDict[int, tuple[float, float, float]]


class VannaVolgaPricer:
    MAX_STRIKE_CACHE_PER_SLICE = 2048

    def __init__(self, bs: GKBlackScholes, solver: GaussianElimination3) -> None:
        self.bs = bs
        self.solver = solver
        self.slice_caches: dict[MarketSlice, SliceCache] = {}

    def price_vanilla(self, market_slice: MarketSlice, is_call: bool, k: float) -> float:
        base = self.bs.price(
            is_call,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            market_slice.sigma_atm,
        )
        weights = self.weights_pillars(market_slice, k)

        p_25p = self.bs.price(
            is_call,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            market_slice.sigma_25p,
        )
        p_atm = self.bs.price(
            is_call,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            market_slice.sigma_atm,
        )
        p_25c = self.bs.price(
            is_call,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            market_slice.sigma_25c,
        )

        return base + weights[0] * (p_25p - p_atm) + weights[2] * (p_25c - p_atm)

    def price_digital_call(self, market_slice: MarketSlice, k: float) -> float:
        eps = strike_eps(k)
        c_dn = self.price_vanilla(market_slice, True, k - eps)
        c_up = self.price_vanilla(market_slice, True, k + eps)
        return (c_dn - c_up) / (2.0 * eps)

    def price_digital_put(self, market_slice: MarketSlice, k: float) -> float:
        eps = strike_eps(k)
        p_dn = self.price_vanilla(market_slice, False, k - eps)
        p_up = self.price_vanilla(market_slice, False, k + eps)
        return (p_up - p_dn) / (2.0 * eps)

    def weights_atm_rr_bf(self, market_slice: MarketSlice, k_target: float) -> tuple[float, float, float]:
        slice_cache = self.get_or_build_slice_cache(market_slice)
        target_greeks = self.greek_vector(market_slice, k_target, market_slice.sigma_atm)
        return self.solver.solve(slice_cache.atm_rr_bf_greek_matrix, target_greeks)

    def weights_pillars(self, market_slice: MarketSlice, k_target: float) -> tuple[float, float, float]:
        slice_cache = self.get_or_build_slice_cache(market_slice)
        key = strike_key(k_target)
        cached = slice_cache.weights_by_strike.get(key)
        if cached is not None:
            slice_cache.weights_by_strike.move_to_end(key)
            return cached

        weights = rr_bf_to_pillar(self.weights_atm_rr_bf(market_slice, k_target))
        slice_cache.weights_by_strike[key] = weights
        if len(slice_cache.weights_by_strike) > self.MAX_STRIKE_CACHE_PER_SLICE:
            slice_cache.weights_by_strike.popitem(last=False)
        return weights

    def get_or_build_slice_cache(self, market_slice: MarketSlice) -> SliceCache:
        cached = self.slice_caches.get(market_slice)
        if cached is not None:
            return cached

        built = self.build_slice_cache(market_slice)
        self.slice_caches[market_slice] = built
        return built

    def build_slice_cache(self, market_slice: MarketSlice) -> SliceCache:
        sigma = market_slice.sigma_atm
        greek_25p = self.greek_vector(market_slice, market_slice.k_25p, sigma)
        greek_atm = self.greek_vector(market_slice, market_slice.k_atm, sigma)
        greek_25c = self.greek_vector(market_slice, market_slice.k_25c, sigma)

        greek_rr = (
            greek_25c[0] - greek_25p[0],
            greek_25c[1] - greek_25p[1],
            greek_25c[2] - greek_25p[2],
        )
        greek_bf = (
            0.5 * (greek_25c[0] + greek_25p[0]) - greek_atm[0],
            0.5 * (greek_25c[1] + greek_25p[1]) - greek_atm[1],
            0.5 * (greek_25c[2] + greek_25p[2]) - greek_atm[2],
        )

        matrix = (
            (greek_atm[0], greek_rr[0], greek_bf[0]),
            (greek_atm[1], greek_rr[1], greek_bf[1]),
            (greek_atm[2], greek_rr[2], greek_bf[2]),
        )
        return SliceCache(matrix, OrderedDict())

    def greek_vector(self, market_slice: MarketSlice, k: float, sigma: float) -> tuple[float, float, float]:
        is_call_for_greeks = True
        vega = vega_fd(
            self.bs,
            is_call_for_greeks,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            sigma,
        )
        vanna = vanna_fd(
            self.bs,
            is_call_for_greeks,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            sigma,
        )
        volga = volga_fd(
            self.bs,
            is_call_for_greeks,
            market_slice.s,
            k,
            market_slice.t,
            market_slice.rd,
            market_slice.rf,
            sigma,
        )
        return (vega, vanna, volga)


def rr_bf_to_pillar(weights_atm_rr_bf: tuple[float, float, float]) -> tuple[float, float, float]:
    w_atm, w_rr, w_bf = weights_atm_rr_bf
    w_25p = -w_rr + 0.5 * w_bf
    w_atm_pillar = w_atm - w_bf
    w_25c = w_rr + 0.5 * w_bf
    return (w_25p, w_atm_pillar, w_25c)


def strike_key(k: float) -> int:
    return round(k * 1e8)


def strike_eps(k: float) -> float:
    return max(1e-6, k * 1e-4)


# Plots
def implied_vol_from_price(
    bs: GKBlackScholes,
    root_finder: BisectionRootFinder,
    target_price: float,
    is_call: bool,
    s: float,
    k: float,
    t: float,
    rd: float,
    rf: float,
    vol_low: float = 1e-6,
    vol_high: float = 3.0,
) -> float:

    def objective(sigma: float) -> float:
        return bs.price(is_call, s, k, t, rd, rf, sigma) - target_price

    price_low = objective(vol_low)
    price_high = objective(vol_high)

    if math.isnan(price_low) or math.isnan(price_high):
        raise ValueError("Implied vol objective returned NaN.")

    if price_low * price_high > 0.0:
        raise ValueError(
            f"Could not bracket implied vol for K={k:.6f}, "
            f"target_price={target_price:.8f}."
        )

    return root_finder.solve(objective, vol_low, vol_high)


def plot_vv_smile(
    bs: GKBlackScholes,
    root_finder: BisectionRootFinder,
    pricer: VannaVolgaPricer,
    market_slice: MarketSlice,
    n_points: int = 80,
) -> None:
    
    k_min = market_slice.k_25p
    k_max = market_slice.k_25c

    strikes = [
        k_min + i * (k_max - k_min) / (n_points - 1)
        for i in range(n_points)
    ]

    implied_vols = []

    for k in strikes:
        vv_price = pricer.price_vanilla(market_slice, True, k)

        try:
            iv = implied_vol_from_price(
                bs=bs,
                root_finder=root_finder,
                target_price=vv_price,
                is_call=True,
                s=market_slice.s,
                k=k,
                t=market_slice.t,
                rd=market_slice.rd,
                rf=market_slice.rf,
            )
            implied_vols.append(iv)
        except ValueError:
            implied_vols.append(float("nan"))

    pillar_strikes = [
        market_slice.k_25p,
        market_slice.k_atm,
        market_slice.k_25c,
    ]

    pillar_vols = [
        market_slice.sigma_25p,
        market_slice.sigma_atm,
        market_slice.sigma_25c,
    ]

    plt.figure(figsize=(10, 6))

    plt.plot(strikes, implied_vols, label="Vanna-Volga implied smile")
    plt.scatter(pillar_strikes, pillar_vols, label="Market pillars")

    plt.xlabel("Strike")
    plt.ylabel("Implied volatility")
    plt.title("Vanna-Volga Reconstructed FX Volatility Smile")
    plt.grid(True)
    plt.legend()


def plot_vv_vol_surface(
    bs: GKBlackScholes,
    root_finder: BisectionRootFinder,
    pricer: VannaVolgaPricer,
    builder: MarketSliceBuilder,
    s: float,
    rd: float,
    rf: float,
    quotes: list[SmileQuote],
    n_strikes: int = 60,
) -> None:
    """
    For each maturity:
        1. Build MarketSlice from ATM/RR/BF quotes.
        2. Generate strikes between K_25P and K_25C.
        3. Price VV vanilla options.
        4. Invert GK Black-Scholes to recover implied vol.
        5. Plot sigma(K,T).
    """

    market_slices = [
        builder.build(s=s, rd=rd, rf=rf, quote=quote)
        for quote in quotes
    ]

    # Use a common strike grid across all maturities
    global_k_min = min(ms.k_25p for ms in market_slices)
    global_k_max = max(ms.k_25c for ms in market_slices)

    strikes = np.linspace(global_k_min, global_k_max, n_strikes)
    maturities = np.array([ms.t for ms in market_slices])

    vol_surface = np.full((len(market_slices), n_strikes), np.nan)

    for i, market_slice in enumerate(market_slices):
        for j, k in enumerate(strikes):
            # Use OTM convention for better numerical inversion:
            # put below ATM/forward, call above ATM/forward.
            is_call = k >= market_slice.k_atm

            try:
                vv_price = pricer.price_vanilla(
                    market_slice=market_slice,
                    is_call=is_call,
                    k=float(k),
                )

                implied_vol = implied_vol_from_price(
                    bs=bs,
                    root_finder=root_finder,
                    target_price=vv_price,
                    is_call=is_call,
                    s=market_slice.s,
                    k=float(k),
                    t=market_slice.t,
                    rd=market_slice.rd,
                    rf=market_slice.rf,
                )

                vol_surface[i, j] = implied_vol

            except ValueError:
                vol_surface[i, j] = np.nan

    K_grid, T_grid = np.meshgrid(strikes, maturities)

    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot_surface(K_grid, T_grid, vol_surface, alpha=0.85)

    ax.set_xlabel("Strike")
    ax.set_ylabel("Maturity")
    ax.set_zlabel("Implied volatility")
    ax.set_title("Vanna-Volga FX Implied Volatility Surface")



# TEST ============================================================
def run_demo(convention: DeltaConvention) -> None:
    s = 1.0850
    rd = 0.03
    rf = 0.02
    t = 0.5

    sigma_atm = 0.10
    rr25 = -0.02
    bf25 = 0.01

    bs = GKBlackScholes()
    root_finder = BisectionRootFinder()
    solver = GaussianElimination3()

    builder = MarketSliceBuilder(bs, root_finder, convention)
    market_slice = builder.build(s, rd, rf, SmileQuote(t, sigma_atm, rr25, bf25))
    pricer = VannaVolgaPricer(bs, solver)


    quotes_surface = [
    SmileQuote(T=0.25, sigma_atm=0.095, rr25=-0.012, bf25=0.006),
    SmileQuote(T=0.50, sigma_atm=0.100, rr25=-0.020, bf25=0.010),
    SmileQuote(T=1.00, sigma_atm=0.105, rr25=-0.018, bf25=0.012),
    SmileQuote(T=2.00, sigma_atm=0.110, rr25=-0.014, bf25=0.014),
    ]

    plot_vv_vol_surface(
        bs=bs,
        root_finder=root_finder,
        pricer=pricer,
        builder=builder,
        s=s,
        rd=rd,
        rf=rf,
        quotes=quotes_surface,
    )


    print(f"Delta convention: {convention}")
    print(f"MarketSlice(T={market_slice.t:.4f})")
    print(f"S={market_slice.s:.6f} rd={market_slice.rd:.4f} rf={market_slice.rf:.4f}")
    print(
        f"sigmaATM={market_slice.sigma_atm:.4f} "
        f"sigma25P={market_slice.sigma_25p:.4f} "
        f"sigma25C={market_slice.sigma_25c:.4f}"
    )
    print(
        f"K_ATM={market_slice.k_atm:.6f} "
        f"K_25P={market_slice.k_25p:.6f} "
        f"K_25C={market_slice.k_25c:.6f}"
    )
    print()

    k = 1.10
    weights_base = pricer.weights_atm_rr_bf(market_slice, k)
    weights_pillars = pricer.weights_pillars(market_slice, k)
    print(
        f"VV weights base @K={k:.4f} -> "
        f"wATM={weights_base[0]:+.8f} "
        f"wRR={weights_base[1]:+.8f} "
        f"wBF={weights_base[2]:+.8f}"
    )
    print(
        f"VV weights pillars @K={k:.4f} -> "
        f"w25P={weights_pillars[0]:+.8f} "
        f"wATM={weights_pillars[1]:+.8f} "
        f"w25C={weights_pillars[2]:+.8f}"
    )
    print()

    gk_call = bs.price(True, market_slice.s, k, market_slice.t, market_slice.rd, market_slice.rf, market_slice.sigma_atm)
    gk_put = bs.price(False, market_slice.s, k, market_slice.t, market_slice.rd, market_slice.rf, market_slice.sigma_atm)
    print(f"GKBS Call (K={k:.4f}, sigma=ATM {100.0 * market_slice.sigma_atm:.2f}%): {gk_call:.8f}")
    print(f"GKBS Put  (K={k:.4f}, sigma=ATM {100.0 * market_slice.sigma_atm:.2f}%): {gk_put:.8f}")
    print()

    vv_call = pricer.price_vanilla(market_slice, True, k)
    vv_put = pricer.price_vanilla(market_slice, False, k)
    digital_call = pricer.price_digital_call(market_slice, k)
    digital_put = pricer.price_digital_put(market_slice, k)
    print(f"VV Call (K={k:.4f}): {vv_call:.8f}")
    print(f"VV Put  (K={k:.4f}): {vv_put:.8f}")
    print(f"VV Digital Call (K={k:.4f}): {digital_call:.8f}")
    print(f"VV Digital Put  (K={k:.4f}): {digital_put:.8f}")
    
    plot_vv_smile(
    bs=bs,
    root_finder=root_finder,
    pricer=pricer,
    market_slice=market_slice,
    )

    plt.show()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    convention = DeltaConvention.parse(args[0] if args else None)
    run_demo(convention)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

