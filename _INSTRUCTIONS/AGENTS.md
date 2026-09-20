# AGENTS.md

## Mission

Extend the existing hybrid Python/C++ FX pricer into a reproducible pipeline:

```text
Vanna–Volga → constrained SSVI → Heston Fourier calibration → C++ Heston MC → DNT
```

Preserve the existing public API unless a roadmap item explicitly changes it.
Keep Python as the orchestration and calibration layer. Keep numerically hot,
repeated kernels in C++ and expose them through the existing pybind11 boundary.

## Required reading at the start of every run

Read, in order:

1. `PROJECT_SPEC.md`
2. `ARCHITECTURE.md`
3. `DECISIONS.md`
4. `STATE.md`
5. `TASK_QUEUE.md`
6. the files and tests referenced by the selected milestone

Inspect `git status`, the current branch, recent commits, and the existing test
suite before editing. Existing uncommitted user changes must be preserved.

## One-run contract

- Select only the first milestone marked `READY` whose dependencies are `DONE`.
- Change its state to `IN_PROGRESS` before implementation.
- Work only on that milestone and defects directly blocking it.
- If the task is larger than one safe run, complete one coherent vertical slice,
  record the remaining work in `STATE.md`, and do not mark it `DONE`.
- Never silently expand scope or refactor unrelated modules.
- Do not implement later milestones early.

## Git contract

- Never commit or push directly to `main` or `master`.
- Use a branch named `<task-id>-<short-slug>` (for example,
  `M01-baseline`), without a `codex/` prefix.
- Reuse the existing milestone branch if the task remains `IN_PROGRESS`.
- Commit only after the relevant test gate passes.
- Use the exact Conventional Commit suggestion in `TASK_QUEUE.md`, adjusted only
  when the completed vertical slice is narrower.
- Push the task branch after a successful commit.
- Never merge, force-push, rewrite history, delete branches, or tag a release.
- If authentication or branch protection blocks the push, keep the local commit
  and record the blocker in `STATE.md`.

## Engineering boundaries

### Python owns

- FX quote ingestion and validation;
- delta/strike and market conventions;
- the existing Vanna–Volga orchestration;
- SSVI parameterization, constraints, and calibration;
- GK conversion of SSVI IVs into vanilla target prices;
- Heston optimization and diagnostics;
- plots, CLI, configuration, and reporting.

### C++ owns

- Heston characteristic function;
- batched Fourier/FFT vanilla pricing;
- Heston path simulation;
- DNT path-state evaluation and payoff aggregation;
- standard error and Monte Carlo statistics;
- pybind11 bindings for batch-oriented calls.

Do not cross the Python/C++ boundary per path, time step, strike, or optimizer
residual. Bind coarse-grained batch operations.

## Quantitative rules

- All rates, maturities, and volatilities use explicit units and validated domains.
- The domestic risk-neutral drift is `r_d - r_f`.
- SSVI works with forward log-moneyness `k = log(K/F_T)` and total variance
  `w(k,T) = sigma_impl(k,T)^2 T`.
- Build a complete VV smile for each tenor and calibrate SSVI to sampled VV
  total variances. Preserve the original liquid pillars as distinct high-priority
  observations; normalize synthetic sample weights and suppress unreliable wings.
- Check the fitted surface against the encoded static no-arbitrage conditions;
  report any remaining VV-to-SSVI and pillar residuals.
- The market calibration target is the GK price generated from the constrained
  SSVI surface, not an SSVI parameter passed into Heston.
- Heston calibration returns `(v0, kappa, theta, xi, rho)` with positivity and
  correlation constraints enforced through parameter transforms or explicit
  bounds.
- Do not impose the Feller condition silently. Make it an optional policy and
  report whether it holds.
- DNT monitoring convention must be explicit: discrete or continuous-corrected.
- A continuous-monitoring correction must document its approximation under
  stochastic volatility and be tested against the constant-volatility limit.
- Every Monte Carlo result reports seed, paths, steps, price, standard error, and
  95% confidence interval.

## Validation hierarchy

Every quantitative implementation requires, where applicable:

1. domain and invariant tests;
2. known-limit tests;
3. independent reference comparison;
4. convergence tests;
5. regression fixtures with documented tolerances.

Examples:

- flat SSVI/VV surface versus GK;
- put-call parity for Heston vanilla prices;
- Heston approaching constant variance versus GK;
- MC vanilla versus Fourier Heston within a confidence-based tolerance;
- DNT bounds: `0 ≤ price ≤ discounted payout`;
- monotonicity in lower/upper barrier distance;
- time-step convergence for barrier monitoring.

Tests must use deterministic seeds. Never weaken tolerances merely to make a test
pass; explain and justify any tolerance change.

## Completion gate

A milestone is `DONE` only when:

- implementation and tests satisfy every acceptance criterion;
- formatting/static checks relevant to changed files pass;
- public interfaces and numerical conventions are documented;
- `STATE.md` contains results, commands, limitations, and next task;
- `TASK_QUEUE.md` is updated;
- the task branch is committed and pushed.

If any gate fails, leave the milestone `IN_PROGRESS` or mark it `BLOCKED`; do not
produce an empty or knowingly broken commit.

## Reporting

At the end of a run report:

- branch and commit SHA;
- files changed;
- tests executed and their results;
- numerical evidence produced;
- remaining limitations or blockers;
- next ready milestone.
