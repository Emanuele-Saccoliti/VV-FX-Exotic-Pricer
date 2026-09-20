# Project specification

## Objective

Build a research-grade but compact FX exotic-pricing pipeline on top of the
existing Vanna–Volga repository. The deliverable is a calibrated Heston model and
a C++ Monte Carlo pricer for a cash-or-nothing double-no-touch option.

## Market inputs

For each maturity `T`:

- spot `S0`;
- domestic and foreign rates or discount factors;
- ATM implied volatility;
- 25-delta risk reversal;
- 25-delta butterfly;
- delta convention and ATM convention;
- optional bid/ask spreads.

The first production-quality surface requires at least three maturities. Example
fixtures may use synthetic but economically plausible EUR/USD data.

## Pipeline contracts

### 1. Vanna–Volga

The existing implementation reconstructs `25P`, `ATM`, and `25C` pillar
volatilities and their strikes, and evaluates a complete smile for each tenor.
Sample that smile on a documented, finite strike or forward-log-moneyness grid
covering the reliable VV region. Include the three original pillars explicitly.
The sampled VV smile is the calibration input to SSVI, not merely an optimizer
initializer or a benchmark. Its non-pillar points are synthetic observations
derived from the same ATM/RR/BF quotes, not independent traded quotes.

### 2. SSVI

For forward log-moneyness `k` and ATM total variance `theta(T)`, implement:

```text
w(k, theta) = theta/2 * [1 + rho*phi(theta)*k
                 + sqrt((phi(theta)*k + rho)^2 + 1 - rho^2)]
```

Use one documented `phi(theta)` family initially. Parameter domains and
sufficient butterfly/calendar no-arbitrage conditions must be encoded and tested,
not only described. `theta(T)` must be positive and non-decreasing.

For each VV sample, set `k_ij = log(K_ij/F_Tj)` and
`w_VV(k_ij,T_j) = sigma_VV(K_ij,T_j)^2 T_j`. Calibrate one constrained SSVI
surface across tenors by minimizing

```text
sum_j sum_i weight_ij * [w_SSVI(k_ij,T_j) - w_VV(k_ij,T_j)]^2
```

Record the grid and weights. Give the original `25P`, `ATM`, and `25C` pillars
high priority, positive but lower total influence to the remaining VV smile
samples, and zero or sharply reduced weight to extreme wings where VV is
unreliable. Normalize synthetic weights so denser sampling cannot manufacture
more market evidence. Use bid/ask information for the liquid pillars where
available. An exact pillar fit is a goal only when feasible under the selected
SSVI family and no-arbitrage constraints; otherwise report the residuals.

Calibration priorities:

1. project the reconstructed VV smiles across maturities onto SSVI;
2. protect the liquid pillars and remain inside their bid/ask when feasible;
3. limit the influence of synthetic VV samples and exclude unreliable wings;
4. enforce static no-arbitrage conditions and report constraint slack and wing slopes.

Outputs:

- calibrated parameters;
- `w(k,T)` and `sigma(k,T) = sqrt(w/T)`;
- pillar residuals in volatility and price units;
- VV-to-SSVI residuals on the documented fitting grid;
- no-arbitrage diagnostics.

### 3. Target vanilla prices

For each calibration point:

```text
P_target(K,T) = GK(S0,K,T,rd,rf,sigma_SSVI(K,T))
```

Store price, implied volatility, vega, liquidity weight, and provenance.

### 4. Heston calibration

Under the domestic risk-neutral measure:

```text
dS_t = (rd-rf) S_t dt + sqrt(v_t) S_t dW^S_t
dv_t = kappa(theta-v_t) dt + xi sqrt(v_t) dW^v_t
d<W^S,W^v>_t = rho dt
```

Calibrate one global parameter vector initially. The objective is a weighted
price residual, optionally normalized by GK vega or bid/ask:

```text
min sum_i weight_i * (P_Heston_i - P_target_i)^2
```

The primary vanilla engine is a C++ Fourier/FFT implementation. Because FFT uses
a regular log-strike grid, interpolation errors at market strikes must be
measured. An independent quadrature or COS reference is required for validation.

### 5. Double-no-touch

Initial contract:

```text
payout = notional if L < S_t < U for all monitored t in [0,T], else 0
```

Required inputs:

- lower barrier `L`, upper barrier `U`;
- maturity, notional, monitoring convention;
- domestic/foreign rates;
- calibrated Heston parameters;
- paths, time steps, seed.

Required outputs:

- discounted price;
- standard error and 95% confidence interval;
- hit probabilities by barrier when available;
- numerical settings and runtime.

Version 1 supports discrete monitoring. Version 2 adds a documented continuous-
monitoring correction based on a conditional bridge approximation and validates
the constant-volatility limit.

## Non-goals for the first release

- local-stochastic volatility;
- stochastic rates;
- jumps or rough volatility;
- GPU implementation;
- production Bloomberg connectivity;
- automatic trading or live risk;
- SANOS/CVI comparison;
- full XVA or portfolio netting.

## Release definition

Release `v0.2.0` is ready when a clean clone can build the extension, reproduce
SSVI and Heston calibration diagnostics, and price the sample DNT with stable
confidence intervals through one documented command.
