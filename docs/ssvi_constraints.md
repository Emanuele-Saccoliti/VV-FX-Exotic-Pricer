# SSVI no-arbitrage constraints

## Scope and source

The implementation in `vv_pricer.surface.constraints` applies the sufficient
static no-arbitrage conditions in Theorems 4.1 and 4.2 of Jim Gatheral and
Antoine Jacquier, [“Arbitrage-free SVI volatility
surfaces”](https://arxiv.org/abs/1204.0646), *Quantitative Finance* 14(1),
2014. The model uses forward log-moneyness `k = log(K/F)` and the power-law
shape function

```text
phi(theta) = eta * theta**(-gamma).
```

This layer diagnoses a supplied term structure. It does not calibrate `theta`,
`rho`, `eta`, or `gamma`; calibration starts in M06.

## Executable conditions

For positive, strictly increasing maturities, the ATM total-variance knots must
be non-decreasing. The result records each consecutive calendar slack as

```text
[theta(T_i) - theta(T_{i-1})] / [T_i - T_{i-1}] >= 0.
```

The power-law shape derivative satisfies

```text
partial_theta[theta * phi(theta)] / phi(theta) = 1 - gamma.
```

The result records its lower and upper slacks against Theorem 4.1. The upper
bound is infinite when `rho = 0`.

For every supplied `theta`, Theorem 4.2 is encoded as

```text
4 - theta * phi(theta) * (1 + abs(rho)) > 0
4 - theta * phi(theta)**2 * (1 + abs(rho)) >= 0.
```

The asymptotic total-variance slopes are also returned:

```text
left  = theta * phi(theta) * (1 - rho) / 2
right = theta * phi(theta) * (1 + rho) / 2.
```

The strict first butterfly inequality makes both slopes strictly less than the
Lee bound of 2. `SsviArbitrageDiagnostics.constraint_slacks` exposes the named
analytic margins, and `minimum_constraint_slack` gives their minimum.

## Independent finite-grid check

For every slice, a configurable grid defaults to 2,001 points over
`-2 <= k <= 2`. It builds normalized undiscounted Black call prices with
forward 1 and strike `exp(k)`. It then checks:

- non-increasing call prices as strike increases;
- non-decreasing call secant slopes as strike increases, which is the discrete
  convexity condition on the non-uniform strike grid;
- intrinsic lower bounds and the normalized upper bound of 1.

The default absolute numerical tolerance is `1e-10`. These finite-grid checks
are regression diagnostics, not a replacement for the analytic all-strike
sufficient conditions.

## Validation evidence

The deterministic tests include:

- an admissible four-tenor term structure with positive analytic slack and
  monotone, convex, bounded dense-grid calls;
- a flat ATM total-variance interval, accepted at zero calendar slack;
- a decreasing ATM total-variance fixture rejected as calendar arbitrage;
- a deliberately invalid butterfly fixture with negative quadratic slack and
  negative call-convexity slack;
- closed-form wing-slope checks and input-domain failures.

The validation command and exact test count are recorded in `_INSTRUCTIONS/STATE.md`
at milestone completion.

## Limitations

The calendar test observes only the supplied knots. A caller must use a
non-decreasing interpolation for ATM total variance between them. The dense
call grid is finite and configurable, while the analytic conditions provide
the actual sufficient certificate. Bid/ask-aware fitting and optimizer
constraints are intentionally deferred to M06.
