# Repository Description

- The repository provides a modular Python script to price exotic FX options by reconstructing the volatility smile from sparse market quotes such as ATM volatility, 25-delta risk reversals and butterflies.

- Reconstructs the FX volatility smile from sparse market inputs and applies Vanna–Volga adjustments to Black–Scholes prices. Building on the calibrated smile, the framework is extended to exotic payoff foundations, pricing digital options via finite differences on Vanna–Volga adjusted vanilla prices.

- Computes Vega, Vanna and Volga using adaptive finite differences with Richardson extrapolation, including boundary-aware one-sided schemes for improved numerical stability.

- The circular dependency between deltas and strikes is handled through bracket scanning and a robust bisection algorithm.

- Includes a lightweight caching system that stores per-slice Greek matrices and strike-dependent Vanna–Volga weights, reducing repeated computations when pricing multiple options across the same market slice.

- The script prices exotic instruments, such as digital calls and puts, via finite differences on Vanna-Volga-adjusted vanilla prices, creating a foundation for extending the framework to other FX exotic options.

- Provides smile and volatility surface visualization plots to analyse the implied volatility structure induced by the Vanna–Volga pricing adjustment.


# Caching System
Instead of doing the same expensive calculation again, the script first checks whether the result is already available in memory.

In practical terms:
- if the result is already in the cache, this is a **cache hit**;
- if the result is not in the cache, this is a **cache miss**;
- on a cache miss, the script computes the result and stores it for later use.

This matters here because Vanna-Volga pricing repeatedly needs expensive Greek calculations and 3-by-3 linear solves. If we price many strikes on the same market slice, most of the structural information is the same. The script can therefore reuse it instead of rebuilding everything from zero.

The caching system is implemented inside:

```python
class VannaVolgaPricer
```

Conceptually, the script caches two things:

1. the Greek matrix for a market slice;
2. the Vanna-Volga weights for target strikes already priced on that slice.

### Why Caching Matters
For each target strike \(K\), pricing requires:
1. computing the Greek vector at the target strike,
2. solving a 3-by-3 linear system,
3. computing Black-Scholes prices at ATM, 25P, and 25C volatilities.

For each market slice, the pillar Greek matrix is even more expensive because it
requires Greeks at:

```text
K_25P
K_ATM
K_25C
```

Each Greek is itself built from several Black-Scholes calls. Vanna is especially
expensive because it is a derivative of Vega, and Vega is already numerical.

### Slice Cache

The script stores one cache entry per `MarketSlice`:

```python
self.slice_caches: dict[MarketSlice, SliceCache] = {}
```

Each cache entry contains:

```python
SliceCache(
    atm_rr_bf_greek_matrix=...,
    weights_by_strike=...
)
```

The matrix:

```python
atm_rr_bf_greek_matrix
```

depends only on the market slice. It does not depend on the target strike and it
does not depend on whether we are pricing a call or a put.

So, once a market slice has been used once, the expensive pillar Greek matrix is
stored and reused.

Mathematically, the cached matrix is:
```math
A =
\begin{bmatrix}
\text{Vega}_A & \text{Vega}_{RR} & \text{Vega}_{BF} \\
\text{Vanna}_A & \text{Vanna}_{RR} & \text{Vanna}_{BF} \\
\text{Volga}_A & \text{Volga}_{RR} & \text{Volga}_{BF}
\end{bmatrix}
```

### Strike Weight Cache
Each slice cache also stores:

```python
weights_by_strike: OrderedDict[int, tuple[float, float, float]]
```

This is a strike-level cache. If the script prices the same target strike again,
it can reuse the Vanna-Volga pillar weights instead of recomputing:

```text
target Greek vector
3-by-3 solve
ATM/RR/BF to pillar conversion
```

The strike key is:
$$\text{key}(K) = \text{round}(K \times 10^8)$$

This avoids using raw floating-point numbers as dictionary keys.

The cached value is:
$$\left(w_{25P}, w_{\text{ATM,pillar}}, w_{25C}\right)$$


### LRU Eviction
The script caps each strike cache:

```python
MAX_STRIKE_CACHE_PER_SLICE = 2048
```

The `OrderedDict` behaves like a lightweight LRU cache:

- on cache hit, the key is moved to the end with `move_to_end(key)`;
- when the cache exceeds the maximum size, the oldest item is removed with
  `popitem(last=False)`.

This keeps memory bounded while making repeated strike pricing fast.


# Adaptive Finite Differences
Finite differences approximate derivatives by perturbing an input and observing
how the output changes.

For a first derivative:
$$f'(x) \approx\frac{f(x+h)-f(x-h)}{2h}$$

For a second derivative:
$$f''(x) \approx \frac{f(x+h)-2f(x)+f(x-h)}{h^2}$$


The central numerical problem is choosing a good bump size $h$.
* if $h$ is too large, the derivative is too coarse because the price is measured over a wide interval. This is called **truncation error**.
* if $h$ is too small, the two prices being subtracted become almost identical: $f(x+h) \approx f(x-h)$

The subtraction can then lose numerical precision. This is called **floating-point cancellation** or **round-off error**.

The script therefore starts from **scale-aware bumps**. This means the initial bump is proportional to the variable being bumped, but it also has a minimum floor so it never becomes numerically meaningless.

For volatility Greeks, such as Vega and Volga, the bumped variable is $\sigma$:
$$h_\sigma = \max(5 \times 10^{-6}, 0.005|\sigma|)$$

The term $0.005|\sigma|$ means the initial volatility bump is 0.5% of the current
volatility level. The term $5 \times 10^{-6}$ is a minimum floor.

<br>

For the spot bump used in Vanna, the bumped variable is $S$:
$$h_S = \max(10^{-6}, 10^{-4}|S|)$$

