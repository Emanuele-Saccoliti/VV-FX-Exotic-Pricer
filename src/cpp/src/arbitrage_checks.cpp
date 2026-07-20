#include "vv/arbitrage_checks.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace vv {
namespace {

double roundoff_tolerance(const double scale) {
  return std::sqrt(std::numeric_limits<double>::epsilon()) * scale;
}

}  // namespace

ArbitrageDiagnostics check_monotonicity_and_convexity(
    const OptionType option_type, const std::span<const double> strikes,
    const std::span<const double> prices) {
  if (strikes.size() != prices.size() || strikes.size() < 3U) {
    throw std::invalid_argument(
        "arbitrage checks require matching strike/price vectors with at least three points");
  }
  double price_scale = 0.0;
  for (std::size_t index = 0; index < strikes.size(); ++index) {
    if (!(std::isfinite(strikes[index]) && strikes[index] > 0.0 &&
          std::isfinite(prices[index]))) {
      throw std::invalid_argument("strikes and prices must be finite; strikes must be positive");
    }
    if (index > 0U && strikes[index] <= strikes[index - 1U]) {
      throw std::invalid_argument("strikes must be strictly increasing");
    }
    price_scale = std::max(price_scale, std::abs(prices[index]));
  }

  std::size_t monotonicity_violations = 0U;
  std::size_t convexity_violations = 0U;
  double worst_monotonicity_excess = 0.0;
  double worst_convexity_excess = 0.0;

  for (std::size_t index = 1U; index < prices.size(); ++index) {
    const double directional_increase =
        option_type == OptionType::Call
            ? prices[index] - prices[index - 1U]
            : prices[index - 1U] - prices[index];
    const double excess =
        directional_increase - roundoff_tolerance(price_scale);
    if (excess > 0.0) {
      ++monotonicity_violations;
      worst_monotonicity_excess =
          std::max(worst_monotonicity_excess, excess);
    }
  }

  double slope_scale = 0.0;
  for (std::size_t index = 1U; index < prices.size(); ++index) {
    slope_scale = std::max(
        slope_scale,
        std::abs((prices[index] - prices[index - 1U]) /
                 (strikes[index] - strikes[index - 1U])));
  }
  for (std::size_t index = 1U; index + 1U < prices.size(); ++index) {
    const double left_slope =
        (prices[index] - prices[index - 1U]) /
        (strikes[index] - strikes[index - 1U]);
    const double right_slope =
        (prices[index + 1U] - prices[index]) /
        (strikes[index + 1U] - strikes[index]);
    const double excess =
        left_slope - right_slope - roundoff_tolerance(slope_scale);
    if (excess > 0.0) {
      ++convexity_violations;
      worst_convexity_excess = std::max(worst_convexity_excess, excess);
    }
  }

  return ArbitrageDiagnostics{
      strikes.size(),
      true,
      monotonicity_violations == 0U,
      convexity_violations == 0U,
      0U,
      0U,
      monotonicity_violations,
      convexity_violations,
      0.0,
      0.0,
      worst_monotonicity_excess,
      worst_convexity_excess,
  };
}

ArbitrageDiagnostics check_vanilla_arbitrage(
    const OptionType option_type, const std::span<const double> strikes,
    const std::span<const double> prices, const double spot,
    const double maturity, const double domestic_rate,
    const double foreign_rate) {
  ArbitrageDiagnostics diagnostics = check_monotonicity_and_convexity(
      option_type, strikes, prices);
  if (!(std::isfinite(spot) && spot > 0.0 && std::isfinite(maturity) &&
        maturity >= 0.0 && std::isfinite(domestic_rate) &&
        std::isfinite(foreign_rate))) {
    throw std::invalid_argument("invalid market inputs for vanilla price bounds");
  }

  const double discounted_spot = spot * std::exp(-foreign_rate * maturity);
  for (std::size_t index = 0U; index < prices.size(); ++index) {
    const double discounted_strike =
        strikes[index] * std::exp(-domestic_rate * maturity);
    const double lower_bound =
        option_type == OptionType::Call
            ? std::max(discounted_spot - discounted_strike, 0.0)
            : std::max(discounted_strike - discounted_spot, 0.0);
    const double upper_bound = option_type == OptionType::Call
                                   ? discounted_spot
                                   : discounted_strike;
    const double scale = std::max(
        {std::abs(prices[index]), std::abs(lower_bound),
         std::abs(upper_bound)});
    const double tolerance = roundoff_tolerance(scale);
    const double lower_excess = lower_bound - prices[index] - tolerance;
    const double upper_excess = prices[index] - upper_bound - tolerance;
    if (lower_excess > 0.0) {
      ++diagnostics.lower_bound_violations;
      diagnostics.worst_lower_bound_excess =
          std::max(diagnostics.worst_lower_bound_excess, lower_excess);
    }
    if (upper_excess > 0.0) {
      ++diagnostics.upper_bound_violations;
      diagnostics.worst_upper_bound_excess =
          std::max(diagnostics.worst_upper_bound_excess, upper_excess);
    }
  }
  diagnostics.within_bounds = diagnostics.lower_bound_violations == 0U &&
                              diagnostics.upper_bound_violations == 0U;
  return diagnostics;
}

DigitalBoundsDiagnostics check_digital_bounds(
    const std::span<const double> prices, const double maturity,
    const double domestic_rate) {
  if (prices.empty()) {
    throw std::invalid_argument("digital bounds require at least one price");
  }
  if (!(std::isfinite(maturity) && maturity >= 0.0 &&
        std::isfinite(domestic_rate))) {
    throw std::invalid_argument("invalid inputs for digital price bounds");
  }
  const double upper_bound = std::exp(-domestic_rate * maturity);
  std::size_t lower_bound_violations = 0U;
  std::size_t upper_bound_violations = 0U;
  double worst_lower_bound_excess = 0.0;
  double worst_upper_bound_excess = 0.0;
  for (const double price : prices) {
    if (!std::isfinite(price)) {
      throw std::invalid_argument("digital prices must be finite");
    }
    const double scale = std::max(std::abs(price), upper_bound);
    const double tolerance = roundoff_tolerance(scale);
    const double lower_excess = -price - tolerance;
    const double upper_excess = price - upper_bound - tolerance;
    if (lower_excess > 0.0) {
      ++lower_bound_violations;
      worst_lower_bound_excess =
          std::max(worst_lower_bound_excess, lower_excess);
    }
    if (upper_excess > 0.0) {
      ++upper_bound_violations;
      worst_upper_bound_excess =
          std::max(worst_upper_bound_excess, upper_excess);
    }
  }

  return DigitalBoundsDiagnostics{
      prices.size(),
      lower_bound_violations == 0U && upper_bound_violations == 0U,
      lower_bound_violations,
      upper_bound_violations,
      worst_lower_bound_excess,
      worst_upper_bound_excess,
  };
}

}  // namespace vv
