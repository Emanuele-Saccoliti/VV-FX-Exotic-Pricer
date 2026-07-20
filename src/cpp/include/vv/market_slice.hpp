#pragma once

#include "vv/types.hpp"

namespace vv {

MarketSlice build_market_slice(
    double spot, double domestic_rate, double foreign_rate,
    const SmileQuote& quote, DeltaConvention convention);

}  // namespace vv
