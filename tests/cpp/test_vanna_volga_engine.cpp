#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "vv/garman_kohlhagen.hpp"
#include "vv/vanna_volga_engine.hpp"

namespace {

void expect_close(const double actual, const double expected,
                  const double tolerance, const std::string& label) {
  if (std::abs(actual - expected) > tolerance) {
    throw std::runtime_error(label + " mismatch: actual=" +
                             std::to_string(actual) +
                             " expected=" + std::to_string(expected));
  }
}

}  // namespace

int main() {
  constexpr double spot = 1.085;
  constexpr double domestic_rate = 0.03;
  constexpr double foreign_rate = 0.02;
  constexpr double strike = 1.10;
  const vv::SmileQuote quote{0.5, 0.10, -0.02, 0.01};

  for (const vv::DeltaConvention convention : {
           vv::DeltaConvention::SpotPremiumExcluded,
           vv::DeltaConvention::ForwardPremiumExcluded,
           vv::DeltaConvention::SpotPremiumIncluded,
       }) {
    const vv::VannaVolgaEngine engine{convention};
    const vv::MarketSlice market_slice =
        engine.build_slice(spot, domestic_rate, foreign_rate, quote);

    for (const auto [pillar_strike, pillar_volatility] : {
             std::pair{market_slice.strike_25p, market_slice.sigma_25p},
             std::pair{market_slice.strike_atm, market_slice.sigma_atm},
             std::pair{market_slice.strike_25c, market_slice.sigma_25c},
         }) {
      for (const vv::OptionType option_type : {vv::OptionType::Call,
                                               vv::OptionType::Put}) {
        const double vv_price =
            engine.price_vanilla(market_slice, option_type, pillar_strike);
        const double market_price = vv::gk_price(
            option_type, spot, pillar_strike, quote.maturity, domestic_rate,
            foreign_rate, pillar_volatility);
        expect_close(vv_price, market_price, 3e-12, "pillar repricing");
      }
    }

    const vv::WeightResult weight_result = engine.weights(market_slice, strike);
    const double numerical_tolerance =
        std::sqrt(std::numeric_limits<double>::epsilon());
    if (!(weight_result.condition_number < 1.0 / numerical_tolerance &&
          weight_result.backward_error < numerical_tolerance)) {
      throw std::runtime_error("invalid Greek-system diagnostics");
    }

    if (!engine.check_put_call_parity(market_slice, strike).passed ||
        !engine.check_digital_parity(market_slice, strike).passed) {
      throw std::runtime_error("vanilla or digital parity failed");
    }

    std::vector<double> strikes;
    strikes.reserve(101U);
    for (std::size_t index = 0U; index < 101U; ++index) {
      const double fraction = static_cast<double>(index) / 100.0;
      strikes.push_back(market_slice.strike_25p +
                        fraction * (market_slice.strike_25c -
                                    market_slice.strike_25p));
    }
    const vv::ArbitrageDiagnostics call_checks = engine.check_arbitrage(
        market_slice, vv::OptionType::Call,
        std::span<const double>(strikes));
    const vv::ArbitrageDiagnostics put_checks = engine.check_arbitrage(
        market_slice, vv::OptionType::Put,
        std::span<const double>(strikes));
    if (!(call_checks.within_bounds && call_checks.monotonic &&
          call_checks.convex && put_checks.within_bounds &&
          put_checks.monotonic && put_checks.convex)) {
      throw std::runtime_error("static-arbitrage checks failed");
    }

    const std::vector<double> digital_strikes{market_slice.strike_atm};
    if (!engine
             .check_digital_bounds(
                 market_slice, vv::OptionType::Call,
                 std::span<const double>(digital_strikes))
             .within_bounds ||
        !engine
             .check_digital_bounds(
                 market_slice, vv::OptionType::Put,
                 std::span<const double>(digital_strikes))
             .within_bounds) {
      throw std::runtime_error("digital bounds failed");
    }
  }

  const vv::VannaVolgaEngine flat_engine{};
  const vv::SmileQuote flat_quote{0.5, 0.10, 0.0, 0.0};
  const vv::MarketSlice flat_slice =
      flat_engine.build_slice(spot, domestic_rate, foreign_rate, flat_quote);
  const double fwd = vv::forward(spot, domestic_rate, foreign_rate,
                                 flat_quote.maturity);
  const double vol_sqrt_t = flat_quote.sigma_atm *
                            std::sqrt(flat_quote.maturity);
  const double d2 =
      (std::log(fwd / strike) -
       0.5 * flat_quote.sigma_atm * flat_quote.sigma_atm *
           flat_quote.maturity) /
      vol_sqrt_t;
  const double exact_digital_call =
      vv::discount_factor(domestic_rate, flat_quote.maturity) *
      vv::normal_cdf(d2);
  expect_close(flat_engine.price_digital(flat_slice, vv::OptionType::Call,
                                         strike),
               exact_digital_call, 1e-10, "flat-smile digital call");

  std::cout << "Hybrid Vanna-Volga engine checks passed\n";
  return 0;
}
