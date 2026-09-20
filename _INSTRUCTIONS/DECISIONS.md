# Architecture decision log

## ADR-001 — Preserve the hybrid Python/C++ architecture

- Status: accepted
- Decision: Python owns orchestration and optimization; C++ owns repeated
  numerical kernels and Monte Carlo loops.
- Reason: calibration and reporting benefit from Python flexibility, while path
  simulation and batched Fourier pricing justify native performance.

## ADR-002 — Use SSVI between VV and Heston

- Status: accepted
- Decision: reconstruct a full VV smile for every tenor, then project sampled
  VV total variances onto one constrained SSVI surface. SSVI is a static target
  surface, not part of the Heston dynamics.
- Reason: VV transfers liquid FX quote conventions into a complete smile; SSVI
  provides smooth strike and tenor interpolation, controlled wings, and explicit
  static no-arbitrage constraints before Heston calibration.
- Guardrail: VV samples are correlated synthetic observations derived from the
  same quotes. The original ATM/25P/25C pillars have higher priority; synthetic
  weights are normalized across the grid, and unreliable extreme wings are
  excluded or strongly downweighted. Report pillar errors if exact preservation
  conflicts with SSVI admissibility.

## ADR-003 — Calibrate Heston in price space

- Status: accepted
- Decision: compare Heston Fourier prices with GK prices generated from SSVI IVs.
- Reason: avoids an implied-vol inversion inside every residual evaluation and
  gives a direct pricing error. Vega/bid-ask normalization may be added.

## ADR-004 — Use Fourier pricing for calibration and MC for exotics

- Status: accepted
- Decision: the vanilla calibration engine uses a characteristic-function method;
  MC is reserved for the path-dependent payoff and validation.
- Reason: a Monte Carlo optimizer objective would be slow and noisy.

## ADR-005 — First exotic is a double-no-touch

- Status: accepted
- Decision: implement a cash-or-nothing DNT, discrete monitoring first.
- Reason: it is recognizably FX-native and exercises the path engine and barrier
  state while remaining compact.

## ADR-006 — Codex pushes task branches but never merges

- Status: accepted
- Decision: each milestone uses `<id>-<slug>` without a `codex/` prefix and is
  pushed after tests.
- Reason: preserves autonomous progress while keeping final integration under
  human control.
