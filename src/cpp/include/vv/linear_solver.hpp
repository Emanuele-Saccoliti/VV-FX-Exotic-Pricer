#pragma once

#include "vv/types.hpp"

namespace vv {

LinearSystem3 analyze_linear_system(const Matrix3& matrix);

LinearSolveResult solve_linear_system(const LinearSystem3& system,
                                      const Vector3& right_hand_side);

}  // namespace vv
