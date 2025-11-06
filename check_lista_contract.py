#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查Lista MEV合约的状态和权限
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
print("=" * 60)

# 加载ABI
abi_file = 'abi/bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json'
with open(abi_file, 'r') as f:
    abi_data = json.load(f)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_address),
    abi=abi_data['abi']
)

print("\n📊 合约状态检查:")
print("=" * 60)

# 1. 检查基本信息
try:
    name = contract.functions.name().call()
    symbol = contract.functions.symbol().call()
    print(f"✅ 合约名称: {name}")
    print(f"✅ 合约符号: {symbol}")
except Exception as e:
    print(f"❌ 获取基本信息失败: {e}")

# 2. 检查余额
try:
    balance = contract.functions.balanceOf(wallet_address).call()
    balance_formatted = w3.from_wei(balance, 'ether')
    print(f"✅ Shares余额: {balance_formatted:.6f}")
except Exception as e:
    print(f"❌ 获取余额失败: {e}")

# 3. 检查最大可取出
try:
    max_withdraw = contract.functions.maxWithdraw(wallet_address).call()
    max_withdraw_formatted = w3.from_wei(max_withdraw, 'ether')
    print(f"✅ 最大可取出: {max_withdraw_formatted:.6f}")
except Exception as e:
    print(f"❌ 获取最大可取出失败: {e}")

# 4. 检查maxRedeem
try:
    max_redeem = contract.functions.maxRedeem(wallet_address).call()
    max_redeem_formatted = w3.from_wei(max_redeem, 'ether')
    print(f"✅ 最大可赎回shares: {max_redeem_formatted:.6f}")
except Exception as e:
    print(f"❌ 获取最大可赎回失败: {e}")

# 5. 检查是否暂停
try:
    paused = contract.functions.paused().call()
    print(f"{'❌' if paused else '✅'} 合约暂停状态: {'已暂停' if paused else '未暂停'}")
except Exception as e:
    print(f"⚠️ 无法检查暂停状态: {e}")

# 6. 检查角色 (如果有的话)
try:
    # DEFAULT_ADMIN_ROLE
    default_admin_role = contract.functions.DEFAULT_ADMIN_ROLE().call()
    has_admin = contract.functions.hasRole(default_admin_role, wallet_address).call()
    print(f"{'✅' if has_admin else '❌'} DEFAULT_ADMIN_ROLE: {'有权限' if has_admin else '无权限'}")
except Exception as e:
    print(f"⚠️ 无法检查管理员角色: {e}")

# 7. 检查是否有WITHDRAWER角色
try:
    # 尝试常见的角色名称
    role_names = ['WITHDRAWER_ROLE', 'WITHDRAW_ROLE', 'USER_ROLE']
    for role_name in role_names:
        try:
            role = contract.functions[role_name]().call()
            has_role = contract.functions.hasRole(role, wallet_address).call()
            print(f"{'✅' if has_role else '❌'} {role_name}: {'有权限' if has_role else '无权限'}")
        except:
            pass
except Exception as e:
    print(f"⚠️ 角色检查跳过")

# 8. 检查资产兑换比例
try:
    # 尝试convertToAssets
    test_shares = w3.to_wei(1, 'ether')
    assets = contract.functions.convertToAssets(test_shares).call()
    assets_formatted = w3.from_wei(assets, 'ether')
    print(f"✅ 1 share = {assets_formatted:.6f} assets")
except Exception as e:
    print(f"⚠️ 无法获取兑换比例: {e}")

# 9. 检查提取资产需要的shares
try:
    test_assets = w3.to_wei(0.01, 'ether')
    shares = contract.functions.convertToShares(test_assets).call()
    shares_formatted = w3.from_wei(shares, 'ether')
    print(f"✅ 取出0.01 assets需要: {shares_formatted:.6f} shares")
except Exception as e:
    print(f"⚠️ 无法计算所需shares: {e}")

# 10. 尝试模拟withdraw调用
print(f"\n🔍 模拟withdraw调用:")
print("=" * 60)

try:
    test_amount = w3.to_wei(0.01, 'ether')
    
    # 尝试调用withdraw (只是模拟，不实际发送)
    result = contract.functions.withdraw(
        test_amount,
        Web3.to_checksum_address(wallet_address),
        Web3.to_checksum_address(wallet_address)
    ).call({'from': wallet_address})
    
    print(f"✅ withdraw模拟调用成功!")
    print(f"   返回值(shares): {w3.from_wei(result, 'ether'):.6f}")
    
except Exception as e:
    print(f"❌ withdraw模拟调用失败: {e}")
    print(f"   错误类型: {type(e).__name__}")
    
    # 如果是revert，尝试解析原因
    if hasattr(e, 'args') and len(e.args) > 0:
        print(f"   错误详情: {e.args[0]}")

# 11. 检查合约代码
print(f"\n📝 合约代码检查:")
print("=" * 60)
code = w3.eth.get_code(Web3.to_checksum_address(contract_address))
print(f"✅ 合约有代码: {len(code)} bytes")

# 12. 列出所有可用的函数
print(f"\n📋 合约函数列表:")
print("=" * 60)
functions = [item for item in abi_data['abi'] if item.get('type') == 'function']
print(f"总共 {len(functions)} 个函数")

# 只显示与withdraw相关的函数
withdraw_functions = [f for f in functions if 'withdraw' in f.get('name', '').lower()]
print(f"\n🔄 Withdraw相关函数 ({len(withdraw_functions)}):")
for func in withdraw_functions:
    name = func['name']
    inputs = func.get('inputs', [])
    input_str = ', '.join([f"{inp['type']} {inp['name']}" for inp in inputs])
    print(f"  - {name}({input_str})")
