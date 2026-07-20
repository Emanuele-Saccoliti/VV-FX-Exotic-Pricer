# Hybrid Python/C++ Vanna-Volga FX Pricer

This project is a hybrid Python/C++ engine for pricing FX options with the
**Vanna-Volga** method. It starts from ATM volatility, 25-delta risk reversal
and butterfly quotes, converts the market deltas into strikes, constructs the
Vanna-Volga replication portfolio, and uses the resulting smile adjustment to
price vanilla and digital options.

The engine includes:

- validation of FX market inputs and reconstruction of the 25P and 25C wing
  volatilities from ATM, risk-reversal and butterfly quotes;
- Garman-Kohlhagen pricing, FX delta calculation and implied-volatility inversion;
- support for spot premium-excluded, forward premium-excluded and spot
  premium-included delta conventions;
- numerical inversion from 25-delta quotes to their corresponding market
  strikes;
- analytic Vega, Vanna and Volga calculations in the compiled C++ backend;
- construction and inversion of the 3-by-3 Vanna-Volga Greek matrix, including
  condition-number, residual and backward-error diagnostics;
- precomputation of the pillar volatility premiums and Greek matrix for each
  market slice, avoiding repeated slice-level calculations;
- Vanna-Volga pricing of vanilla calls and puts across individual strikes or
  strike arrays;
- pricing of digital calls and puts through centered strike differences and
  Richardson extrapolation;
- diagnostics for vanilla price bounds, digital price bounds, put-call parity,
  digital parity, monotonicity and convexity;
- an independent finite-difference and Richardson implementation used to
  validate the analytic C++ Greeks;
- visualization of reconstructed smiles, the 3D implied-volatility surface and
  2D Vega, Vanna and Volga profiles.

**Python and C++ responsibilities**

Python manages the public API and the higher-level pricing workflow. It is
responsible for:

- defining smile quotes and selecting the FX delta convention;
- building pricing applications and market slices through the C++ interface;
- exposing single-strike and batch pricing operations;
- organizing arbitrage, bounds and parity diagnostics;
- generating the smile, volatility-surface and Greek-profile plots;
- running the demonstration workflow and Python integration tests.

C++ implements the quantitative calculations exposed to Python through the
`vv_cpp` extension. It is responsible for:

- Garman-Kohlhagen pricing, deltas and implied-volatility inversion;
- converting delta quotes into 25P, ATM and 25C market strikes;
- computing analytic Vega, Vanna and Volga;
- constructing, checking and solving the Vanna-Volga Greek system;
- precomputing pillar premiums and applying the Vanna-Volga correction;
- pricing vanilla and digital options, including Richardson extrapolation for
  strike derivatives;
- evaluating pricing bounds, parity, monotonicity and convexity;
- computing the independent finite-difference Greeks used by the validation
  tests.

In short, Python organizes the workflow and visualization, while C++ performs
the pricing, Greek, linear-algebra and numerical-diagnostic calculations.

**Requirements**

- Python 3.11 or newer;
- CMake 3.20 or newer;
- a C++20 compiler.

## Structure

```text
Hybrid/
|-- CMakeLists.txt
|-- pyproject.toml
|-- run_demo.py
|-- src/cpp/
|   |-- include/vv/
|   |-- src/
|   `-- bindings/pybind_module.cpp
|-- vv_pricer/
|   |-- application.py
|   |-- cpp_engine.py
|   |-- domain.py
|   |-- market.py
|   |-- pricer.py
|   |-- plotting.py
|   `-- demo.py
`-- tests/
    |-- cpp/
    `-- python/
```

## Build

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The editable installation compiles the `vv_cpp` extension with CMake and a
C++20 compiler.

## Run

```bash
source .venv/bin/activate
python run_demo.py
```

Other conventions:

```bash
python run_demo.py FWD_PREM_EXCLUDED
python run_demo.py SPOT_PREM_INCLUDED --plots
```

The `--plots` view includes:

- the reconstructed Vanna-Volga smile;
- a 3D reconstructed VV volatility surface with its market pillars;
- 2D Vega, Vanna and Volga profiles for each maturity.

The surface uses log-moneyness $\log(K/F)$ and recovers continuous implied
volatilities from VV prices. Every maturity spans its complete 25P-to-ATM-to-25C
interval, and the quoted market pillars are shown directly on the surface.

## Python API

