#pragma once

#include "vv/types.hpp"

namespace vv {

Greeks analytic_greeks(double spot, double strike, double maturity,
                       double domestic_rate, double foreign_rate,
                       double volatility);

}  // namespace vv
