#include "vv/garman_kohlhagen.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <numbers>
#include <stdexcept>
#include <string>

namespace vv {
namespace {

void require_finite(const double value, const char* name) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument(std::string{name} + " must be finite");
  }
}

void validate_gk_inputs(const double spot, const double strike,
                        const double maturity, const double domestic_rate,
                        const double foreign_rate, const double volatility) {
  require_finite(spot, "spot");
  require_finite(strike, "strike");
  require_finite(maturity, "maturity");
  require_finite(domestic_rate, "domestic_rate");
  require_finite(foreign_rate, "foreign_rate");
  require_finite(volatility, "volatility");
  if (spot <= 0.0) {
    throw std::invalid_argument("spot must be positive");
  }
  if (strike <= 0.0) {
    throw std::invalid_argument("strike must be positive");
  }
  if (maturity < 0.0) {
    throw std::invalid_argument("maturity cannot be negative");
  }
  if (volatility < 0.0) {
    throw std::invalid_argument("volatility cannot be negative");
  }
}

bool brackets_root(const double first, const double second) {
  return first == 0.0 || second == 0.0 ||
         std::signbit(first) != std::signbit(second);
}

}  // namespace

double normal_cdf(const double x) {
  return 0.5 * std::erfc(-x / std::numbers::sqrt2);
}

double normal_pdf(const double x) {
  return std::exp(-0.5 * x * x) /
         std::sqrt(2.0 * std::numbers::pi);
}

double forward(const double spot, const double domestic_rate,
               const double foreign_rate, const double maturity) {
  return spot * std::exp((domestic_rate - foreign_rate) * maturity);
}

double discount_factor(const double rate, const double maturity) {
  return std::exp(-rate * maturity);
}

double gk_price(const OptionType option_type, const double spot,
                const double strike, const double maturity,
                const double domestic_rate, const double foreign_rate,
                const double volatility) {
  validate_gk_inputs(spot, strike, maturity, domestic_rate, foreign_rate,
                     volatility);
  if (maturity == 0.0) {
    if (option_type == OptionType::Call) {
      return std::max(spot - strike, 0.0);
    }
    return std::max(strike - spot, 0.0);
  }

  const double fwd = forward(spot, domestic_rate, foreign_rate, maturity);
  const double domestic_df = discount_factor(domestic_rate, maturity);
  if (volatility == 0.0) {
    return domestic_df *
           (option_type == OptionType::Call
                ? std::max(fwd - strike, 0.0)
                : std::max(strike - fwd, 0.0));
  }
  const double vol_sqrt_t = volatility * std::sqrt(maturity);
  const double d1 =
      (std::log(fwd / strike) + 0.5 * volatility * volatility * maturity) /
      vol_sqrt_t;
  const double d2 = d1 - vol_sqrt_t;

  if (option_type == OptionType::Call) {
    return domestic_df * (fwd * normal_cdf(d1) - strike * normal_cdf(d2));
  }
  return domestic_df *
         (strike * normal_cdf(-d2) - fwd * normal_cdf(-d1));
}

double gk_delta(const DeltaConvention convention,
                const OptionType option_type, const double spot,
                const double strike, const double maturity,
                const double domestic_rate, const double foreign_rate,
                const double volatility) {
  validate_gk_inputs(spot, strike, maturity, domestic_rate, foreign_rate,
                     volatility);
  if (maturity == 0.0) {
    if (option_type == OptionType::Call) {
      return spot > strike ? 1.0 : 0.0;
    }
    return spot < strike ? -1.0 : 0.0;
  }
  if (volatility == 0.0) {
    throw std::invalid_argument(
        "delta is discontinuous at zero volatility");
  }

  const double fwd = forward(spot, domestic_rate, foreign_rate, maturity);
  const double vol_sqrt_t = volatility * std::sqrt(maturity);
  const double d1 =
      (std::log(fwd / strike) + 0.5 * volatility * volatility * maturity) /
      vol_sqrt_t;
  const double d2 = d1 - vol_sqrt_t;
  const bool is_call = option_type == OptionType::Call;

  if (convention == DeltaConvention::SpotPremiumExcluded) {
    const double foreign_df = discount_factor(foreign_rate, maturity);
    return is_call ? foreign_df * normal_cdf(d1)
                   : -foreign_df * normal_cdf(-d1);
  }
  if (convention == DeltaConvention::ForwardPremiumExcluded) {
    return is_call ? normal_cdf(d1) : -normal_cdf(-d1);
  }

  const double scale =
      discount_factor(domestic_rate, maturity) * strike / spot;
  return is_call ? scale * normal_cdf(d2) : -scale * normal_cdf(-d2);
}

double implied_volatility(const double target_price,
                          const OptionType option_type, const double spot,
                          const double strike, const double maturity,
                          const double domestic_rate,
                          const double foreign_rate, const double vol_low,
                          const double vol_high, const double tolerance,
                          const std::size_t max_iterations) {
  require_finite(target_price, "target_price");
  if (maturity <= 0.0) {
    throw std::invalid_argument(
        "implied volatility requires a positive maturity");
  }
  if (vol_low < 0.0 || vol_high < 0.0 ||
      (vol_high > 0.0 && vol_low > 0.0 && vol_high <= vol_low)) {
    throw std::invalid_argument("invalid implied-volatility initial bracket");
  }
  if (tolerance < 0.0) {
    throw std::invalid_argument("invalid root-finder configuration");
  }

  const auto objective = [&](const double volatility) {
    return gk_price(option_type, spot, strike, maturity, domestic_rate,
                    foreign_rate, volatility) -
           target_price;
  };

  double lo = vol_low;
  double hi =
      vol_high > lo
          ? vol_high
          : std::max(2.0 * lo,
                     std::sqrt(std::numeric_limits<double>::epsilon()));
  double f_lo = objective(lo);
  if (!std::isfinite(f_lo)) {
    throw std::runtime_error(
        "implied-volatility objective returned a non-finite value");
  }
  if (f_lo == 0.0) {
    return lo;
  }
  if (f_lo > 0.0) {
    throw std::invalid_argument(
        "target price is below the near-zero-volatility price");
  }
  double f_hi = objective(hi);
  while (f_hi < 0.0) {
    if (!(hi <= 0.5 * std::numeric_limits<double>::max())) {
      break;
    }
    hi *= 2.0;
    f_hi = objective(hi);
  }
  if (!(std::isfinite(f_hi) && brackets_root(f_lo, f_hi))) {
    throw std::invalid_argument(
        "implied-volatility root could not be dynamically bracketed");
  }
  if (f_hi == 0.0) {
    return hi;
  }

  std::size_t iteration = 0U;
  while (max_iterations == 0U || iteration < max_iterations) {
    const double midpoint = std::midpoint(lo, hi);
    if (midpoint == lo || midpoint == hi) {
      return midpoint;
    }
    const double f_midpoint = objective(midpoint);
    if (f_midpoint == 0.0 ||
        (tolerance > 0.0 &&
         (std::abs(f_midpoint) < tolerance || (hi - lo) < tolerance))) {
      return midpoint;
    }
    if (brackets_root(f_lo, f_midpoint)) {
      hi = midpoint;
    } else {
      lo = midpoint;
      f_lo = f_midpoint;
    }
    ++iteration;
  }
  return 0.5 * (lo + hi);
}

}  // namespace vv
