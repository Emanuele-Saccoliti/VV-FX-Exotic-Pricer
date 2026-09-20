"""Freeze the public v2 VV outputs before adding a multi-tenor surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import vv_cpp
from vv_pricer import DeltaConvention, SmileQuote, build_application


_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "vv_baseline_v2.json"
_BASELINE = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _assert_slice_fields(
    market_slice: Any,
    expected: dict[str, float],
    names: tuple[str, ...],
    tolerance: float,
) -> None:
    for name in names:
        assert getattr(market_slice, name) == pytest.approx(
            expected[name], abs=tolerance, rel=0
        )


def _assert_weight_fields(
    weights: Any, expected: dict[str, object], tolerance: float
) -> None:
    for name, actual in (
        ("weights_atm_rr_bf", weights.atm_rr_bf),
        ("weights_pillars", weights.pillars),
    ):
        assert list(actual) == pytest.approx(expected[name], abs=tolerance, rel=0)


def _assert_prices(
    pricer: Any,
    market_slice: Any,
    strike: float,
    expected: dict[str, float],
    tolerances: dict[str, float],
) -> None:
    for name, actual in (
        ("vv_call", pricer.price_vanilla(market_slice, True, strike)),
        ("vv_put", pricer.price_vanilla(market_slice, False, strike)),
    ):
        assert actual == pytest.approx(
            expected[name], abs=tolerances["vanilla_price"], rel=0
        )
    for name, actual in (
        ("digital_call", pricer.price_digital_call(market_slice, strike)),
        ("digital_put", pricer.price_digital_put(market_slice, strike)),
    ):
        assert actual == pytest.approx(
            expected[name], abs=tolerances["digital_price"], rel=0
        )


def test_cpp_extension_smoke() -> None:
    """The installed extension and public Python facade must agree on version."""
    from vv_pricer import __version__

    assert vv_cpp.__version__ == __version__ == "0.3.0"
    assert len(_BASELINE["cases"]) == len(DeltaConvention)


@pytest.mark.parametrize("case", _BASELINE["cases"], ids=lambda case: case["convention"])
def test_vv_baseline_regression(case: dict[str, object]) -> None:
    """Compare the original C++ results through the public Python API."""
    inputs = _BASELINE["input"]
    tolerances = _BASELINE["absolute_tolerances"]
    expected = case["expected"]
    quote = SmileQuote(
        T=inputs["maturity_years"],
        sigma_atm=inputs["sigma_atm_decimal"],
        rr25=inputs["rr25_decimal"],
        bf25=inputs["bf25_decimal"],
    )
    application = build_application(DeltaConvention[case["convention"]])
    market_slice = application.builder.build(
        inputs["spot"], inputs["domestic_rate"], inputs["foreign_rate"], quote
    )
    pricer = application.pricer
    strike = inputs["evaluation_strike"]
    weights = pricer.weights(market_slice, strike)

    _assert_slice_fields(
        market_slice, expected, ("sigma_25p", "sigma_atm", "sigma_25c"),
        tolerances["volatility"],
    )
    _assert_slice_fields(
        market_slice, expected, ("strike_25p", "strike_atm", "strike_25c"),
        tolerances["strike"],
    )
    _assert_weight_fields(weights, expected, tolerances["weight"])
    _assert_prices(pricer, market_slice, strike, expected, tolerances)
