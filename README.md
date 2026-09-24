# Hybrid Python/C++ FX Pricer

An FX options pricer built in layers. The working engine reconstructs a
Vanna–Volga (VV) smile from ATM, 25-delta risk-reversal and butterfly quotes,
then prices vanilla and digital options. Python provides the public workflow;
C++ performs the numerical pricing through a `pybind11` extension.

The next layers will use the implemented SSVI kernel to project complete VV
smiles onto a constrained surface, calibrate Heston to vanilla prices derived
from that surface, and price a double-no-touch option with C++ Monte Carlo.
Those layers are planned; the current release does **not** yet implement SSVI
constraints or calibration, Heston, or DNT pricing.

## Project status

| Layer | Status | What it delivers |
| --- | --- | --- |
| Vanna–Volga engine | Implemented | FX conventions, market pillars, GK and VV pricing, digitals, diagnostics and plots. |
| M01 baseline | Verified | Frozen numerical outputs for all three delta conventions and a reproducible test command. |
| M02 market contracts | Implemented | Immutable multi-tenor ATM/RR/BF inputs with explicit rates and conventions. |
| M03 multi-tenor VV | Implemented | Reusable complete-smile samples with liquid-pillar provenance and explicit reliable-wing cutoffs. |
| SSVI kernel | Implemented | Vectorized power-law SSVI total variance with validated parameters. |
| SSVI constraints and calibration | Planned | Constrained cross-maturity projection of sampled VV total variances. |
| Heston calibration | Planned | C++ Fourier vanilla prices calibrated to GK targets from SSVI. |
| Heston double-no-touch | Planned | C++ Monte Carlo price, standard error and confidence interval. |

This README grows with the implementation: each completed layer adds its
inputs, public API, numerical conventions, example, validation evidence and
known limitations here. Planned features stay marked as planned until their
code and tests pass.

## Current capabilities

- Reconstruct 25P and 25C volatilities and strikes from ATM, RR25 and BF25
  quotes under spot premium-excluded, forward premium-excluded or spot
  premium-included FX delta conventions.
- Price calls and puts with Garman–Kohlhagen (GK) and a VV correction matched
  to the three market pillars. Invert GK prices to implied volatilities.
- Price digital calls and puts from strike derivatives of the complete VV price
  using centered differences and Richardson extrapolation.
- Expose scalar and batch vanilla pricing, analytic Vega/Vanna/Volga, VV
  replication weights and Greek-system condition diagnostics.
- Check put-call and digital parity, theoretical price bounds, monotonicity and
  convexity on supplied strike grids.
- Plot VV smiles, a reconstructed volatility surface and Greek profiles. The
  plotting demo can use several independent maturities; it is not yet a
  calibrated cross-maturity SSVI surface.
- Sample a complete VV smile for every tenor in `FxMarketTermStructure`,
  returning strikes, forwards, implied volatilities, total variances and the
  provenance of every liquid or synthetic observation.
- Evaluate scalar or broadcast-array SSVI total variances with an immutable,
  validated power-law parameter object.

## Architecture

```text
ATM / RR25 / BF25 market quotes
          ↓
Python: quote objects, FX convention, application and reports
          ↓
C++: delta-to-strike, GK, Greeks and Vanna–Volga engine
          ↓
VV vanilla and digital prices, smile plots and diagnostics

Planned extension:
VV smiles → constrained SSVI → GK target prices
          → Heston Fourier calibration → Heston MC → DNT
```

The existing VV implementation is retained as the foundation for the new
layers; extending the project does not require rewriting that engine.

### What the folders mean

| Folder | Contents | Keep in Git? |
| --- | --- | --- |
| `vv_pricer/` | Python API and workflow. | Yes |
| `src/cpp/` | C++ pricing engine and Python bindings. | Yes |
| `tests/python/`, `tests/cpp/` | Test source code written for the project. | Yes |
| `tests/fixtures/` | Fixed reference values used by regression tests. | Yes |
| `docs/`, `scripts/` | Project documentation and repeatable commands. | Yes |
| `_generated/` | Temporary compiler output and CTest run logs. | No |
| `.venv/` | Locally installed Python packages and compiled extension. | No |

CTest creates a folder named `Testing/` **inside** `_generated/cpp-tests/`
when it runs. That folder contains its logs and results; the actual test code
is only in `tests/`. You can delete `_generated/` at any time.

## Requirements and installation

- Python 3.11 or newer
- CMake 3.20 or newer
- A C++20 compiler

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The installation compiles `vv_cpp` into the local environment. `_generated/`,
`.venv/` and test caches are generated files and are ignored by Git. They can
be removed and recreated; the source code is in `vv_pricer/` and `src/cpp/`.

## Run the current pricer

```bash
python -m vv_pricer
python -m vv_pricer FWD_PREM_EXCLUDED
python -m vv_pricer SPOT_PREM_INCLUDED --plots
```

The default convention is `SPOT_PREM_EXCLUDED`. The equivalent installed
command is `vv-pricer`; `run_demo.py` is also retained for compatibility.

### Python API

```python
from vv_pricer import DeltaConvention, SmileQuote, build_application

application = build_application(DeltaConvention.SPOT_PREM_EXCLUDED)
market_slice = application.builder.build(
    spot=1.085,
    domestic_rate=0.03,
    foreign_rate=0.02,
    quote=SmileQuote(T=0.5, sigma_atm=0.10, rr25=-0.02, bf25=0.01),
)

strike = 1.10
call = application.pricer.price_vanilla(market_slice, True, strike)
put = application.pricer.price_vanilla(market_slice, False, strike)
digital_call = application.pricer.price_digital_call(market_slice, strike)
weights = application.pricer.weights(market_slice, strike)
```

