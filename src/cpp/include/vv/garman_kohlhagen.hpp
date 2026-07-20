#pragma once

#include "vv/types.hpp"

namespace vv {

double normal_cdf(double x);
double normal_pdf(double x);
double forward(double spot, double domestic_rate, double foreign_rate,
               double maturity);
double discount_factor(double rate, double maturity);

double gk_price(OptionType option_type, double spot, double strike,
                double maturity, double domestic_rate, double foreign_rate,
                double volatility);

double gk_delta(DeltaConvention convention, OptionType option_type, double spot,
                double strike, double maturity, double domestic_rate,
                double foreign_rate, double volatility);

double implied_volatility(double target_price, OptionType option_type,
                          double spot, double strike, double maturity,
                          double domestic_rate, double foreign_rate,
                          double vol_low = 0.0, double vol_high = 0.0,
                          double tolerance = 0.0,
                          std::size_t max_iterations = 0);

}  // namespace vv
