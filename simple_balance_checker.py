#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版以太坊余额查询工具
使用Brownie框架但不需要完整项目结构

安装: pip install eth-brownie
使用: python simple_balance_checker.py
"""

import os
import sys
from decimal import Decimal

try:
    from brownie import network, Contract, web3
    print("✅ Brownie框架已导入")
except ImportError:
    print("❌ 请先安装Brownie框架:")
    print("pip install eth-brownie")
    sys.exit(1)

# 目标地址（我们之前分析的Concrete_STABLE）
TARGET_ADDRESS = "0x6503de9fe77d256d9d823f2d335ce83ece9e153f"

# USDT合约地址
USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# 简化的ERC20 ABI
ERC20_ABI = '''[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]'''

def connect_to_ethereum():
    """连接到以太坊主网"""
    try:
        # 检查是否已连接
        if network.is_connected():
            print(f"✅ 已连接到: {network.show_active()}")
            return True
        
        # 尝试连接到主网
        try:
            network.connect('mainnet')
            print(f"✅ 已连接到: {network.show_active()}")
            return True
        except:
            # 如果主网连接失败，尝试使用默认配置
            print("⚠️ 使用默认网络配置...")
            return True
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def get_eth_balance(address):
    """获取ETH余额"""
    try:
        balance_wei = web3.eth.get_balance(address)
        balance_eth = web3.from_wei(balance_wei, 'ether')
        return float(balance_eth)
    except Exception as e:
        print(f"⚠️ 获取ETH余额失败: {e}")
        return 0.0

def get_usdt_balance(address):
    """获取USDT余额"""
    try:
        # 创建USDT合约实例
        usdt_contract = Contract.from_abi("USDT", USDT_CONTRACT, ERC20_ABI)
        
        # 获取余额
        balance_wei = usdt_contract.balanceOf(address)
        
        # USDT是6位小数
        balance = balance_wei / (10 ** 6)
        return float(balance)
        
    except Exception as e:
        print(f"⚠️ 获取USDT余额失败: {e}")
        return 0.0

def check_address_balance(address):
    """检查指定地址的余额"""
    print(f"\n📊 查询地址: {address}")
    print("=" * 60)
    
    # 获取ETH余额
    eth_balance = get_eth_balance(address)
    print(f"💰 ETH余额: {eth_balance:.6f} ETH")
    
    # 获取USDT余额
    usdt_balance = get_usdt_balance(address)
    print(f"💰 USDT余额: {usdt_balance:,.2f} USDT")
    
    # 获取当前区块信息
    try:
        current_block = web3.eth.block_number
        print(f"📊 当前区块: {current_block:,}")
    except:
        pass
    
    print(f"🔗 Etherscan: https://etherscan.io/address/{address}")
    
    return {
        'address': address,
        'eth_balance': eth_balance,
        'usdt_balance': usdt_balance
    }

def main():
    """主函数"""
    print("🚀 Brownie以太坊余额查询工具 - 简化版")
    print("=" * 50)
    
    # 连接到以太坊
    if not connect_to_ethereum():
        print("❌ 无法连接到以太坊网络")
        return
    
    try:
        # 查询预设地址
        print(f"\n1️⃣ 查询Concrete_STABLE合约地址余额")
        result1 = check_address_balance(TARGET_ADDRESS)
        
        # 交互式查询
        print(f"\n2️⃣ 自定义地址查询")
        custom_address = input("请输入要查询的地址 (回车跳过): ").strip()
        
        if custom_address:
            if not custom_address.startswith('0x') or len(custom_address) != 42:
                print("⚠️ 地址格式不正确，应为42位十六进制字符串")
            else:
                result2 = check_address_balance(custom_address)
        
        # 比较多个地址（示例）
        print(f"\n3️⃣ 批量查询示例地址")
        example_addresses = [
            "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Binance
            "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Curve
        ]
        
        results = []
        for addr in example_addresses:
            result = check_address_balance(addr)
            results.append(result)
        
        # 显示汇总
        print(f"\n📈 查询汇总")
        print("=" * 60)
        all_results = [result1] + results
        
        total_eth = sum(r['eth_balance'] for r in all_results)
        total_usdt = sum(r['usdt_balance'] for r in all_results)
        
        print(f"📊 总计查询地址: {len(all_results)}")
        print(f"💰 总ETH余额: {total_eth:.6f} ETH")
        print(f"💰 总USDT余额: {total_usdt:,.2f} USDT")
        
        # 排序显示
        print(f"\n🏆 按USDT余额排序:")
        sorted_results = sorted(all_results, key=lambda x: x['usdt_balance'], reverse=True)
        for i, result in enumerate(sorted_results, 1):
            addr = result['address']
            usdt = result['usdt_balance']
            print(f"   {i}. {addr[:10]}...{addr[-6:]}: {usdt:,.2f} USDT")
    
    except KeyboardInterrupt:
        print(f"\n👋 查询已停止")
    
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 断开连接
        try:
            if network.is_connected():
                network.disconnect()
                print(f"\n👋 已断开网络连接")
        except:
            pass

if __name__ == "__main__":
    main()