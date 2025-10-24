#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Brownie连接mainnet-fork的示例程序
需要先启动Ganache分叉: ./start_ganache_fork.sh

功能:
1. 连接到mainnet-fork网络
2. 查询真实主网数据（通过分叉）
3. 可以进行交易模拟而不花费真实ETH
"""

import os
import sys
from decimal import Decimal

try:
    from brownie import network, accounts, Contract, web3, Wei
    print("✅ Brownie框架已导入")
except ImportError:
    print("❌ 请先安装Brownie框架:")
    print("pip install eth-brownie")
    sys.exit(1)

# 目标合约地址
TARGET_ADDRESS = "0x6503de9fe77d256d9d823f2d335ce83ece9e153f"
USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDC_CONTRACT = "0xA0b86a33E6441b57ee3e4BEd34CE66fcEe8d5c4"

# ERC20 ABI
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
    },
    {
        "constant": true,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]'''

def connect_to_mainnet_fork():
    """连接到mainnet-fork网络"""
    try:
        # 检查是否已连接
        if network.is_connected():
            current_network = network.show_active()
            print(f"✅ 已连接到: {current_network}")
            if current_network == 'mainnet-fork':
                return True
            else:
                print(f"⚠️ 当前连接到 {current_network}，正在切换到 mainnet-fork...")
                network.disconnect()
        
        # 连接到mainnet-fork
        network.connect('mainnet-fork')
        print(f"✅ 已连接到: {network.show_active()}")
        
        # 验证连接
        chain_id = web3.eth.chain_id
        block_number = web3.eth.block_number
        print(f"📊 链ID: {chain_id}")
        print(f"📊 当前区块: {block_number:,}")
        
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"💡 请确保:")
        print(f"   1. 已启动Ganache分叉: ./start_ganache_fork.sh")
        print(f"   2. brownie-config.yaml中配置了mainnet-fork网络")
        return False

def get_fork_accounts():
    """获取分叉网络中的测试账户"""
    try:
        print(f"\n🔑 测试账户信息:")
        print("=" * 50)
        
        # 获取所有账户
        test_accounts = accounts
        
        for i, account in enumerate(test_accounts[:5]):  # 只显示前5个
            balance = account.balance()
            balance_eth = web3.from_wei(balance, 'ether')
            print(f"账户 {i}: {account.address}")
            print(f"   余额: {balance_eth:.2f} ETH")
        
        print(f"总账户数: {len(test_accounts)}")
        return test_accounts
        
    except Exception as e:
        print(f"⚠️ 获取账户失败: {e}")
        return []

def query_mainnet_data():
    """查询主网数据（通过分叉）"""
    print(f"\n📊 查询主网数据:")
    print("=" * 50)
    
    try:
        # 查询目标地址ETH余额
        target_balance = web3.eth.get_balance(TARGET_ADDRESS)
        target_eth = web3.from_wei(target_balance, 'ether')
        print(f"🎯 目标合约ETH余额: {target_eth:.6f} ETH")
        print(f"   地址: {TARGET_ADDRESS}")
        
        # 查询USDT合约信息
        usdt = Contract.from_abi("USDT", USDT_CONTRACT, ERC20_ABI)
        usdt_name = usdt.name()
        usdt_symbol = usdt.symbol()
        usdt_decimals = usdt.decimals()
        print(f"\n💰 USDT合约信息:")
        print(f"   名称: {usdt_name}")
        print(f"   符号: {usdt_symbol}")
        print(f"   小数位: {usdt_decimals}")
        print(f"   地址: {USDT_CONTRACT}")
        
        # 查询目标地址的USDT余额
        usdt_balance = usdt.balanceOf(TARGET_ADDRESS)
        usdt_amount = usdt_balance / (10 ** usdt_decimals)
        print(f"   目标地址USDT余额: {usdt_amount:,.2f} USDT")
        
        # 查询USDC合约信息
        usdc = Contract.from_abi("USDC", USDC_CONTRACT, ERC20_ABI)
        usdc_balance = usdc.balanceOf(TARGET_ADDRESS)
        usdc_decimals = usdc.decimals()
        usdc_amount = usdc_balance / (10 ** usdc_decimals)
        print(f"\n💎 USDC余额: {usdc_amount:,.2f} USDC")
        
        return {
            'eth_balance': target_eth,
            'usdt_balance': usdt_amount,
            'usdc_balance': usdc_amount,
            'usdt_contract': usdt,
            'usdc_contract': usdc
        }
        
    except Exception as e:
        print(f"⚠️ 查询数据失败: {e}")
        return None

def simulate_transaction():
    """模拟交易示例"""
    print(f"\n🧪 交易模拟示例:")
    print("=" * 50)
    
    try:
        # 获取测试账户
        test_accounts = accounts
        if not test_accounts:
            print("❌ 没有可用的测试账户")
            return
        
        sender = test_accounts[0]
        receiver = test_accounts[1]
        
        print(f"📤 发送方: {sender.address}")
        print(f"📥 接收方: {receiver.address}")
        
        # 发送方初始余额
        sender_balance_before = sender.balance()
        receiver_balance_before = receiver.balance()
        
        print(f"\n💰 转账前余额:")
        print(f"   发送方: {web3.from_wei(sender_balance_before, 'ether'):.2f} ETH")
        print(f"   接收方: {web3.from_wei(receiver_balance_before, 'ether'):.2f} ETH")
        
        # 发送1 ETH
        amount = Wei('1 ether')
        print(f"\n🔄 模拟转账 1 ETH...")
        
        # 执行转账
        tx = sender.transfer(receiver, amount)
        print(f"✅ 交易成功!")
        print(f"   交易哈希: {tx.txid}")
        print(f"   Gas使用: {tx.gas_used:,}")
        print(f"   Gas价格: {tx.gas_price:,} wei")
        
        # 转账后余额
        sender_balance_after = sender.balance()
        receiver_balance_after = receiver.balance()
        
        print(f"\n💰 转账后余额:")
        print(f"   发送方: {web3.from_wei(sender_balance_after, 'ether'):.2f} ETH")
        print(f"   接收方: {web3.from_wei(receiver_balance_after, 'ether'):.2f} ETH")
        
        # 验证余额变化
        sender_diff = web3.from_wei(sender_balance_after - sender_balance_before, 'ether')
        receiver_diff = web3.from_wei(receiver_balance_after - receiver_balance_before, 'ether')
        
        print(f"\n📊 余额变化:")
        print(f"   发送方: {sender_diff:.6f} ETH")
        print(f"   接收方: {receiver_diff:.6f} ETH")
        
    except Exception as e:
        print(f"⚠️ 交易模拟失败: {e}")

def interactive_mode():
    """交互模式"""
    while True:
        print(f"\n🔧 操作选项:")
        print("1. 查询主网数据")
        print("2. 查看测试账户")  
        print("3. 模拟ETH转账")
        print("4. 查看网络状态")
        print("5. 退出")
        
        choice = input("\n请选择操作 (1-5): ").strip()
        
        if choice == '1':
            query_mainnet_data()
        elif choice == '2':
            get_fork_accounts()
        elif choice == '3':
            simulate_transaction()
        elif choice == '4':
            print(f"\n🌐 网络状态:")
            print(f"   当前网络: {network.show_active()}")
            print(f"   链ID: {web3.eth.chain_id}")
            print(f"   当前区块: {web3.eth.block_number:,}")
            print(f"   Gas价格: {web3.eth.gas_price:,} wei")
        elif choice == '5':
            break
        else:
            print("❌ 无效选择")

def main():
    """主函数"""
    print("🚀 Brownie Mainnet-Fork 程序")
    print("=" * 40)
    
    # 连接到mainnet-fork
    if not connect_to_mainnet_fork():
        return
    
    try:
        # 获取测试账户
        test_accounts = get_fork_accounts()
        
        # 查询主网数据
        mainnet_data = query_mainnet_data()
        
        # 进入交互模式
        interactive_mode()
    
    except KeyboardInterrupt:
        print(f"\n👋 程序已停止")
    
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 断开连接
        try:
            if network.is_connected():
                network.disconnect()
                print(f"👋 已断开网络连接")
        except:
            pass

if __name__ == "__main__":
    main()