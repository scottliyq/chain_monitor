#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深入分析 gas 估算失败的原因
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

# 加载私钥
private_key = os.getenv('WALLET_PRIVATE_KEY')
if not private_key.startswith('0x'):
    private_key = '0x' + private_key

account = Account.from_key(private_key)
wallet_address = account.address

print(f"💼 钱包地址: {wallet_address}")
print("=" * 80)

# 加载ABI
abi_file = 'abi/bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json'
with open(abi_file, 'r') as f:
    abi_data = json.load(f)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_address),
    abi=abi_data['abi']
)

print("\n🔍 测试不同的调用方式:")
print("=" * 80)

# 测试金额
test_amount = w3.to_wei(0.001, 'ether')

# 1. staticCall (view call)
print("\n1️⃣ 测试 staticCall (view call) - 只读调用，不改变状态:")
try:
    result = contract.functions.withdraw(
        test_amount,
        Web3.to_checksum_address(wallet_address),
        Web3.to_checksum_address(wallet_address)
    ).call({'from': wallet_address})
    
    print(f"   ✅ call() 成功")
    print(f"   返回值: {w3.from_wei(result, 'ether'):.6f} shares")
except Exception as e:
    print(f"   ❌ call() 失败: {e}")

# 2. 使用不同的 gas 值测试 estimate_gas
print("\n2️⃣ 测试 estimate_gas 使用不同的初始gas值:")

nonce = w3.eth.get_transaction_count(wallet_address)
gas_price = w3.eth.gas_price

for gas_limit in [100000, 200000, 300000, 500000, 1000000, 2000000]:
    print(f"\n   Gas Limit: {gas_limit}")
    try:
        tx = contract.functions.withdraw(
            test_amount,
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(wallet_address)
        ).build_transaction({
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': 56
        })
        
        estimated_gas = w3.eth.estimate_gas(tx)
        print(f"   ✅ estimate_gas 成功: {estimated_gas}")
        break
    except Exception as e:
        print(f"   ❌ estimate_gas 失败: {e}")

# 3. 不指定 gas 参数
print("\n3️⃣ 测试 estimate_gas 不指定gas参数:")
try:
    tx_no_gas = contract.functions.withdraw(
        test_amount,
        Web3.to_checksum_address(wallet_address),
        Web3.to_checksum_address(wallet_address)
    ).build_transaction({
        'from': wallet_address,
        'nonce': nonce,
        'gasPrice': gas_price,
        'chainId': 56
    })
    
    estimated_gas = w3.eth.estimate_gas(tx_no_gas)
    print(f"   ✅ estimate_gas 成功: {estimated_gas}")
except Exception as e:
    print(f"   ❌ estimate_gas 失败: {e}")

# 4. 使用 eth_call 直接测试
print("\n4️⃣ 测试直接使用 eth_call RPC:")
try:
    # 编码函数调用
    call_data = contract.functions.withdraw(
        test_amount,
        Web3.to_checksum_address(wallet_address),
        Web3.to_checksum_address(wallet_address)
    ).build_transaction({
        'from': wallet_address,
        'to': contract_address,
        'gas': 0,
        'gasPrice': 0,
        'value': 0,
        'nonce': 0,
        'chainId': 56
    })
    
    result = w3.eth.call({
        'from': wallet_address,
        'to': contract_address,
        'data': call_data['data']
    })
    print(f"   ✅ eth_call 成功")
    print(f"   返回数据: {result.hex()}")
except Exception as e:
    print(f"   ❌ eth_call 失败: {e}")

# 5. 测试 estimateGas RPC
print("\n5️⃣ 测试 eth_estimateGas RPC:")
try:
    call_data = contract.functions.withdraw(
        test_amount,
        Web3.to_checksum_address(wallet_address),
        Web3.to_checksum_address(wallet_address)
    ).build_transaction({
        'from': wallet_address,
        'to': contract_address,
        'gas': 0,
        'gasPrice': 0,
        'value': 0,
        'nonce': 0,
        'chainId': 56
    })
    
    gas = w3.eth.estimate_gas({
        'from': wallet_address,
        'to': contract_address,
        'data': call_data['data']
    })
    print(f"   ✅ eth_estimateGas 成功: {gas}")
except Exception as e:
    print(f"   ❌ eth_estimateGas 失败: {e}")

# 6. 检查当前区块的 gas limit
print("\n6️⃣ 检查区块信息:")
try:
    latest_block = w3.eth.get_block('latest')
    print(f"   最新区块号: {latest_block['number']}")
    print(f"   区块 Gas Limit: {latest_block['gasLimit']:,}")
    print(f"   区块 Gas Used: {latest_block['gasUsed']:,}")
    print(f"   剩余可用 Gas: {latest_block['gasLimit'] - latest_block['gasUsed']:,}")
except Exception as e:
    print(f"   ❌ 获取区块信息失败: {e}")

# 7. 测试更小的金额
print("\n7️⃣ 测试更小的金额:")
for amount in [0.0001, 0.00001, 0.000001]:
    print(f"\n   测试金额: {amount}")
    test_amt = w3.to_wei(amount, 'ether')
    
    # 先测试 call
    try:
        result = contract.functions.withdraw(
            test_amt,
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(wallet_address)
        ).call({'from': wallet_address})
        print(f"   ✅ call() 成功: {w3.from_wei(result, 'ether'):.9f} shares")
    except Exception as e:
        print(f"   ❌ call() 失败: {e}")
        continue
    
    # 测试 estimate_gas
    try:
        gas = w3.eth.estimate_gas({
            'from': wallet_address,
            'to': contract_address,
            'data': contract.encode_abi(
                fn_name='withdraw',
                args=[test_amt, Web3.to_checksum_address(wallet_address), Web3.to_checksum_address(wallet_address)]
            )
        })
        print(f"   ✅ estimate_gas 成功: {gas}")
    except Exception as e:
        print(f"   ❌ estimate_gas 失败: {e}")

# 8. 检查账户状态
print("\n8️⃣ 检查账户状态:")
try:
    balance = w3.eth.get_balance(wallet_address)
    print(f"   BNB余额: {w3.from_wei(balance, 'ether'):.6f} BNB")
    
    nonce = w3.eth.get_transaction_count(wallet_address)
    print(f"   Nonce: {nonce}")
    
    code = w3.eth.get_code(wallet_address)
    if len(code) > 2:
        print(f"   ⚠️ 这是一个合约地址，不是EOA")
    else:
        print(f"   ✅ 这是一个EOA地址")
except Exception as e:
    print(f"   ❌ 检查账户失败: {e}")

print("\n" + "=" * 80)
print("📊 分析结论:")
print("=" * 80)
print("如果 call() 成功但 estimate_gas 失败，可能的原因：")
print("1. call() 不会检查某些状态变化的限制（如重入保护、时间锁等）")
print("2. estimate_gas 会模拟完整的交易执行，包括所有状态检查")
print("3. 合约可能有 view/pure 函数不检查但实际交易会检查的条件")
print("4. 可能需要更高的 gas limit 才能估算成功")
