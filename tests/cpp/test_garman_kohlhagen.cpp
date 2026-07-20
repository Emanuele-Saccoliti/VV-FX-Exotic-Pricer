#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

#include "vv/analytic_greeks.hpp"
#include "vv/finite_difference_greeks.hpp"
#include "vv/garman_kohlhagen.hpp"

namespace {

void expect_close(const double actual, const double expected,
                  const double absolute_tolerance,
                  const double relative_tolerance, const std::string& label) {
  const double scale = std::max(std::abs(actual), std::abs(expected));
  const double tolerance = absolute_tolerance + relative_tolerance * scale;
  if (std::abs(actual - expected) > tolerance) {
    throw std::runtime_error(label + " mismatch: actual=" +
                             std::to_string(actual) +
                             " expected=" + std::to_string(expected));
  }
}

}  // namespace

int main() {
  constexpr double spot = 1.085;
  constexpr double strike = 1.10;
  constexpr double maturity = 0.5;
  constexpr double domestic_rate = 0.03;
  constexpr double foreign_rate = 0.02;
  constexpr double volatility = 0.10;

  const double call = vv::gk_price(vv::OptionType::Call, spot, strike, maturity,
                                   domestic_rate, foreign_rate, volatility);
  const double put = vv::gk_price(vv::OptionType::Put, spot, strike, maturity,
                                  domestic_rate, foreign_rate, volatility);
  const double parity = vv::discount_factor(domestic_rate, maturity) *
                        (vv::forward(spot, domestic_rate, foreign_rate,
                                     maturity) -
                         strike);
  expect_close(call - put, parity, 1e-14, 1e-12, "put-call parity");

  const vv::Greeks greeks = vv::analytic_greeks(
      spot, strike, maturity, domestic_rate, foreign_rate, volatility);
  const vv::Greeks finite_difference = vv::finite_difference_greeks(
      spot, strike, maturity, domestic_rate, foreign_rate, volatility);

  expect_close(greeks.vega, finite_difference.vega, 1e-9, 2e-6, "Vega");
  expect_close(greeks.vanna, finite_difference.vanna, 1e-8, 3e-6, "Vanna");
  expect_close(greeks.volga, finite_difference.volga, 1e-7, 3e-6, "Volga");

  const double recovered_volatility = vv::implied_volatility(
      call, vv::OptionType::Call, spot, strike, maturity, domestic_rate,
      foreign_rate);
  expect_close(recovered_volatility, volatility, 1e-11, 1e-11,
               "implied volatility");

  const double zero_volatility_call = vv::gk_price(
      vv::OptionType::Call, spot, strike, maturity, domestic_rate,
      foreign_rate, 0.0);
  const double recovered_zero_volatility = vv::implied_volatility(
      zero_volatility_call, vv::OptionType::Call, spot, strike, maturity,
      domestic_rate, foreign_rate);
  expect_close(recovered_zero_volatility, 0.0, 0.0, 0.0,
               "zero implied volatility limit");

  constexpr double high_volatility = 4.0;
  const double high_volatility_call = vv::gk_price(
      vv::OptionType::Call, spot, strike, maturity, domestic_rate,
      foreign_rate, high_volatility);
  const double recovered_high_volatility = vv::implied_volatility(
      high_volatility_call, vv::OptionType::Call, spot, strike, maturity,
      domestic_rate, foreign_rate);
  expect_close(recovered_high_volatility, high_volatility, 1e-10, 1e-10,
               "dynamically bracketed high implied volatility");

  std::cout << "Garman-Kohlhagen and analytic Greek checks passed\n";
  return 0;
}
