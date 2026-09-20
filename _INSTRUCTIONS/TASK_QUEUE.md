# Task queue

Allowed states: `READY`, `PENDING`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

Only the first `READY` milestone may be selected. After completing it, mark the
next milestone `READY` only if all dependencies are `DONE`.

## M01 — Baseline characterization

- State: IN_PROGRESS
- Dependencies: none
- Goal: freeze current Python/C++ behavior before extending the system.
- Work:
  - document current public APIs and numerical conventions;
  - add missing build smoke tests and deterministic regression fixtures;
  - capture existing VV prices, strikes, weights, and digital outputs;
  - add one end-to-end baseline command.
- Acceptance:
  - clean build and current tests pass;
  - fixtures include tolerances and provenance;
  - no intentional pricing change.
- Commit: `test(baseline): freeze existing VV pricing behavior`

## M02 — Multi-tenor market contracts

- State: PENDING
- Dependencies: M01
- Goal: represent a term structure of FX ATM/RR/BF quotes and conventions.
- Acceptance:
  - validated immutable data objects;
  - sorted unique maturities;
  - explicit domestic/foreign rates and delta conventions;
  - unit tests for invalid and valid inputs.
- Commit: `feat(market): add multi-tenor FX quote contracts`

## M03 — Reusable VV smile sampler

- State: PENDING
- Dependencies: M02
- Goal: reconstruct a complete VV smile per tenor and sample its reliable region
  for subsequent SSVI projection.
- Acceptance:
  - batch API returns strikes, vols, forwards, total variances, and provenance;
  - sampling grid includes the original liquid pillars and documents its wing cutoffs;
  - liquid pillars remain distinguishable from synthetic VV smile samples;
  - single-slice regression results remain unchanged.
- Commit: `feat(vv): build multi-tenor smile sampler`

## M04 — SSVI kernel and parameters

- State: PENDING
- Dependencies: M03
- Goal: implement vectorized SSVI total variance and a documented phi family.
- Acceptance:
  - correct scalar and array behavior;
  - positive total variance on admissible fixtures;
  - analytic/numerical limit tests at ATM and symmetric cases;
  - no optimizer yet.
- Commit: `feat(surface): implement SSVI total variance kernel`

## M05 — SSVI no-arbitrage constraints

- State: PENDING
- Dependencies: M04
- Goal: encode admissibility, butterfly, calendar, and wing diagnostics.
- Acceptance:
  - constraints are executable and cited in documentation;
  - positive and deliberately invalid fixtures;
  - dense-grid call-price monotonicity/convexity checks;
  - constraint slack included in result objects.
- Commit: `feat(surface): enforce SSVI arbitrage constraints`

## M06 — Global SSVI calibration

- State: PENDING
- Dependencies: M05
- Goal: project the sampled VV smiles onto one constrained SSVI surface across
  all tenors in total-variance space.
- Acceptance:
  - objective fits sampled VV total variances across tenors;
  - original liquid pillars have high priority and synthetic weights are
    normalized so sampling density does not increase their total influence;
  - unreliable extreme wings are excluded or strongly downweighted;
  - deterministic multistart or documented initialization;
  - calibration result records parameters, objective, pillar and VV-grid
    residuals, no-arbitrage status, and optimizer status;
  - recovery test on synthetic SSVI data.
- Commit: `feat(surface): add constrained global SSVI calibration`

## M07 — GK target price grid

- State: PENDING
- Dependencies: M06
- Goal: convert SSVI total variance to weighted vanilla targets.
- Acceptance:
  - each point stores strike, maturity, IV, price, vega, and weight;
  - put-call parity and no-arbitrage price bounds pass;
  - liquid and synthetic provenance retained.
- Commit: `feat(calibration): build SSVI vanilla target grid`

## M08 — C++ Heston characteristic function

- State: PENDING
- Dependencies: M07
- Goal: implement a stable risk-neutral FX Heston characteristic function.
- Acceptance:
  - branch convention documented;
  - finite values across an admissible parameter grid;
  - symmetry/normalization and constant-variance limit tests;
  - no Python loop around characteristic evaluations.
- Commit: `feat(cpp): implement Heston characteristic function`

## M09 — C++ Fourier/FFT vanilla pricer

- State: PENDING
- Dependencies: M08
- Goal: price a log-strike grid in batches and interpolate to requested strikes.
- Acceptance:
  - damping and grid configuration explicit;
  - put-call parity;
  - agreement with an independent quadrature/COS reference;
  - quantified FFT interpolation and truncation error.
- Commit: `feat(cpp): add batched Heston Fourier pricer`

## M10 — Python bindings for Heston prices

- State: PENDING
- Dependencies: M09
- Goal: expose a coarse-grained batch price API through pybind11.
- Acceptance:
  - parameter and array validation at the boundary;
  - predictable exception translation;
  - Python integration and shape tests;
  - no per-strike Python-to-C++ calls in normal usage.
- Commit: `feat(bindings): expose batched Heston pricing`

## M11 — Heston calibration engine

- State: PENDING
- Dependencies: M10
- Goal: calibrate `(v0,kappa,theta,xi,rho)` to the SSVI/GK target prices.
- Acceptance:
  - admissible transforms or bounds;
  - weighted price residuals with optional vega normalization;
  - deterministic restarts and failure reporting;
  - synthetic parameter-recovery test with realistic tolerance.
- Commit: `feat(heston): calibrate model to SSVI target prices`

## M12 — Calibration diagnostics

- State: PENDING
- Dependencies: M11
- Goal: make model mismatch and stability visible.
- Acceptance:
  - price and IV residual reports by tenor/moneyness;
  - Feller status reported, not silently imposed;
  - parameter/bound activity and objective decomposition;
  - reproducible calibration fixture and plots.
- Commit: `feat(reporting): add Heston calibration diagnostics`

## M13 — C++ Heston Monte Carlo engine

- State: PENDING
- Dependencies: M12
- Goal: simulate spot and non-negative variance efficiently in C++.
- Acceptance:
  - documented scheme, initially Andersen QE or QE-M;
  - deterministic seeded results and antithetic option;
  - variance non-negativity policy tested;
  - MC vanilla agrees with Fourier price within confidence tolerance;
  - convergence/runtime benchmark included.
- Commit: `feat(cpp): implement Heston QE Monte Carlo engine`

## M14 — C++ double-no-touch pricer

- State: PENDING
- Dependencies: M13
- Goal: price a cash-or-nothing FX DNT with explicit monitoring convention.
- Acceptance:
  - discrete monitoring implemented first;
  - continuous correction implemented or clearly feature-gated;
  - price, SE, CI, barrier hit statistics, and settings returned;
  - payoff bounds, barrier monotonicity, constant-volatility, and step convergence tests;
  - Python invokes one coarse-grained C++ call.
- Commit: `feat(exotics): add C++ Heston double-no-touch pricer`

## M15 — End-to-end release and benchmark

- State: PENDING
- Dependencies: M14
- Goal: provide a reproducible research-quality workflow and release candidate.
- Acceptance:
  - one documented command runs quote→VV→SSVI→Heston→DNT;
  - CI builds/tests Python and C++;
  - README explains data provenance, assumptions, and limitations;
  - calibration and MC benchmarks stored in a compact report;
  - version metadata prepared for `v0.2.0` without creating the tag.
- Commit: `docs(release): publish end-to-end DNT workflow`
