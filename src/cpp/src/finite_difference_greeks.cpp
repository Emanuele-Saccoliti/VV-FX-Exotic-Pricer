#include "vv/finite_difference_greeks.hpp"

#include <cmath>
#include <limits>
#include <optional>
#include <stdexcept>

#include "vv/garman_kohlhagen.hpp"

namespace vv {
namespace {

struct StencilEstimate {
  double value;
  double roundoff_bound;
};

struct BestEstimate {
  double value;
  double estimated_error;
};

bool representable_central_step(const double value, const double step) {
  return step > 0.0 && value + step != value && value - step != value;
}

void consider_richardson_estimate(
    const std::optional<double> previous_richardson,
    const double current_richardson, const double roundoff_bound,
    BestEstimate& best) {
  if (!previous_richardson.has_value() ||
      !std::isfinite(current_richardson) ||
      !std::isfinite(roundoff_bound)) {
    return;
  }

  // Successive fourth-order estimates differ by 15 times the finer-grid
  // leading truncation error.
  const double truncation_error =
      std::abs(current_richardson - previous_richardson.value()) / 15.0;
  const double total_error = truncation_error + roundoff_bound;
  if (total_error < best.estimated_error) {
    best = BestEstimate{current_richardson, total_error};
  }
}

template <typename Estimator>
double refine_one_dimension(Estimator estimate, const double value) {
  double step = 0.25 * value;
  StencilEstimate previous_raw = estimate(step);
  std::optional<double> previous_richardson;
  BestEstimate best{previous_raw.value,
                    std::numeric_limits<double>::infinity()};

  while (true) {
    const double next_step = 0.5 * step;
    if (!representable_central_step(value, next_step)) {
      break;
    }

    const StencilEstimate current_raw = estimate(next_step);
    const double current_richardson =
        (4.0 * current_raw.value - previous_raw.value) / 3.0;
    const double roundoff_bound =
        (4.0 * current_raw.roundoff_bound + previous_raw.roundoff_bound) /
        3.0;
    consider_richardson_estimate(previous_richardson, current_richardson,
                                 roundoff_bound, best);

    previous_raw = current_raw;
    previous_richardson = current_richardson;
    step = next_step;
  }
  return best.value;
}

template <typename Estimator>
double refine_two_dimensions(Estimator estimate, const double first_value,
                             const double second_value) {
  double first_step = 0.25 * first_value;
  double second_step = 0.25 * second_value;
  StencilEstimate previous_raw = estimate(first_step, second_step);
  std::optional<double> previous_richardson;
  BestEstimate best{previous_raw.value,
                    std::numeric_limits<double>::infinity()};

  while (true) {
    const double next_first_step = 0.5 * first_step;
    const double next_second_step = 0.5 * second_step;
    if (!representable_central_step(first_value, next_first_step) ||
        !representable_central_step(second_value, next_second_step)) {
      break;
    }

    const StencilEstimate current_raw =
        estimate(next_first_step, next_second_step);
    const double current_richardson =
        (4.0 * current_raw.value - previous_raw.value) / 3.0;
    const double roundoff_bound =
        (4.0 * current_raw.roundoff_bound + previous_raw.roundoff_bound) /
        3.0;
    consider_richardson_estimate(previous_richardson, current_richardson,
                                 roundoff_bound, best);

    previous_raw = current_raw;
    previous_richardson = current_richardson;
    first_step = next_first_step;
    second_step = next_second_step;
  }
  return best.value;
}

}  // namespace

Greeks finite_difference_greeks(
    const double spot, const double strike, const double maturity,
    const double domestic_rate, const double foreign_rate,
    const double volatility) {
  if (!(std::isfinite(spot) && spot > 0.0 &&
        std::isfinite(volatility) && volatility > 0.0)) {
    throw std::invalid_argument(
        "spot and volatility must be finite and positive for finite differences");
  }

  const auto price = [&](const double bumped_spot,
                         const double bumped_volatility) {
    return gk_price(OptionType::Call, bumped_spot, strike, maturity,
                    domestic_rate, foreign_rate, bumped_volatility);
  };
  constexpr double epsilon = std::numeric_limits<double>::epsilon();

  const double vega = refine_one_dimension(
      [&](const double step) {
        const double upper = price(spot, volatility + step);
        const double lower = price(spot, volatility - step);
        return StencilEstimate{
            (upper - lower) / (2.0 * step),
            epsilon * (std::abs(upper) + std::abs(lower)) / (2.0 * step)};
      },
      volatility);

  const double central_price = price(spot, volatility);
  const double volga = refine_one_dimension(
      [&](const double step) {
        const double upper = price(spot, volatility + step);
        const double lower = price(spot, volatility - step);
        return StencilEstimate{
            (upper - 2.0 * central_price + lower) / (step * step),
            epsilon * (std::abs(upper) + 2.0 * std::abs(central_price) +
                       std::abs(lower)) /
                (step * step)};
      },
      volatility);

  const double vanna = refine_two_dimensions(
      [&](const double spot_step, const double volatility_step) {
        const double upper_upper =
            price(spot + spot_step, volatility + volatility_step);
        const double upper_lower =
            price(spot + spot_step, volatility - volatility_step);
        const double lower_upper =
            price(spot - spot_step, volatility + volatility_step);
        const double lower_lower =
            price(spot - spot_step, volatility - volatility_step);
        const double denominator = 4.0 * spot_step * volatility_step;
        return StencilEstimate{
            (upper_upper - upper_lower - lower_upper + lower_lower) /
                denominator,
            epsilon * (std::abs(upper_upper) + std::abs(upper_lower) +
                       std::abs(lower_upper) + std::abs(lower_lower)) /
                denominator};
      },
      spot, volatility);

  return Greeks{vega, vanna, volga};
}

}  // namespace vv
