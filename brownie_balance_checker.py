#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Brownie框架查询以太坊地址余额
支持ETH余额和ERC20代币余额查询

安装依赖:
pip install eth-brownie

初始化Brownie项目（如果需要）:
brownie init
"""

import os
import json
from decimal import Decimal
from typing import Dict, List, Optional, Union

try:
    from brownie import network, accounts, Contract, web3
    from brownie.network import main
    print("✅ Brownie库已导入")
except ImportError:
    print("❌ 请安装Brownie: pip install eth-brownie")
    exit(1)

# 常用代币合约地址
TOKEN_CONTRACTS = {
    'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    'USDC': '0xA0b86a33E6441b57ee3e4BEd34CE66fcEe8d5c4',
    'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
    'WETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
    'UNI': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',
    'LINK': '0x514910771AF9Ca656af840dff83E8264EcF986CA',
    'WBTC': '0x2260FAC5E5542a773Aa44fBCfEDf7C193bc2C599',
}

# ERC20代币标准ABI
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

class EthereumBalanceChecker:
    """以太坊余额查询器"""
    
    def __init__(self, network_name: str = "mainnet"):
        """
        初始化
        :param network_name: 网络名称 (mainnet, goerli, sepolia等)
        """
        self.network_name = network_name
        self.connected = False
        self.token_contracts = {}
        
        # 连接到网络
        self.connect_network()
    
    def connect_network(self):
        """连接到以太坊网络"""
        try:
            # 检查是否已连接
            if network.is_connected():
                print(f"✅ 已连接到网络: {network.show_active()}")
                self.connected = True
                return
            
            # 连接到指定网络
            network.connect(self.network_name)
            print(f"✅ 已连接到网络: {network.show_active()}")
            print(f"📊 当前区块高度: {web3.eth.block_number:,}")
            self.connected = True
            
        except Exception as e:
            print(f"❌ 连接网络失败: {e}")
            print(f"💡 可用网络: {network.show_active()}")
            self.connected = False
    
    def disconnect_network(self):
        """断开网络连接"""
        try:
            if network.is_connected():
                network.disconnect()
                print(f"👋 已断开网络连接")
                self.connected = False
        except Exception as e:
            print(f"⚠️ 断开连接时出错: {e}")
    
    def get_eth_balance(self, address: str) -> float:
        """获取ETH余额"""
        if not self.connected:
            print("❌ 未连接到网络")
            return 0.0
        
        try:
            # 获取Wei余额
            balance_wei = web3.eth.get_balance(address)
            # 转换为ETH
            balance_eth = web3.from_wei(balance_wei, 'ether')
            return float(balance_eth)
        except Exception as e:
            print(f"⚠️ 获取ETH余额失败: {e}")
            return 0.0
    
    def get_token_contract(self, token_address: str) -> Optional[Contract]:
        """获取代币合约实例"""
        try:
            if token_address in self.token_contracts:
                return self.token_contracts[token_address]
            
            # 创建合约实例
            contract = Contract.from_abi(
                "ERC20Token",
                token_address,
                ERC20_ABI
            )
            
            # 缓存合约实例
            self.token_contracts[token_address] = contract
            return contract
            
        except Exception as e:
            print(f"⚠️ 获取代币合约失败: {e}")
            return None
    
    def get_token_info(self, token_address: str) -> Dict[str, Union[str, int]]:
        """获取代币基本信息"""
        contract = self.get_token_contract(token_address)
        if not contract:
            return {}
        
        try:
            info = {
                'address': token_address,
                'name': contract.name(),
                'symbol': contract.symbol(),
                'decimals': contract.decimals(),
                'total_supply': contract.totalSupply()
            }
            return info
        except Exception as e:
            print(f"⚠️ 获取代币信息失败: {e}")
            return {'address': token_address}
    
    def get_token_balance(self, address: str, token_address: str) -> float:
        """获取ERC20代币余额"""
        if not self.connected:
            print("❌ 未连接到网络")
            return 0.0
        
        contract = self.get_token_contract(token_address)
        if not contract:
            return 0.0
        
        try:
            # 获取余额
            balance_wei = contract.balanceOf(address)
            
            # 获取小数位数
            decimals = contract.decimals()
            
            # 转换为正常单位
            balance = balance_wei / (10 ** decimals)
            return float(balance)
            
        except Exception as e:
            print(f"⚠️ 获取代币余额失败: {e}")
            return 0.0
    
    def get_all_balances(self, address: str, tokens: List[str] = None) -> Dict[str, Dict]:
        """获取地址的所有余额"""
        if not self.connected:
            print("❌ 未连接到网络")
            return {}
        
        if tokens is None:
            tokens = list(TOKEN_CONTRACTS.keys())
        
        balances = {}
        
        # ETH余额
        eth_balance = self.get_eth_balance(address)
        balances['ETH'] = {
            'symbol': 'ETH',
            'balance': eth_balance,
            'address': 'native',
            'decimals': 18
        }
        
        # 代币余额
        for token_symbol in tokens:
            if token_symbol in TOKEN_CONTRACTS:
                token_address = TOKEN_CONTRACTS[token_symbol]
                token_balance = self.get_token_balance(address, token_address)
                token_info = self.get_token_info(token_address)
                
                balances[token_symbol] = {
                    'symbol': token_symbol,
                    'balance': token_balance,
                    'address': token_address,
                    'name': token_info.get('name', token_symbol),
                    'decimals': token_info.get('decimals', 18)
                }
        
        return balances
    
    def display_balances(self, address: str, balances: Dict[str, Dict]):
        """显示余额信息"""
        print(f"\n📊 地址余额查询结果")
        print(f"🔗 地址: {address}")
        print(f"🌐 网络: {network.show_active()}")
        print("=" * 80)
        
        # 计算总价值（这里只显示余额，实际应用中可以接入价格API）
        total_items = 0
        
        for token_symbol, info in balances.items():
            balance = info['balance']
            if balance > 0:
                total_items += 1
                token_address = info['address']
                decimals = info.get('decimals', 18)
                
                print(f"💰 {token_symbol:<6} {balance:>15,.6f}")
                if token_address != 'native':
                    print(f"   📝 合约: {token_address}")
                print()
        
        print(f"📈 共找到 {total_items} 种有余额的资产")
        print(f"🔗 Etherscan: https://etherscan.io/address/{address}")
    
    def batch_check_addresses(self, addresses: List[str], tokens: List[str] = None) -> Dict[str, Dict]:
        """批量检查多个地址的余额"""
        results = {}
        
        print(f"🔍 开始批量检查 {len(addresses)} 个地址...")
        
        for i, address in enumerate(addresses, 1):
            print(f"📊 [{i}/{len(addresses)}] 检查地址: {address[:10]}...{address[-6:]}")
            
            try:
                balances = self.get_all_balances(address, tokens)
                results[address] = balances
                
                # 显示有余额的资产数量
                non_zero_count = sum(1 for info in balances.values() if info['balance'] > 0)
                print(f"   ✅ 找到 {non_zero_count} 种有余额的资产")
                
            except Exception as e:
                print(f"   ❌ 查询失败: {e}")
                results[address] = {}
        
        return results
    
    def save_results(self, results: Dict, filename: str = None):
        """保存查询结果到文件"""
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"temp/ethereum_balances_{timestamp}.json"
        
        try:
            os.makedirs('temp', exist_ok=True)
            
            # 准备保存数据
            save_data = {
                'network': network.show_active(),
                'query_time': timestamp if 'timestamp' in locals() else None,
                'total_addresses': len(results),
                'results': results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 结果已保存到: {filename}")
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")

def main():
    """主函数"""
    print("🚀 Brownie以太坊余额查询工具")
    print("=" * 50)
    
    # 创建查询器
    checker = EthereumBalanceChecker("mainnet")
    
    if not checker.connected:
        print("❌ 无法连接到以太坊网络")
        return
    
    try:
        # 示例地址（一些知名地址）
        example_addresses = [
            "0x6503de9fe77d256d9d823f2d335ce83ece9e153f",  # Concrete_STABLE
            "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Binance Hot Wallet
            "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",  # Curve.fi
        ]
        
        # 交互式查询
        print(f"\n请选择查询模式:")
        print(f"1. 查询单个地址")
        print(f"2. 查询多个地址")
        print(f"3. 使用示例地址")
        
        choice = input("请输入选择 (1-3): ").strip()
        
        if choice == '1':
            # 单个地址查询
            address = input("请输入以太坊地址: ").strip()
            if not address:
                print("❌ 地址不能为空")
                return
            
            balances = checker.get_all_balances(address)
            checker.display_balances(address, balances)
            
            # 保存结果
            save_choice = input("\n是否保存结果到文件? (y/N): ").strip().lower()
            if save_choice == 'y':
                checker.save_results({address: balances})
        
        elif choice == '2':
            # 多个地址查询
            print("请输入多个地址，每行一个，输入空行结束:")
            addresses = []
            while True:
                addr = input().strip()
                if not addr:
                    break
                addresses.append(addr)
            
            if not addresses:
                print("❌ 没有输入有效地址")
                return
            
            results = checker.batch_check_addresses(addresses)
            
            # 显示汇总
            print(f"\n📊 批量查询汇总:")
            for addr, balances in results.items():
                non_zero = sum(1 for info in balances.values() if info['balance'] > 0)
                print(f"   {addr}: {non_zero} 种资产")
            
            # 保存结果
            checker.save_results(results)
        
        elif choice == '3':
            # 示例地址查询
            print(f"\n使用示例地址进行查询...")
            results = checker.batch_check_addresses(example_addresses)
            
            # 显示详细结果
            for addr, balances in results.items():
                checker.display_balances(addr, balances)
            
            # 保存结果
            checker.save_results(results)
        
        else:
            print("❌ 无效选择")
    
    except KeyboardInterrupt:
        print(f"\n👋 查询已停止")
    
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 断开网络连接
        checker.disconnect_network()

if __name__ == "__main__":
    main()