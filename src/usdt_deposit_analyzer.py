#!/usr/bin/env python3
"""历史兼容 shim。"""

from analysis.token_deposit_analyzer import TokenDepositAnalyzer, TokenDepositAnalyzer as USDTDepositAnalyzer

__all__ = ["TokenDepositAnalyzer", "USDTDepositAnalyzer"]