The term $10^{-4}|S|$ means the initial spot bump is 0.01% of the current spot level. The term $10^{-6}$ is a minimum floor.

After choosing the initial bump, the script refines it by repeatedly halving it:
$$h_{n+1} = \frac{h_n}{2}$$

So the sequence of tested bumps is:
$$h_0,\quad \frac{h_0}{2},\quad \frac{h_0}{4},\quad \frac{h_0}{8},\quad \ldots$$


The loop does not refine forever. The maximum number of refinements is:

```python
MAX_REFINEMENTS = 5
```

This means the script can test at most:

$$
h_0,\quad
\frac{h_0}{2},\quad
\frac{h_0}{4},\quad
\frac{h_0}{8},\quad
\frac{h_0}{16},\quad
\frac{h_0}{32}
$$

The value `5` is a practical numerical compromise. It gives the derivative
enough chances to stabilize, but it avoids making $h$ so small that round-off
error dominates or the calculation becomes unnecessarily expensive.

### Stability Test

The loop stops when two consecutive estimates are close enough:

$$
|D_n - D_{n-1}|
\le
\epsilon_{\text{abs}}
+
\epsilon_{\text{rel}}
\max(1, |D_n|, |D_{n-1}|)
$$

The script uses:

```python
ABS_TOL = 1e-10
REL_TOL = 5e-4
```

### Boundary Protection

The script prevents invalid numerical bumps by enforcing:

```python
MIN_SIGMA = 1e-8
MIN_SPOT = 1e-12
MIN_STEP = 1e-8
```

If a symmetric scheme would cross the lower bound, the script uses a one-sided scheme.

For the first derivative near a lower bound:
$$f'(x) \approx \frac{-3f(x)+4f(x+h)-f(x+2h)}{2h}$$

For the second derivative near a lower bound:
$$f''(x) \approx \frac{f(x)-2f(x+h)+f(x+2h)}{h^2} $$


# Richardson Extrapolation

Richardson extrapolation improves a finite-difference estimate by combining two estimates computed with different step sizes.

Assume:
$$D(h)=D^* + C h^p + O(h^{p+1})$$

where:
- $D(h)$ is the derivative estimate using step \(h\),
- $D^*$ is the true derivative,
- $p$ is the convergence order.

The same derivative estimated with half the step is:
$$D(h/2)=D^* + C\left(\frac{h}{2}\right)^p + O(h^{p+1})$$

Eliminating the leading error term gives:
$$D_{\text{rich}}=\frac{2^pD(h/2)-D(h)}{2^p-1}$$


For central first derivatives, the order is $p = 2$ so:
$$D_{\text{rich}}=\frac{4D(h/2)-D(h)}{3}$$

For central second derivatives, the order is also $p = 2$.


Near a lower boundary, we use a boundary-aware one-sided scheme to maintain numerical stability for the second derivative, so the order is $p = 1$:
$$D_{\text{rich}}=2D(h/2)-D(h)$$



# Greeks Computation

### Vega
Vega is the first derivative with respect to volatility $\frac{\partial V}{\partial \sigma}$. The finite-difference estimate is:
$$\text{Vega} \approx \frac{V(\sigma+h_\sigma)-V(\sigma-h_\sigma)}{2h_\sigma}$$


### Volga
Volga is the second derivative with respect to volatility $\frac{\partial^2 V}{\partial \sigma^2}$. The finite-difference estimate is:
$$\text{Volga}\approx\frac{V(\sigma+h_\sigma)-2V(\sigma)+V(\sigma-h_\sigma)}{h_\sigma^2}$$


### Vanna
Vanna is implemented as the spot derivative of Vega $\frac{\partial \text{Vega}}{\partial S}$. The finite-difference estimate is:
$$\text{Vanna}\approx \frac{\text{Vega}(S+h_S)-\text{Vega}(S-h_S)}{2h_S}$$


Vanna is the most computationally expensive Greek to compute. Because it measures how Vega changes with respect to the underlying asset, every single Vanna calculation requires nested finite-difference loops.


# Digital Options
Digital options are priced from Vanna-Volga adjusted vanilla prices.

For a digital call:
$$\text{DigitalCall}(K)=-\frac{\partial C(K)}{\partial K}$$

The finite-difference approximation is:
$$\text{DigitalCall}(K) \approx \frac{C(K-\epsilon)-C(K+\epsilon)}{2\epsilon}$$

For a digital put:
$$\text{DigitalPut}(K) = \frac{\partial P(K)}{\partial K}$$

The finite-difference approximation is:
$$\text{DigitalPut}(K) \approx \frac{P(K+\epsilon)-P(K-\epsilon)}{2\epsilon}$$

The strike bump is:
$$\epsilon = \max(10^{-6}, 10^{-4}K)$$

Because the vanilla prices are already Vanna-Volga adjusted, the digital prices inherit the smile correction.




# End-To-End Flow
1. Parse the selected delta convention.
2. Define spot, domestic rate, foreign rate, maturity, ATM vol, RR, and BF.
3. Build 25P and 25C volatilities from ATM/RR/BF.
4. Convert 25-delta quotes into strikes.
5. Build a `MarketSlice`.
6. Compute or retrieve the cached pillar Greek matrix.
7. Compute target-strike Greeks using adaptive finite differences and
   Richardson extrapolation.
8. Solve the 3-by-3 Vanna-Volga weight system.
9. Convert ATM/RR/BF weights into pillar weights.
10. Cache the target-strike weights.
11. Price vanilla calls and puts with the VV correction.
12. Price digital calls and puts by finite differences on VV vanilla prices.
13. Optionally plot smile or surface diagnostics.

