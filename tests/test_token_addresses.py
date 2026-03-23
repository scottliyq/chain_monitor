#!/usr/bin/env python3
"""
测试地址常量模块的简单脚本
"""

import sys
import os
from _path_setup import ensure_src_path

ensure_src_path()

# 直接测试地址常量
from address_constant import TOKEN_CONTRACTS, USDT_CONTRACT_ADDRESS, USDC_CONTRACT_ADDRESS
from address_constant import get_token_address, get_all_usdt_addresses, get_all_usdc_addresses

print("🔍 测试多链代币地址常量")
print("=" * 60)

print(f"📊 以太坊主网:")
print(f"   USDT: {USDT_CONTRACT_ADDRESS}")
print(f"   USDC: {USDC_CONTRACT_ADDRESS}")

print(f"\n🌐 所有链的USDT地址:")
usdt_addresses = get_all_usdt_addresses()
for chain, address in usdt_addresses.items():
    print(f"   {chain.capitalize()}: {address}")

print(f"\n💰 所有链的USDC地址:")
usdc_addresses = get_all_usdc_addresses()
for chain_token, address in usdc_addresses.items():
    print(f"   {chain_token.replace('_', ' ').title()}: {address}")

print(f"\n🔧 测试辅助函数:")
test_cases = [
    ("ethereum", "USDT"),
    ("arbitrum", "USDT"),
    ("arbitrum", "USDC"),
    ("arbitrum", "USDC.e"),
    ("base", "USDC"),
    ("bsc", "USDT"),
    ("bsc", "USDC"),
]

for chain, token in test_cases:
    address = get_token_address(chain, token)
    print(f"   {chain.capitalize()} {token}: {address}")

print(f"\n📊 支持的链:")
for chain in TOKEN_CONTRACTS.keys():
    token_count = len([t for t, a in TOKEN_CONTRACTS[chain].items() if a != "0x0000000000000000000000000000000000000000"])
    print(f"   {chain.capitalize()}: {token_count} 个代币")

print(f"\n✅ 测试完成!")
