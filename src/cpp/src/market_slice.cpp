#include "vv/market_slice.hpp"

#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>

#include "vv/garman_kohlhagen.hpp"

namespace vv {
namespace {

double require_positive_volatility(const double volatility,
                                   const char* label) {
  if (!(std::isfinite(volatility) && volatility > 0.0)) {
    throw std::invalid_argument(std::string{label} +
                                " volatility must be finite and positive");
  }
  return volatility;
}

bool brackets_root(const double first, const double second) {
  return first == 0.0 || second == 0.0 ||
         std::signbit(first) != std::signbit(second);
}

double bisect(const std::function<double(double)>& objective, double lo,
              double hi) {
  double f_lo = objective(lo);
  const double f_hi = objective(hi);
  if (!(std::isfinite(f_lo) && std::isfinite(f_hi))) {
    throw std::runtime_error("delta root objective returned a non-finite value");
  }
  if (!brackets_root(f_lo, f_hi)) {
    throw std::runtime_error("delta-to-strike root is not bracketed");
  }
  if (f_lo == 0.0) {
    return lo;
  }
  if (f_hi == 0.0) {
    return hi;
  }

  while (true) {
    const double midpoint = std::midpoint(lo, hi);
    if (midpoint == lo || midpoint == hi) {
      return midpoint;
    }
    const double f_midpoint = objective(midpoint);
    if (f_midpoint == 0.0) {
      return midpoint;
    }
    if (brackets_root(f_lo, f_midpoint)) {
      hi = midpoint;
    } else {
      lo = midpoint;
      f_lo = f_midpoint;
    }
  }
}

double strike_from_delta(const double spot, const double domestic_rate,
                         const double foreign_rate, const double maturity,
                         const double volatility, const OptionType option_type,
                         const double target_delta,
                         const DeltaConvention convention) {
  const double fwd = forward(spot, domestic_rate, foreign_rate, maturity);
  const auto objective = [&](const double strike) {
    return gk_delta(convention, option_type, spot, strike, maturity,
                    domestic_rate, foreign_rate, volatility) -
           target_delta;
  };

  if (option_type == OptionType::Call) {
    double lo = fwd;
    double f_lo = objective(lo);
    if (f_lo < 0.0) {
      throw std::runtime_error(
          "25-delta call has no root on the out-of-the-money branch");
    }
    double hi = 2.0 * fwd;
    while (true) {
      const double f_hi = objective(hi);
      if (std::isfinite(f_hi) && brackets_root(f_lo, f_hi)) {
        return bisect(objective, lo, hi);
      }
      lo = hi;
      f_lo = f_hi;
      if (!(hi <= 0.5 * std::numeric_limits<double>::max())) {
        break;
      }
      hi *= 2.0;
    }
  } else {
    double hi = fwd;
    double f_hi = objective(hi);
    if (f_hi > 0.0) {
      throw std::runtime_error(
          "25-delta put has no root on the out-of-the-money branch");
    }
    double lo = 0.5 * fwd;
    while (true) {
      const double f_lo = objective(lo);
      if (std::isfinite(f_lo) && brackets_root(f_lo, f_hi)) {
        return bisect(objective, lo, hi);
      }
      hi = lo;
      f_hi = f_lo;
      const double next_lo = 0.5 * lo;
      if (!(next_lo > 0.0 && next_lo < lo)) {
        break;
      }
      lo = next_lo;
    }
  }
  throw std::runtime_error(
      "could not dynamically bracket delta-to-strike root");
}

}  // namespace

MarketSlice build_market_slice(const double spot, const double domestic_rate,
                               const double foreign_rate,
                               const SmileQuote& quote,
                               const DeltaConvention convention) {
  if (!(std::isfinite(spot) && std::isfinite(domestic_rate) &&
        std::isfinite(foreign_rate) && std::isfinite(quote.maturity) &&
        std::isfinite(quote.sigma_atm) && std::isfinite(quote.rr25) &&
        std::isfinite(quote.bf25))) {
    throw std::invalid_argument("market inputs must be finite");
  }
  if (spot <= 0.0 || quote.maturity <= 0.0 || quote.sigma_atm <= 0.0) {
    throw std::invalid_argument(
        "spot, maturity and ATM volatility must be positive");
  }
  const double sigma_25p =
      require_positive_volatility(
          quote.sigma_atm + quote.bf25 - 0.5 * quote.rr25, "25P");
  const double sigma_25c =
      require_positive_volatility(
          quote.sigma_atm + quote.bf25 + 0.5 * quote.rr25, "25C");
  const double strike_atm =
      forward(spot, domestic_rate, foreign_rate, quote.maturity);
  const double strike_25c = strike_from_delta(
      spot, domestic_rate, foreign_rate, quote.maturity, sigma_25c,
      OptionType::Call, 0.25, convention);
  const double strike_25p = strike_from_delta(
      spot, domestic_rate, foreign_rate, quote.maturity, sigma_25p,
      OptionType::Put, -0.25, convention);

  return MarketSlice{spot,
                     domestic_rate,
                     foreign_rate,
                     quote.maturity,
                     quote.sigma_atm,
                     sigma_25p,
                     sigma_25c,
                     strike_atm,
                     strike_25p,
                     strike_25c,
                     convention};
}

}  // namespace vv
