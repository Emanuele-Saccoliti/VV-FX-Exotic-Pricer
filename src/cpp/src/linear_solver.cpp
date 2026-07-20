#include "vv/linear_solver.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace vv {
namespace {

double matrix_inf_norm(const Matrix3& matrix) {
  double norm = 0.0;
  for (const auto& row : matrix) {
    double row_sum = 0.0;
    for (const double value : row) {
      if (!std::isfinite(value)) {
        throw std::invalid_argument("linear-system matrix must be finite");
      }
      row_sum += std::abs(value);
    }
    norm = std::max(norm, row_sum);
  }
  return norm;
}

Vector3 gaussian_solve(const Matrix3& input_matrix,
                       const Vector3& right_hand_side) {
  Matrix3 matrix = input_matrix;
  Vector3 rhs = right_hand_side;
  const double matrix_norm = matrix_inf_norm(matrix);
  if (matrix_norm == 0.0) {
    throw std::runtime_error("singular zero 3x3 matrix");
  }
  const double pivot_tolerance =
      3.0 * std::numeric_limits<double>::epsilon() * matrix_norm;

  for (std::size_t column = 0; column < 3U; ++column) {
    std::size_t pivot = column;
    double best = std::abs(matrix[column][column]);
    for (std::size_t row = column + 1U; row < 3U; ++row) {
      const double candidate = std::abs(matrix[row][column]);
      if (candidate > best) {
        best = candidate;
        pivot = row;
      }
    }
    if (best <= pivot_tolerance) {
      throw std::runtime_error("singular or numerically rank-deficient 3x3 matrix");
    }
    if (pivot != column) {
      std::swap(matrix[pivot], matrix[column]);
      std::swap(rhs[pivot], rhs[column]);
    }

    for (std::size_t row = column + 1U; row < 3U; ++row) {
      const double factor = matrix[row][column] / matrix[column][column];
      for (std::size_t index = column; index < 3U; ++index) {
        matrix[row][index] -= factor * matrix[column][index];
      }
      rhs[row] -= factor * rhs[column];
    }
  }

  Vector3 solution{};
  for (std::size_t reverse = 0; reverse < 3U; ++reverse) {
    const std::size_t row = 2U - reverse;
    double subtotal = rhs[row];
    for (std::size_t column = row + 1U; column < 3U; ++column) {
      subtotal -= matrix[row][column] * solution[column];
    }
    solution[row] = subtotal / matrix[row][row];
  }
  return solution;
}

}  // namespace

LinearSystem3 analyze_linear_system(const Matrix3& matrix) {
  const double condition_limit =
      1.0 / std::sqrt(std::numeric_limits<double>::epsilon());
  Matrix3 inverse{};
  for (std::size_t column = 0; column < 3U; ++column) {
    Vector3 basis{};
    basis[column] = 1.0;
    const Vector3 inverse_column = gaussian_solve(matrix, basis);
    for (std::size_t row = 0; row < 3U; ++row) {
      inverse[row][column] = inverse_column[row];
    }
  }

  const double condition_number =
      matrix_inf_norm(matrix) * matrix_inf_norm(inverse);
  if (!std::isfinite(condition_number) ||
      condition_number > condition_limit) {
    throw std::runtime_error("Vanna-Volga Greek matrix is ill-conditioned");
  }
  return LinearSystem3{matrix, inverse, condition_number};
}

LinearSolveResult solve_linear_system(const LinearSystem3& system,
                                      const Vector3& right_hand_side) {
  Vector3 solution{};
  for (std::size_t row = 0; row < 3U; ++row) {
    for (std::size_t column = 0; column < 3U; ++column) {
      solution[row] += system.inverse[row][column] * right_hand_side[column];
    }
  }

  double residual = 0.0;
  for (std::size_t row = 0; row < 3U; ++row) {
    double reconstructed = 0.0;
    for (std::size_t column = 0; column < 3U; ++column) {
      reconstructed += system.matrix[row][column] * solution[column];
    }
    residual = std::max(residual,
                        std::abs(reconstructed - right_hand_side[row]));
  }
  const double matrix_norm = matrix_inf_norm(system.matrix);
  double solution_norm = 0.0;
  double rhs_norm = 0.0;
  for (std::size_t index = 0U; index < 3U; ++index) {
    solution_norm = std::max(solution_norm, std::abs(solution[index]));
    rhs_norm = std::max(rhs_norm, std::abs(right_hand_side[index]));
  }
  const double normalization = matrix_norm * solution_norm + rhs_norm;
  const double backward_error =
      normalization > 0.0 ? residual / normalization : 0.0;
  return LinearSolveResult{solution, system.condition_number, residual,
                           backward_error};
}

}  // namespace vv
