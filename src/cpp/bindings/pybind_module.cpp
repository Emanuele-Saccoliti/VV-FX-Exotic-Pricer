#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cstddef>
#include <span>
#include <string>
#include <vector>

#include "vv/analytic_greeks.hpp"
#include "vv/finite_difference_greeks.hpp"
#include "vv/garman_kohlhagen.hpp"
#include "vv/types.hpp"
#include "vv/vanna_volga_engine.hpp"
#include "vv/version.hpp"

namespace py = pybind11;

PYBIND11_MODULE(vv_cpp, module) {
  module.doc() = "C++ quantitative backend for the hybrid Vanna-Volga pricer";
  module.attr("__version__") = std::string{vv::version};

  py::enum_<vv::DeltaConvention>(module, "DeltaConvention")
      .value("SPOT_PREM_EXCLUDED",
             vv::DeltaConvention::SpotPremiumExcluded)
      .value("FWD_PREM_EXCLUDED",
             vv::DeltaConvention::ForwardPremiumExcluded)
      .value("SPOT_PREM_INCLUDED", vv::DeltaConvention::SpotPremiumIncluded)
      .export_values();

  py::enum_<vv::OptionType>(module, "OptionType")
      .value("CALL", vv::OptionType::Call)
      .value("PUT", vv::OptionType::Put)
      .export_values();

  py::class_<vv::SmileQuote>(module, "SmileQuote")
      .def(py::init<double, double, double, double>(), py::arg("maturity"),
           py::arg("sigma_atm"), py::arg("rr25"), py::arg("bf25"))
      .def_readwrite("maturity", &vv::SmileQuote::maturity)
      .def_readwrite("sigma_atm", &vv::SmileQuote::sigma_atm)
      .def_readwrite("rr25", &vv::SmileQuote::rr25)
      .def_readwrite("bf25", &vv::SmileQuote::bf25);

  py::class_<vv::MarketSlice>(module, "MarketSlice")
      .def_readonly("spot", &vv::MarketSlice::spot)
      .def_readonly("domestic_rate", &vv::MarketSlice::domestic_rate)
      .def_readonly("foreign_rate", &vv::MarketSlice::foreign_rate)
      .def_readonly("maturity", &vv::MarketSlice::maturity)
      .def_readonly("sigma_atm", &vv::MarketSlice::sigma_atm)
      .def_readonly("sigma_25p", &vv::MarketSlice::sigma_25p)
      .def_readonly("sigma_25c", &vv::MarketSlice::sigma_25c)
      .def_readonly("strike_atm", &vv::MarketSlice::strike_atm)
      .def_readonly("strike_25p", &vv::MarketSlice::strike_25p)
      .def_readonly("strike_25c", &vv::MarketSlice::strike_25c)
      .def_readonly("delta_convention", &vv::MarketSlice::delta_convention)
      .def_property_readonly(
          "condition_number", [](const vv::MarketSlice& market_slice) {
            return market_slice.greek_system.condition_number;
          });

  py::class_<vv::Greeks>(module, "Greeks")
      .def_readonly("vega", &vv::Greeks::vega)
      .def_readonly("vanna", &vv::Greeks::vanna)
      .def_readonly("volga", &vv::Greeks::volga);

  py::class_<vv::WeightResult>(module, "WeightResult")
      .def_readonly("atm_rr_bf", &vv::WeightResult::atm_rr_bf)
      .def_readonly("pillars", &vv::WeightResult::pillars)
      .def_readonly("condition_number", &vv::WeightResult::condition_number)
      .def_readonly("residual_inf_norm",
                    &vv::WeightResult::residual_inf_norm)
      .def_readonly("backward_error", &vv::WeightResult::backward_error);

  py::class_<vv::ArbitrageDiagnostics>(module, "ArbitrageDiagnostics")
      .def_readonly("points", &vv::ArbitrageDiagnostics::points)
      .def_readonly("within_bounds",
                    &vv::ArbitrageDiagnostics::within_bounds)
      .def_readonly("monotonic", &vv::ArbitrageDiagnostics::monotonic)
      .def_readonly("convex", &vv::ArbitrageDiagnostics::convex)
      .def_readonly("lower_bound_violations",
                    &vv::ArbitrageDiagnostics::lower_bound_violations)
      .def_readonly("upper_bound_violations",
                    &vv::ArbitrageDiagnostics::upper_bound_violations)
      .def_readonly("monotonicity_violations",
                    &vv::ArbitrageDiagnostics::monotonicity_violations)
      .def_readonly("convexity_violations",
                    &vv::ArbitrageDiagnostics::convexity_violations)
      .def_readonly("worst_lower_bound_excess",
                    &vv::ArbitrageDiagnostics::worst_lower_bound_excess)
      .def_readonly("worst_upper_bound_excess",
                    &vv::ArbitrageDiagnostics::worst_upper_bound_excess)
      .def_readonly("worst_monotonicity_excess",
                    &vv::ArbitrageDiagnostics::worst_monotonicity_excess)
      .def_readonly("worst_convexity_excess",
                    &vv::ArbitrageDiagnostics::worst_convexity_excess);

  py::class_<vv::DigitalBoundsDiagnostics>(module,
                                           "DigitalBoundsDiagnostics")
      .def_readonly("points", &vv::DigitalBoundsDiagnostics::points)
      .def_readonly("within_bounds",
                    &vv::DigitalBoundsDiagnostics::within_bounds)
      .def_readonly("lower_bound_violations",
                    &vv::DigitalBoundsDiagnostics::lower_bound_violations)
      .def_readonly("upper_bound_violations",
                    &vv::DigitalBoundsDiagnostics::upper_bound_violations)
      .def_readonly("worst_lower_bound_excess",
                    &vv::DigitalBoundsDiagnostics::worst_lower_bound_excess)
      .def_readonly("worst_upper_bound_excess",
                    &vv::DigitalBoundsDiagnostics::worst_upper_bound_excess);

  py::class_<vv::ParityDiagnostics>(module, "ParityDiagnostics")
      .def_readonly("passed", &vv::ParityDiagnostics::passed)
      .def_readonly("actual", &vv::ParityDiagnostics::actual)
      .def_readonly("expected", &vv::ParityDiagnostics::expected)
      .def_readonly("absolute_error", &vv::ParityDiagnostics::absolute_error)
      .def_readonly("normalized_error",
                    &vv::ParityDiagnostics::normalized_error);

  py::class_<vv::VannaVolgaEngine>(module, "VannaVolgaEngine")
      .def(py::init<vv::DeltaConvention>(),
           py::arg("delta_convention") =
               vv::DeltaConvention::SpotPremiumExcluded)
      .def(
          "build_slice",
          [](const vv::VannaVolgaEngine& engine, const double spot,
             const double domestic_rate, const double foreign_rate,
             const vv::SmileQuote& quote) {
            py::gil_scoped_release release;
            return engine.build_slice(spot, domestic_rate, foreign_rate, quote);
          },
          py::arg("spot"), py::arg("domestic_rate"),
          py::arg("foreign_rate"), py::arg("quote"))
      .def("greeks", &vv::VannaVolgaEngine::greeks,
           py::arg("market_slice"), py::arg("strike"),
           py::arg("volatility"))
      .def(
          "greeks_batch",
          [](const vv::VannaVolgaEngine& engine,
             const vv::MarketSlice& market_slice,
             const py::array_t<double,
                               py::array::c_style | py::array::forcecast>&
                 strikes,
             const double volatility) {
            if (strikes.ndim() != 1) {
              throw py::value_error("strikes must be one-dimensional");
            }
            const std::size_t count =
                static_cast<std::size_t>(strikes.size());
            std::vector<vv::Greeks> result;
            {
              py::gil_scoped_release release;
              result = engine.greeks_batch(
                  market_slice,
                  std::span<const double>(strikes.data(), count), volatility);
            }
            py::array_t<double> output(
                {static_cast<py::ssize_t>(count), static_cast<py::ssize_t>(3)});
            double* data = output.mutable_data();
            for (std::size_t index = 0U; index < count; ++index) {
              data[3U * index] = result[index].vega;
              data[3U * index + 1U] = result[index].vanna;
              data[3U * index + 2U] = result[index].volga;
            }
            return output;
          },
          py::arg("market_slice"), py::arg("strikes"),
          py::arg("volatility"))
      .def("weights", &vv::VannaVolgaEngine::weights,
           py::arg("market_slice"), py::arg("strike"),
           py::call_guard<py::gil_scoped_release>())
      .def("price_vanilla", &vv::VannaVolgaEngine::price_vanilla,
           py::arg("market_slice"), py::arg("option_type"),
           py::arg("strike"), py::call_guard<py::gil_scoped_release>())
      .def(
          "price_vanilla_batch",
          [](const vv::VannaVolgaEngine& engine,
             const vv::MarketSlice& market_slice,
             const vv::OptionType option_type,
             const py::array_t<double,
                               py::array::c_style | py::array::forcecast>&
                 strikes) {
            if (strikes.ndim() != 1) {
              throw py::value_error("strikes must be one-dimensional");
            }
            const std::size_t count =
                static_cast<std::size_t>(strikes.size());
            std::vector<double> result;
            {
              py::gil_scoped_release release;
              result = engine.price_vanilla_batch(
                  market_slice, option_type,
                  std::span<const double>(strikes.data(), count));
            }
            py::array_t<double> output(static_cast<py::ssize_t>(count));
            std::copy(result.begin(), result.end(), output.mutable_data());
            return output;
          },
          py::arg("market_slice"), py::arg("option_type"),
          py::arg("strikes"))
      .def("price_digital", &vv::VannaVolgaEngine::price_digital,
           py::arg("market_slice"), py::arg("option_type"),
           py::arg("strike"), py::call_guard<py::gil_scoped_release>())
      .def(
          "check_arbitrage",
          [](const vv::VannaVolgaEngine& engine,
             const vv::MarketSlice& market_slice,
             const vv::OptionType option_type,
             const py::array_t<double,
                               py::array::c_style | py::array::forcecast>&
                 strikes) {
            if (strikes.ndim() != 1) {
              throw py::value_error("strikes must be one-dimensional");
            }
            const std::size_t count =
                static_cast<std::size_t>(strikes.size());
            py::gil_scoped_release release;
            return engine.check_arbitrage(
                market_slice, option_type,
                std::span<const double>(strikes.data(), count));
          },
          py::arg("market_slice"), py::arg("option_type"),
          py::arg("strikes"))
      .def(
          "check_digital_bounds",
          [](const vv::VannaVolgaEngine& engine,
             const vv::MarketSlice& market_slice,
             const vv::OptionType option_type,
             const py::array_t<double,
                               py::array::c_style | py::array::forcecast>&
                 strikes) {
            if (strikes.ndim() != 1) {
              throw py::value_error("strikes must be one-dimensional");
            }
            const std::size_t count =
                static_cast<std::size_t>(strikes.size());
            py::gil_scoped_release release;
            return engine.check_digital_bounds(
                market_slice, option_type,
                std::span<const double>(strikes.data(), count));
          },
          py::arg("market_slice"), py::arg("option_type"),
          py::arg("strikes"))
      .def("check_put_call_parity",
           &vv::VannaVolgaEngine::check_put_call_parity,
           py::arg("market_slice"), py::arg("strike"),
           py::call_guard<py::gil_scoped_release>())
      .def("check_digital_parity",
           &vv::VannaVolgaEngine::check_digital_parity,
           py::arg("market_slice"), py::arg("strike"),
           py::call_guard<py::gil_scoped_release>())
      .def("implied_volatility", &vv::VannaVolgaEngine::implied_volatility,
           py::arg("market_slice"), py::arg("option_type"),
           py::arg("strike"), py::arg("target_price"),
           py::arg("vol_low") = 0.0, py::arg("vol_high") = 0.0,
           py::call_guard<py::gil_scoped_release>())
      .def_property_readonly("delta_convention",
                             &vv::VannaVolgaEngine::delta_convention);

  module.def("gk_price", &vv::gk_price, py::arg("option_type"),
             py::arg("spot"), py::arg("strike"), py::arg("maturity"),
             py::arg("domestic_rate"), py::arg("foreign_rate"),
             py::arg("volatility"));
  module.def("gk_delta", &vv::gk_delta, py::arg("delta_convention"),
             py::arg("option_type"), py::arg("spot"), py::arg("strike"),
             py::arg("maturity"), py::arg("domestic_rate"),
             py::arg("foreign_rate"), py::arg("volatility"));
  module.def("analytic_greeks", &vv::analytic_greeks, py::arg("spot"),
             py::arg("strike"), py::arg("maturity"),
             py::arg("domestic_rate"), py::arg("foreign_rate"),
             py::arg("volatility"));
  module.def("finite_difference_greeks", &vv::finite_difference_greeks,
             py::arg("spot"), py::arg("strike"), py::arg("maturity"),
             py::arg("domestic_rate"), py::arg("foreign_rate"),
             py::arg("volatility"));
}
