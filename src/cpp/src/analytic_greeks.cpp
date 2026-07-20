#include "vv/analytic_greeks.hpp"

#include <cmath>
#include <stdexcept>

#include "vv/garman_kohlhagen.hpp"

namespace vv {

Greeks analytic_greeks(const double spot, const double strike,
                       const double maturity, const double domestic_rate,
                       const double foreign_rate, const double volatility) {
  if (!(std::isfinite(spot) && std::isfinite(strike) &&
        std::isfinite(maturity) && std::isfinite(domestic_rate) &&
        std::isfinite(foreign_rate) && std::isfinite(volatility))) {
    throw std::invalid_argument("Greek inputs must be finite");
  }
  if (spot <= 0.0 || strike <= 0.0 || maturity <= 0.0 ||
      volatility <= 0.0) {
    throw std::invalid_argument(
        "analytic Greeks require positive spot, strike, maturity and volatility");
  }

  const double sqrt_t = std::sqrt(maturity);
  const double vol_sqrt_t = volatility * sqrt_t;
  const double fwd = forward(spot, domestic_rate, foreign_rate, maturity);
  const double d1 =
      (std::log(fwd / strike) + 0.5 * volatility * volatility * maturity) /
      vol_sqrt_t;
  const double d2 = d1 - vol_sqrt_t;
  const double foreign_df = discount_factor(foreign_rate, maturity);
  const double vega = spot * foreign_df * normal_pdf(d1) * sqrt_t;
  const double vanna = -foreign_df * normal_pdf(d1) * d2 / volatility;
  const double volga = vega * d1 * d2 / volatility;
  return Greeks{vega, vanna, volga};
}

}  // namespace vv
