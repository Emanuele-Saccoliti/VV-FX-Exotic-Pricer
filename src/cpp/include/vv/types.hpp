#pragma once

#include <array>
#include <cstddef>

namespace vv {

enum class DeltaConvention {
  SpotPremiumExcluded,
  ForwardPremiumExcluded,
  SpotPremiumIncluded,
};

enum class OptionType { Call, Put };

struct SmileQuote {
  double maturity;
  double sigma_atm;
  double rr25;
  double bf25;
};

struct Greeks {
  double vega;
  double vanna;
  double volga;
};

using Vector3 = std::array<double, 3>;
using Matrix3 = std::array<Vector3, 3>;

struct LinearSystem3 {
  Matrix3 matrix;
  Matrix3 inverse;
  double condition_number;
};

struct MarketSlice {
  double spot;
  double domestic_rate;
  double foreign_rate;
  double maturity;
  double sigma_atm;
  double sigma_25p;
  double sigma_25c;
  double strike_atm;
  double strike_25p;
  double strike_25c;
  DeltaConvention delta_convention;
  LinearSystem3 greek_system{};
  Vector3 pillar_premiums{};
};

struct LinearSolveResult {
  Vector3 solution;
  double condition_number;
  double residual_inf_norm;
  double backward_error;
};

struct WeightResult {
  Vector3 atm_rr_bf;
  Vector3 pillars;
  double condition_number;
  double residual_inf_norm;
  double backward_error;
};

struct ArbitrageDiagnostics {
  std::size_t points;
  bool within_bounds;
  bool monotonic;
  bool convex;
  std::size_t lower_bound_violations;
  std::size_t upper_bound_violations;
  std::size_t monotonicity_violations;
  std::size_t convexity_violations;
  double worst_lower_bound_excess;
  double worst_upper_bound_excess;
  double worst_monotonicity_excess;
  double worst_convexity_excess;
};

struct DigitalBoundsDiagnostics {
  std::size_t points;
  bool within_bounds;
  std::size_t lower_bound_violations;
  std::size_t upper_bound_violations;
  double worst_lower_bound_excess;
  double worst_upper_bound_excess;
};

struct ParityDiagnostics {
  bool passed;
  double actual;
  double expected;
  double absolute_error;
  double normalized_error;
};

}  // namespace vv
