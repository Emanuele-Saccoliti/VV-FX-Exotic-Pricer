# Repository Description

- The repository provides a modular Python script to price exotic FX options by reconstructing the volatility smile from sparse market quotes such as ATM volatility, 25-delta risk reversals and butterflies.

- Reconstructs the FX volatility smile from sparse market inputs and applies Vanna–Volga adjustments to Black–Scholes prices. Building on the calibrated smile, the framework is extended to exotic payoff foundations, pricing digital options via finite differences on Vanna–Volga adjusted vanilla prices.

- Computes Vega, Vanna and Volga using adaptive finite differences with Richardson extrapolation, including boundary-aware one-sided schemes for improved numerical stability.

- The circular dependency between deltas and strikes is handled through bracket scanning and a robust bisection algorithm.

- Includes a lightweight caching system that stores per-slice Greek matrices and strike-dependent Vanna–Volga weights, reducing repeated computations when pricing multiple options across the same market slice.

- The script prices exotic instruments, such as digital calls and puts, via finite differences on Vanna-Volga-adjusted vanilla prices, creating a foundation for extending the framework to other FX exotic options.

- Provides smile and volatility surface visualization tools to inspect the implied volatility structure induced by the Vanna–Volga pricing adjustment.

