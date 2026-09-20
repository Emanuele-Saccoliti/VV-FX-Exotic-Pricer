# Architecture

## Dependency direction

```text
market quotes
  → FX conventions / complete VV smiles by tenor
  → sampled VV total variances with pillar provenance and weights
  → constrained global SSVI projection
  → GK target grid
  → Heston Fourier engine
  → Heston calibrator
  → Heston MC engine
  → DNT payoff/report
```

Later modules may depend on earlier abstractions. Surface construction must not
depend on Heston; the Heston model must not depend on the DNT payoff.

## Proposed Python layout

```text
vv_pricer/
  market.py                 # existing market inputs, extended to multi-tenor
  conventions.py            # existing FX delta/ATM conventions
  pricer.py                 # existing VV public API
  surface/
    __init__.py
    types.py                # pillars, VV smile samples, total-variance points
    ssvi.py                 # kernel and parameterization
    constraints.py          # admissibility and diagnostics
    calibration.py          # weighted VV-to-SSVI global constrained fit
    target_grid.py          # SSVI IV → GK prices and weights
  models/
    heston.py               # parameter object and validation
    calibration.py          # optimizer orchestration
  products/
    double_no_touch.py      # product definition, no simulation loops
  reports/
    calibration.py
    convergence.py
  cpp_engine.py             # existing extension adapter, expanded batch API
```

## Proposed C++ layout

```text
src/cpp/
  include/vvfx/
    heston_parameters.hpp
    heston_characteristic.hpp
    heston_fourier.hpp
    heston_simulator.hpp
    double_no_touch.hpp
    mc_result.hpp
  heston_characteristic.cpp
  heston_fourier.cpp
  heston_simulator.cpp
  double_no_touch.cpp
  bindings.cpp
```

Adapt exact paths to the current repository conventions rather than duplicating
existing modules.

## Binding surface

Prefer batch calls such as:

```python
heston_prices(params, spot, rd, rf, maturities, strikes, fft_config)
price_double_no_touch(params, market, product, mc_config)
```

Return structured arrays or small result objects. Do not expose C++ iterators,
random engines, path-level callbacks, or a call per strike/time step.

## Numerical configuration

Configurations must be explicit serializable objects:

- `FFTConfig`: grid size, spacing, damping, interpolation policy;
- `HestonCalibrationConfig`: bounds/transforms, weights, tolerances, restarts;
- `MCConfig`: paths, steps, seed, scheme, antithetic flag, bridge policy.

Every report serializes the configurations used so results are reproducible.
