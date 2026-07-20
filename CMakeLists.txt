cmake_minimum_required(VERSION 3.20)
project(vv_hybrid_pricer VERSION 0.3.0 LANGUAGES CXX)

option(VV_BUILD_PYTHON "Build the vv_cpp Python extension" ON)
option(VV_BUILD_TESTS "Build the C++ quantitative tests" ON)

add_library(vv_compile_options INTERFACE)
target_compile_features(vv_compile_options INTERFACE cxx_std_20)
if(MSVC)
  target_compile_options(vv_compile_options INTERFACE /W4 /WX)
else()
  target_compile_options(
    vv_compile_options
    INTERFACE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror
  )
endif()

add_library(
  vv_core STATIC
  src/cpp/src/analytic_greeks.cpp
  src/cpp/src/arbitrage_checks.cpp
  src/cpp/src/finite_difference_greeks.cpp
  src/cpp/src/garman_kohlhagen.cpp
  src/cpp/src/linear_solver.cpp
  src/cpp/src/market_slice.cpp
  src/cpp/src/vanna_volga_engine.cpp
)
set_target_properties(vv_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_link_libraries(vv_core PUBLIC vv_compile_options)
target_include_directories(vv_core PUBLIC src/cpp/include)

if(VV_BUILD_PYTHON)
  find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(vv_cpp src/cpp/bindings/pybind_module.cpp)
  target_link_libraries(vv_cpp PRIVATE vv_core)
  target_include_directories(vv_cpp PRIVATE src/cpp/include)
  install(TARGETS vv_cpp LIBRARY DESTINATION . RUNTIME DESTINATION .)
endif()

if(VV_BUILD_TESTS)
  enable_testing()

  add_executable(vv_gk_test tests/cpp/test_garman_kohlhagen.cpp)
  target_link_libraries(vv_gk_test PRIVATE vv_core)
  add_test(NAME vv_gk_test COMMAND vv_gk_test)

  add_executable(vv_engine_test tests/cpp/test_vanna_volga_engine.cpp)
  target_link_libraries(vv_engine_test PRIVATE vv_core)
  add_test(NAME vv_engine_test COMMAND vv_engine_test)
endif()
