from __future__ import annotations

import argparse

from .conventions import DeltaConvention
from .demo import run_demo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the hybrid Python/C++ Vanna-Volga FX pricer."
    )
    parser.add_argument(
        "convention",
        nargs="?",
        default=None,
        help="FX delta convention (default: SPOT_PREM_EXCLUDED).",
    )
    parser.add_argument(
        "--plots",
        action="store_true",
        help="Display the smile, VV surfaces and analytic Greek profiles.",
    )
    args = parser.parse_args()
    run_demo(DeltaConvention.parse(args.convention), show_plots=args.plots)
    return 0
