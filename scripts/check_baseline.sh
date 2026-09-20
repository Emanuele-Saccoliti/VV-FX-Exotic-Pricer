#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python_bin="${PYTHON_BIN:-python3}"

"$python_bin" -m pip install -e '.[dev]'
"$python_bin" -m pytest -q
cmake -S . -B build/baseline-cpp -DVV_BUILD_PYTHON=OFF -DVV_BUILD_TESTS=ON
cmake --build build/baseline-cpp
ctest --test-dir build/baseline-cpp --output-on-failure
MPLBACKEND=Agg "$python_bin" -m vv_pricer
