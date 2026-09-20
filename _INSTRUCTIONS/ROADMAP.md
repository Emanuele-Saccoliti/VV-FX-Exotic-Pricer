# Roadmap

## Phase A — Preserve and generalize the market layer

- M01 freezes the current numerical behavior and build.
- M02 introduces multi-tenor market data contracts.
- M03 turns the existing VV implementation into a reusable full-smile sampler
  with original pillars identified separately from synthetic points.

Exit condition: VV smiles and their documented fitting grids can be generated
reproducibly for several maturities without breaking existing APIs.

## Phase B — Build the constrained SSVI surface

- M04 implements the SSVI kernel and parameter objects.
- M05 implements explicit no-arbitrage constraints and diagnostics.
- M06 projects sampled VV total variances onto one globally constrained SSVI
  surface, with liquid pillar priority and limited synthetic weight.
- M07 produces the weighted GK target grid.

Exit condition: the project reports VV-grid and original-pillar fit errors,
wing behavior, and constraint slack on a multi-tenor fixture.

## Phase C — Calibrate Heston with Fourier pricing

- M08 implements the C++ Heston characteristic function.
- M09 implements and validates batched Fourier/FFT vanilla pricing.
- M10 exposes the batch engine through pybind11.
- M11 implements constrained Heston calibration.
- M12 adds calibration diagnostics and reproducibility fixtures.

Exit condition: Heston reprices the chosen SSVI target grid within documented
tolerances, and the remaining model mismatch is visible rather than hidden.

## Phase D — Price a double-no-touch in C++

- M13 implements the Heston path simulator.
- M14 implements DNT payoff, monitoring, and Monte Carlo statistics.
- M15 integrates, benchmarks, documents, and releases the end-to-end demo.

Exit condition: one command builds the project and produces the surface fit,
Heston fit, DNT price, confidence interval, and convergence diagnostics.
