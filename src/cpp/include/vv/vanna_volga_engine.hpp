#pragma once

#include <span>
#include <vector>

#include "vv/types.hpp"

namespace vv {

class VannaVolgaEngine {
 public:
  explicit VannaVolgaEngine(
      DeltaConvention convention = DeltaConvention::SpotPremiumExcluded);

  [[nodiscard]] MarketSlice build_slice(double spot, double domestic_rate,
                                        double foreign_rate,
                                        const SmileQuote& quote) const;

  [[nodiscard]] Greeks greeks(const MarketSlice& market_slice, double strike,
                              double volatility) const;

  [[nodiscard]] std::vector<Greeks> greeks_batch(
      const MarketSlice& market_slice, std::span<const double> strikes,
      double volatility) const;

  [[nodiscard]] WeightResult weights(const MarketSlice& market_slice,
                                     double strike) const;

  [[nodiscard]] double price_vanilla(const MarketSlice& market_slice,
                                     OptionType option_type,
                                     double strike) const;

  [[nodiscard]] std::vector<double> price_vanilla_batch(
      const MarketSlice& market_slice, OptionType option_type,
      std::span<const double> strikes) const;

  [[nodiscard]] double price_digital(const MarketSlice& market_slice,
                                     OptionType option_type,
                                     double strike) const;

  [[nodiscard]] ArbitrageDiagnostics check_arbitrage(
      const MarketSlice& market_slice, OptionType option_type,
      std::span<const double> strikes) const;

  [[nodiscard]] DigitalBoundsDiagnostics check_digital_bounds(
      const MarketSlice& market_slice, OptionType option_type,
      std::span<const double> strikes) const;

  [[nodiscard]] ParityDiagnostics check_put_call_parity(
      const MarketSlice& market_slice, double strike) const;

  [[nodiscard]] ParityDiagnostics check_digital_parity(
      const MarketSlice& market_slice, double strike) const;

  [[nodiscard]] double implied_volatility(
      const MarketSlice& market_slice, OptionType option_type, double strike,
      double target_price, double vol_low = 0.0,
      double vol_high = 0.0) const;

  [[nodiscard]] DeltaConvention delta_convention() const noexcept;

 private:
  [[nodiscard]] LinearSystem3 build_system(
      const MarketSlice& market_slice) const;
  [[nodiscard]] Vector3 build_pillar_premiums(
      const MarketSlice& market_slice) const;
  [[nodiscard]] double strike_derivative(const MarketSlice& market_slice,
                                         OptionType option_type,
                                         double strike,
                                         double step) const;
  [[nodiscard]] static bool digital_step_is_representable(double strike,
                                                          double step);
  [[nodiscard]] static ParityDiagnostics parity_diagnostics(
      double actual, double expected, double scale);

  DeltaConvention convention_;
};

}  // namespace vv
