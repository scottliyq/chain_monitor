#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 withdrawQueue 状态
"""

import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# BSC RPC
rpc_url = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed1.binance.org')
w3 = Web3(Web3.HTTPProvider(rpc_url))

# 合约地址
contract_address = "0x6402d64F035E18F9834591d3B994dFe41a0f162D"

# 加载ABI
abi_file = 'abi/bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json'
with open(abi_file, 'r') as f:
    abi_data = json.load(f)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_address),
    abi=abi_data['abi']
)

print("🔍 检查 WithdrawQueue:")
print("=" * 60)

# 获取 withdrawQueue 长度
try:
    queue_length = contract.functions.withdrawQueueLength().call()
    print(f"✅ WithdrawQueue 长度: {queue_length}")
    
    # 获取队列中的策略
    print(f"\n📋 WithdrawQueue 内容:")
    for i in range(queue_length):
        try:
            strategy = contract.functions.withdrawQueue(i).call()
            print(f"   索引 {i}: {strategy}")
        except Exception as e:
            print(f"   索引 {i}: 读取失败 - {e}")
            
except Exception as e:
    print(f"❌ 获取 withdrawQueue 失败: {e}")

# 尝试查看totalAssets和totalSupply
print(f"\n📊 合约总体状态:")
print("=" * 60)

try:
    total_assets = contract.functions.totalAssets().call()
    total_assets_formatted = w3.from_wei(total_assets, 'ether')
    print(f"✅ 总资产: {total_assets_formatted:.2f}")
except Exception as e:
    print(f"❌ 获取总资产失败: {e}")

try:
    total_supply = contract.functions.totalSupply().call()
    total_supply_formatted = w3.from_wei(total_supply, 'ether')
    print(f"✅ 总供应量: {total_supply_formatted:.2f}")
except Exception as e:
    print(f"❌ 获取总供应量失败: {e}")

# 计算比例
try:
    if total_supply > 0:
        ratio = total_assets / total_supply
        print(f"✅ 资产/供应比例: {ratio:.6f}")
        print(f"   (每个share价值 {ratio:.6f} assets)")
except:
    pass