```python
from vv_pricer import DeltaConvention, SmileQuote, build_application

application = build_application(DeltaConvention.SPOT_PREM_EXCLUDED)

market_slice = application.builder.build(
    1.085,
    0.03,
    0.02,
    SmileQuote(T=0.5, sigma_atm=0.10, rr25=-0.02, bf25=0.01),
)

call = application.pricer.price_vanilla(market_slice, True, 1.10)
put = application.pricer.price_vanilla(market_slice, False, 1.10)
digital_call = application.pricer.price_digital_call(market_slice, 1.10)

put_call_check = application.pricer.check_put_call_parity(
    market_slice,
    1.10,
)
```

## Smile Quotes

The 25-delta wing volatilities are reconstructed from ATM volatility, risk
reversal and butterfly:

$$
\sigma_{25P}=\sigma_{ATM}+BF_{25}-\frac{RR_{25}}{2},
$$

$$
\sigma_{25C}=\sigma_{ATM}+BF_{25}+\frac{RR_{25}}{2}.
$$

The C++ engine validates that both wing volatilities are finite and positive.

## Analytic Greeks

For

$$
F=S e^{(r_d-r_f)T},
\qquad
d_1=\frac{\log(F/K)+\frac12\sigma^2T}{\sigma\sqrt{T}},
\qquad
d_2=d_1-\sigma\sqrt{T},
$$

the production engine uses:

$$
\operatorname{Vega}=S e^{-r_fT}\phi(d_1)\sqrt{T},
$$

$$
\operatorname{Vanna}=-e^{-r_fT}\phi(d_1)\frac{d_2}{\sigma},
$$

$$
\operatorname{Volga}=\operatorname{Vega}\frac{d_1d_2}{\sigma}.
$$

The test suite compares these formulas with a separate C++ implementation
based on finite differences and Richardson extrapolation. The numerical Greeks
are validation code only and are not used by the pricer. Their refinement starts
from bumps equal to 25% of spot and volatility, then halves both steps while
balancing truncation and floating-point errors.

## Prepared Market Slice

Building a market slice performs the expensive slice-level work once:

- construction of the ATM, 25P and 25C strikes;
- calculation of the three pillar Greek vectors;
- construction and inversion of the 3-by-3 Vanna-Volga matrix;
- condition-number analysis;
- calculation of the fixed 25P and 25C volatility premiums.

The prepared slice owns this data. Pricing a new strike only computes its
analytic Greek vector and multiplies it by the stored inverse matrix:

$$
w(K)=A^{-1}g(K).
$$

This replaces the previous general-purpose cache. There are no floating-point
cache keys, eviction rules or capacity parameters.

The Vanna-Volga price is:

$$
V_{VV}(K)=V_{ATM}(K)
+w_{25P}(K)\Delta V_{25P}
+w_{25C}(K)\Delta V_{25C},
$$

where each pillar premium is computed once at its own market strike:

$$
\Delta V_i=V_{GK}(K_i,\sigma_i)-V_{GK}(K_i,\sigma_{ATM}).
$$

## Digital Pricing

Digital prices are strike derivatives of the complete Vanna-Volga price:

$$
D_{call}(K)=-\frac{\partial C_{VV}}{\partial K},
\qquad
D_{put}(K)=\frac{\partial P_{VV}}{\partial K}.
$$

The implementation uses the fixed relative bump

$$
h=10^{-4}K,
$$

which is one basis point of strike. It computes two centered derivatives:

$$
D(h)=\frac{V(K+h)-V(K-h)}{2h},
$$

$$
D(h/2)=\frac{V(K+h/2)-V(K-h/2)}{h},
$$

and applies Richardson once:

$$
D_{rich}=\frac{4D(h/2)-D(h)}{3}.
$$

The bump is a transparent numerical heuristic. A deterministic flat-smile test
compares the result with analytic Garman-Kohlhagen digitals.

## Diagnostics

For strike grids, the engine checks:

- theoretical call and put price bounds;
- digital bounds between zero and the domestic discount factor;
- call and put monotonicity;
- convexity using secant slopes on non-uniform grids.

It also provides explicit single-strike checks for:

$$
C(K)-P(K)=e^{-r_dT}(F-K),
$$

$$
D_{call}(K)+D_{put}(K)=e^{-r_dT}.
$$

These checks are called without tolerance parameters. Small floating-point
protections are handled automatically inside C++.

Each weight calculation exposes the matrix condition number, raw residual and
normalized backward error.

## Tests

Python integration tests:

```bash
python -m pytest -q
```

C++ tests:

```bash
cmake -S . -B build/cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DVV_BUILD_PYTHON=OFF \
  -DVV_BUILD_TESTS=ON

cmake --build build/cmake --parallel
ctest --test-dir build/cmake --output-on-failure
```
