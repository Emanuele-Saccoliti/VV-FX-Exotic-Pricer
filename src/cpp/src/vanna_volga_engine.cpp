#include "vv/vanna_volga_engine.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

#include "vv/analytic_greeks.hpp"
#include "vv/arbitrage_checks.hpp"
#include "vv/garman_kohlhagen.hpp"
#include "vv/linear_solver.hpp"
#include "vv/market_slice.hpp"

namespace vv {
namespace {

constexpr double digital_relative_bump = 1e-4;

Vector3 to_vector(const Greeks& greeks) {
  return Vector3{greeks.vega, greeks.vanna, greeks.volga};
}

Vector3 rr_bf_to_pillars(const Vector3& weights) {
  const double weight_atm = weights[0];
  const double weight_rr = weights[1];
  const double weight_bf = weights[2];
  return Vector3{-weight_rr + 0.5 * weight_bf, weight_atm - weight_bf,
                 weight_rr + 0.5 * weight_bf};
}

}  // namespace

VannaVolgaEngine::VannaVolgaEngine(const DeltaConvention convention)
    : convention_{convention} {}

MarketSlice VannaVolgaEngine::build_slice(
    const double spot, const double domestic_rate, const double foreign_rate,
    const SmileQuote& quote) const {
  MarketSlice market_slice = build_market_slice(
      spot, domestic_rate, foreign_rate, quote, convention_);
  market_slice.greek_system = build_system(market_slice);
  market_slice.pillar_premiums = build_pillar_premiums(market_slice);
  return market_slice;
}

Greeks VannaVolgaEngine::greeks(const MarketSlice& market_slice,
                                const double strike,
                                const double volatility) const {
  return analytic_greeks(market_slice.spot, strike, market_slice.maturity,
                         market_slice.domestic_rate, market_slice.foreign_rate,
                         volatility);
}

std::vector<Greeks> VannaVolgaEngine::greeks_batch(
    const MarketSlice& market_slice, const std::span<const double> strikes,
    const double volatility) const {
  std::vector<Greeks> result;
  result.reserve(strikes.size());
  for (const double strike : strikes) {
    result.push_back(greeks(market_slice, strike, volatility));
  }
  return result;
}

LinearSystem3 VannaVolgaEngine::build_system(
    const MarketSlice& market_slice) const {
  const Vector3 vector_25p =
      to_vector(greeks(market_slice, market_slice.strike_25p,
                       market_slice.sigma_atm));
  const Vector3 vector_atm =
      to_vector(greeks(market_slice, market_slice.strike_atm,
                       market_slice.sigma_atm));
  const Vector3 vector_25c =
      to_vector(greeks(market_slice, market_slice.strike_25c,
                       market_slice.sigma_atm));

  Vector3 vector_rr{};
  Vector3 vector_bf{};
  for (std::size_t index = 0U; index < 3U; ++index) {
    vector_rr[index] = vector_25c[index] - vector_25p[index];
    vector_bf[index] =
        0.5 * (vector_25c[index] + vector_25p[index]) - vector_atm[index];
  }

  const Matrix3 matrix{{
      Vector3{vector_atm[0], vector_rr[0], vector_bf[0]},
      Vector3{vector_atm[1], vector_rr[1], vector_bf[1]},
      Vector3{vector_atm[2], vector_rr[2], vector_bf[2]},
  }};
  return analyze_linear_system(matrix);
}

Vector3 VannaVolgaEngine::build_pillar_premiums(
    const MarketSlice& market_slice) const {
  const auto volatility_premium = [&](const double strike,
                                      const double volatility) {
    const double market_price = gk_price(
        OptionType::Call, market_slice.spot, strike, market_slice.maturity,
        market_slice.domestic_rate, market_slice.foreign_rate, volatility);
    const double atm_price = gk_price(
        OptionType::Call, market_slice.spot, strike, market_slice.maturity,
        market_slice.domestic_rate, market_slice.foreign_rate,
        market_slice.sigma_atm);
    return market_price - atm_price;
  };

  return Vector3{
      volatility_premium(market_slice.strike_25p, market_slice.sigma_25p),
      0.0,
      volatility_premium(market_slice.strike_25c, market_slice.sigma_25c),
  };
}

WeightResult VannaVolgaEngine::weights(const MarketSlice& market_slice,
                                       const double strike) const {
  if (!(std::isfinite(strike) && strike > 0.0)) {
    throw std::invalid_argument("strike must be finite and positive");
  }
  if (!(std::isfinite(market_slice.greek_system.condition_number) &&
        market_slice.greek_system.condition_number > 0.0)) {
    throw std::invalid_argument("market slice has not been prepared");
  }

  const LinearSolveResult solved = solve_linear_system(
      market_slice.greek_system,
      to_vector(greeks(market_slice, strike, market_slice.sigma_atm)));
  return WeightResult{solved.solution, rr_bf_to_pillars(solved.solution),
                      solved.condition_number, solved.residual_inf_norm,
                      solved.backward_error};
}

double VannaVolgaEngine::price_vanilla(const MarketSlice& market_slice,
                                       const OptionType option_type,
                                       const double strike) const {
  const WeightResult weight_result = weights(market_slice, strike);
  const double base =
      gk_price(option_type, market_slice.spot, strike, market_slice.maturity,
               market_slice.domestic_rate, market_slice.foreign_rate,
               market_slice.sigma_atm);

  double correction = 0.0;
  for (std::size_t index = 0U; index < 3U; ++index) {
    correction += weight_result.pillars[index] *
                  market_slice.pillar_premiums[index];
  }
  return base + correction;
}

std::vector<double> VannaVolgaEngine::price_vanilla_batch(
    const MarketSlice& market_slice, const OptionType option_type,
    const std::span<const double> strikes) const {
  std::vector<double> result;
  result.reserve(strikes.size());
  for (const double strike : strikes) {
    result.push_back(price_vanilla(market_slice, option_type, strike));
  }
  return result;
}

bool VannaVolgaEngine::digital_step_is_representable(const double strike,
                                                     const double step) {
  return step > 0.0 && strike - step > 0.0 && strike - step < strike &&
         strike + step > strike && std::isfinite(strike + step);
}

double VannaVolgaEngine::strike_derivative(
    const MarketSlice& market_slice, const OptionType option_type,
    const double strike, const double step) const {
  if (!digital_step_is_representable(strike, step)) {
    throw std::runtime_error(
        "digital finite-difference step is not representable");
  }
  return (price_vanilla(market_slice, option_type, strike + step) -
          price_vanilla(market_slice, option_type, strike - step)) /
         (2.0 * step);
}

double VannaVolgaEngine::price_digital(const MarketSlice& market_slice,
                                       const OptionType option_type,
                                       const double strike) const {
  if (!(std::isfinite(strike) && strike > 0.0)) {
    throw std::invalid_argument("strike must be finite and positive");
  }
  const double step = digital_relative_bump * strike;
  const double half_step = 0.5 * step;
  const double coarse =
      strike_derivative(market_slice, option_type, strike, step);
  const double fine =
      strike_derivative(market_slice, option_type, strike, half_step);
  const double richardson = (4.0 * fine - coarse) / 3.0;
  return option_type == OptionType::Call ? -richardson : richardson;
}

ArbitrageDiagnostics VannaVolgaEngine::check_arbitrage(
    const MarketSlice& market_slice, const OptionType option_type,
    const std::span<const double> strikes) const {
  const std::vector<double> prices =
      price_vanilla_batch(market_slice, option_type, strikes);
  return check_vanilla_arbitrage(
      option_type, strikes, std::span<const double>(prices), market_slice.spot,
      market_slice.maturity, market_slice.domestic_rate,
      market_slice.foreign_rate);
}

DigitalBoundsDiagnostics VannaVolgaEngine::check_digital_bounds(
    const MarketSlice& market_slice, const OptionType option_type,
    const std::span<const double> strikes) const {
  if (strikes.empty()) {
    throw std::invalid_argument("digital bounds require at least one strike");
  }
  std::vector<double> prices;
  prices.reserve(strikes.size());
  for (const double strike : strikes) {
    prices.push_back(price_digital(market_slice, option_type, strike));
  }
  return vv::check_digital_bounds(std::span<const double>(prices),
                                  market_slice.maturity,
                                  market_slice.domestic_rate);
}

ParityDiagnostics VannaVolgaEngine::parity_diagnostics(
    const double actual, const double expected, const double scale) {
  const double error = std::abs(actual - expected);
  const double normalized_error = scale > 0.0 ? error / scale : error;
  const double tolerance =
      std::sqrt(std::numeric_limits<double>::epsilon());
  return ParityDiagnostics{normalized_error <= tolerance, actual, expected,
                           error, normalized_error};
}

ParityDiagnostics VannaVolgaEngine::check_put_call_parity(
    const MarketSlice& market_slice, const double strike) const {
  const double call = price_vanilla(market_slice, OptionType::Call, strike);
  const double put = price_vanilla(market_slice, OptionType::Put, strike);
  const double domestic_df =
      discount_factor(market_slice.domestic_rate, market_slice.maturity);
  const double fwd = forward(market_slice.spot, market_slice.domestic_rate,
                             market_slice.foreign_rate,
                             market_slice.maturity);
  const double discounted_spot =
      market_slice.spot *
      discount_factor(market_slice.foreign_rate, market_slice.maturity);
  const double discounted_strike = domestic_df * strike;
  return parity_diagnostics(call - put, domestic_df * (fwd - strike),
                            discounted_spot + discounted_strike);
}

ParityDiagnostics VannaVolgaEngine::check_digital_parity(
    const MarketSlice& market_slice, const double strike) const {
  const double call = price_digital(market_slice, OptionType::Call, strike);
  const double put = price_digital(market_slice, OptionType::Put, strike);
  const double domestic_df =
      discount_factor(market_slice.domestic_rate, market_slice.maturity);
  return parity_diagnostics(call + put, domestic_df, domestic_df);
}

double VannaVolgaEngine::implied_volatility(
    const MarketSlice& market_slice, const OptionType option_type,
    const double strike, const double target_price, const double vol_low,
    const double vol_high) const {
  return vv::implied_volatility(
      target_price, option_type, market_slice.spot, strike,
      market_slice.maturity, market_slice.domestic_rate,
      market_slice.foreign_rate, vol_low, vol_high);
}

DeltaConvention VannaVolgaEngine::delta_convention() const noexcept {
  return convention_;
}

}  // namespace vv