Here `T` is in years; rates and volatilities are annualized decimal fractions.
Spot and strike are domestic currency per unit of foreign currency. Rates are
continuously compounded and the forward is
`F_T = S_0 exp((r_d - r_f) T)`.

### Multi-tenor market contract

`FxMarketTermStructure` is the validated input boundary for a term structure.
It holds one positive spot, explicit delta and ATM conventions, and one
`TenorMarketQuote` per maturity. Each tenor pairs a `SmileQuote` with its own
continuously compounded domestic and foreign rates. Maturities are stored in
strictly increasing order and must be unique.

```python
from vv_pricer import (
    AtmConvention,
    DeltaConvention,
    FxMarketTermStructure,
    SmileQuote,
    TenorMarketQuote,
)

market = FxMarketTermStructure.from_tenors(
    spot=1.085,
    delta_convention=DeltaConvention.SPOT_PREM_EXCLUDED,
    atm_convention=AtmConvention.FORWARD,
    tenors=(
        TenorMarketQuote(SmileQuote(0.25, 0.095, -0.012, 0.004), 0.030, 0.020),
        TenorMarketQuote(SmileQuote(1.00, 0.110, -0.018, 0.007), 0.032, 0.021),
    ),
)
```

The current engine supports `AtmConvention.FORWARD`, consistent with its
existing forward-ATM strike construction.

### Multi-tenor VV smile sampling

`VannaVolgaSmileSampler.sample` builds all stored tenors in one call. Each
`VvSmileSample` is ordered by strike and exposes `strikes`,
`implied_volatilities`, `total_variances`, `forward`, and `provenances`.
`liquid_pillars` selects the original 25P/ATM/25C inputs; `synthetic_points`
selects observations obtained by repricing the complete VV smile and inverting
the corresponding out-of-the-money GK price.

```python
from vv_pricer import VannaVolgaSmileSampler

samples = VannaVolgaSmileSampler().sample(market)
for sample in samples:
    print(sample.maturity, sample.forward, sample.strikes)
```

The deterministic default grid is expressed in forward log-moneyness. It
contains all three liquid pillars and three synthetic interior points in each
anchor interval. The reliable-region cutoff extends only 50% of the relevant
25-delta-to-ATM distance beyond each 25-delta pillar. Both the sampling density
and extension fraction are configurable with `VvSmileSamplingConfig`, and the
actual lower and upper cutoffs are stored on every result. This cutoff is a
documented VV reliability heuristic, not a proof of absence of static
arbitrage; later SSVI calibration must still enforce its own constraints.

### SSVI total-variance kernel

`ssvi_total_variance` evaluates the SSVI slice in forward log-moneyness
`k = log(K/F)` for positive ATM total variance `theta`. The initial shape
family is `phi(theta) = eta * theta**(-gamma)`, with immutable validated
`SsviPowerLawParameters`. Scalar inputs return a float; NumPy-compatible array
inputs broadcast and return a `float64` array.

```text
w(k, theta) = theta/2 * [1 + rho*phi(theta)*k
                  + sqrt((phi(theta)*k + rho)^2 + 1 - rho^2)]
```

```python
import numpy as np

from vv_pricer import SsviPowerLawParameters, ssvi_total_variance

parameters = SsviPowerLawParameters(rho=-0.35, eta=1.1, gamma=0.25)
log_moneyness = np.array([-0.20, 0.0, 0.20])
total_variance = ssvi_total_variance(log_moneyness, 0.04, parameters)
```

The parameter object enforces `-1 < rho < 1`, `eta > 0`, and
`0 < gamma <= 0.5`, following the power-law family in
[Gatheral and Jacquier](https://arxiv.org/abs/1204.0646). These are local
parameter-domain checks, not a complete static-arbitrage certificate.
Butterfly and calendar constraints, surface diagnostics, and calibration are
deliberately deferred to later milestones.

## From FX quotes to VV prices

The three market volatilities are

```text
sigma_25P = sigma_ATM + BF25 - RR25 / 2
sigma_25C = sigma_ATM + BF25 + RR25 / 2
```

The ATM strike is the forward. Each wing strike solves the selected 25-delta
convention at its own wing volatility. For a strike `K`, the VV engine matches
the target option's Vega, Vanna and Volga to the three pillars and applies the
resulting correction to its ATM-volatility GK price:

```text
V_VV(K) = V_GK(K, sigma_ATM)
        + w_25P(K) [V_GK(K_25P, sigma_25P) - V_GK(K_25P, sigma_ATM)]
        + w_25C(K) [V_GK(K_25C, sigma_25C) - V_GK(K_25C, sigma_ATM)]
```

Pillar repricing is checked against GK at the quoted volatilities. Digital
prices use numerical strike derivatives of the *full* VV vanilla price. The
finite strike-grid checks help detect local arbitrage violations but do not
prove that the entire VV smile is arbitrage-free.

## Validation

After installation, run the Python tests without recompiling:

```bash
python -m pytest -q
```

For a full clean-build check, including the C++ tests and CLI demo:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/check_baseline.sh
```

M01 froze 25P/ATM/25C volatilities and strikes, both VV weight bases, vanilla
prices and digital prices for all three supported delta conventions. The
[baseline record](docs/baseline.md) explains the numerical conventions,
fixture provenance and tolerances. The frozen values are regression anchors
from the existing engine, alongside independent parity, Greek and pillar
repricing checks.

## Next layer

The next implementation step is to encode SSVI no-arbitrage constraints and
diagnostics. Calibration remains a later milestone.
