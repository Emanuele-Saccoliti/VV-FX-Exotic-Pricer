# M01 baseline: hybrid Vanna–Volga v2

This documents the public behavior of source commit
`5267287ecc55dc781b4f9e4a91cec3a2c9be2a76` before the SSVI work. The
version reported by the Python package and `vv_cpp` extension is `0.3.0`.
M01 adds regression evidence and does not change pricing formulas.

## Reproduce

From a clean repository checkout with Python 3.11+, a C++20 compiler and CMake
3.20+, run:

```bash
python3 -m venv .venv
PYTHON_BIN=.venv/bin/python bash scripts/check_baseline.sh
```

The command installs the C++ extension, runs the Python tests, builds and runs
the two C++ tests, and runs the CLI demo. `build/` and `.venv/` are generated
and ignored. The script requires the repository's tracked `README.md`, which
is referenced by `pyproject.toml` during package installation.

## Public entry points

| Python interface | Current behavior |
| --- | --- |
| `SmileQuote(T, sigma_atm, rr25, bf25)` | One maturity's ATM, 25-delta risk reversal and butterfly. |
| `DeltaConvention` | Spot premium excluded, forward premium excluded, or spot premium included. |
| `build_application(convention)` | Constructs the C++ engine, market-slice builder and VV pricer. |
| `MarketSliceBuilder.build(spot, rd, rf, quote)` | Creates and validates a single-tenor slice with pillar strikes and vols. |
| `VannaVolgaPricer.price_vanilla`, `price_vanilla_batch` | VV call or put premium at positive strikes. |
| `VannaVolgaPricer.price_digital_call`, `price_digital_put` | Strike-derivative digital prices. |
| `VannaVolgaPricer.weights`, `weights_atm_rr_bf`, `weights_pillars` | Greek-system weights and solve diagnostics. |
| `VannaVolgaPricer.implied_volatility` | GK inversion for a given vanilla price. |
| `VannaVolgaPricer.greeks`, `greeks_batch` | Analytic GK vega, vanna and volga. |
| `VannaVolgaPricer.check_arbitrage`, `check_digital_bounds`, `check_put_call_parity`, `check_digital_parity` | Numerical diagnostics on supplied strikes. |
| `CppQuantitativeEngine.gk_price` | Garman–Kohlhagen vanilla reference price. |
| `python -m vv_pricer` / `vv-pricer` | Prints one-slice demo diagnostics; optional `--plots`. |

`vv_cpp` also exposes the underlying C++ `SmileQuote`, `MarketSlice`,
`VannaVolgaEngine`, GK functions and diagnostics via pybind11. The Python
facade is the supported orchestration layer. There is no multi-tenor object or
SSVI surface in this baseline.

## Numerical conventions

- Spot and strike are quoted as domestic currency per unit of foreign currency.
  Vanilla and digital prices are in domestic currency per unit foreign notional.
- `T` is in years; rates and volatilities are annualized decimal fractions.
  Rates are continuously compounded. The forward is
  `F = S0 exp((rd-rf)T)` and the domestic discount factor is `exp(-rd T)`.
- `sigma_25p = sigma_atm + bf25 - rr25/2` and
  `sigma_25c = sigma_atm + bf25 + rr25/2`. The ATM strike is the forward.
  The 25-delta strikes solve the selected convention using the corresponding
  25-delta volatilities.
- VV prices add a Greek-matched correction to the ATM-volatility GK price.
  The three original pillars reprice to their GK quotes within numerical
  precision. The reported weights are in both ATM/RR/BF and 25P/ATM/25C bases.
- Digital prices are numerical strike derivatives of VV vanilla prices using
  central differences and Richardson extrapolation, with initial bump
  `1e-4 * strike`. They are sensitive to roundoff more than vanilla prices.
- No-arbitrage diagnostics evaluate the supplied finite strike grid. They do
  not certify the entire VV smile or a future SSVI surface.

## Frozen regression evidence

`tests/fixtures/vv_baseline_v2.json` captures the original engine's outputs
for `S0=1.085`, `rd=0.03`, `rf=0.02`, `T=0.5`, `ATM=0.10`, `RR25=-0.02`,
`BF25=0.01`, and evaluation strike `1.10` under all three delta conventions.
It records pillar vols and strikes, both weight bases, vanilla prices and
digital prices. The source commit and capture date are stored in the fixture.

These values are regression anchors from the implementation, not independent
market observations or an independent pricing reference. Absolute tolerances
are `1e-12` for vols, `2e-10` for strikes and vanilla prices, `2e-9` for weights,
and `2e-8` for digitals. Strike roots and Greek solves can differ slightly
across compilers; the finite-difference digitals have the largest cancellation
error. Existing C++ GK parity/Greek checks and Python pillar repricing tests
provide independent mathematical checks alongside these frozen outputs.
