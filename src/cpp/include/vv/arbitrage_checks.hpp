#pragma once

#include <span>

#include "vv/types.hpp"

namespace vv {

ArbitrageDiagnostics check_monotonicity_and_convexity(
    OptionType option_type, std::span<const double> strikes,
    std::span<const double> prices);

ArbitrageDiagnostics check_vanilla_arbitrage(
    OptionType option_type, std::span<const double> strikes,
    std::span<const double> prices, double spot, double maturity,
    double domestic_rate, double foreign_rate);

DigitalBoundsDiagnostics check_digital_bounds(
    std::span<const double> prices, double maturity, double domestic_rate);

}  // namespace vv
