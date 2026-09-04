#!/usr/bin/env python3
"""Uniswap v4 历史收费分析的纯函数测试。"""

import unittest

from tests._path_setup import ensure_src_path

ensure_src_path()

from analysis.uniswap_v4_fee_analyzer import (
    ZERO_ADDRESS,
    _chunk_ranges,
    calculate_observed_residual,
    estimate_core_fee_raw,
    infer_swap_assets,
)


class TestUniswapV4FeeAnalyzer(unittest.TestCase):
    def test_chunk_ranges(self) -> None:
        self.assertEqual(list(_chunk_ranges(10, 25, 10)), [(10, 19), (20, 25)])

    def test_infer_swap_assets(self) -> None:
        currency0 = ZERO_ADDRESS
        currency1 = "0x1111111111111111111111111111111111111111"
        result = infer_swap_assets(100, -95, currency0, currency1)
        self.assertEqual(result, (currency0, currency1, 100, 95))

    def test_estimate_core_fee(self) -> None:
        self.assertEqual(estimate_core_fee_raw(1_000_000, 200_000), 166_666)

    def test_observed_input_residual(self) -> None:
        result = calculate_observed_residual(1_000, 900, 1_050, 900)
        self.assertEqual(result, (50, 0, 5.0))

    def test_observed_output_shortfall(self) -> None:
        result = calculate_observed_residual(1_000, 900, None, 855)
        self.assertEqual(result, (None, 45, 5.0))


if __name__ == "__main__":
    unittest.main()
