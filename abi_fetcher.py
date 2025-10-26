#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合约ABI获取工具
用于查询指定网络上的合约ABI并保存到本地文件
支持多个区块链网络和Etherscan API
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime
import argparse
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ABIFetcher:
    """合约ABI获取器"""
    
    def __init__(self):
        """初始化ABI获取器"""
        self.network_configs = {
            'ethereum': {
                'name': 'Ethereum Mainnet',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 1
            },
            'arbitrum': {
                'name': 'Arbitrum One',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 42161
            },
            'base': {
                'name': 'Base',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 8453
            },
            'bsc': {
                'name': 'BNB Smart Chain',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 56
            },
            'polygon': {
                'name': 'Polygon',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 137
            },
            'optimism': {
                'name': 'Optimism',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 10
            },
            'avalanche': {
                'name': 'Avalanche C-Chain',
                'api_url': 'https://api.etherscan.io/v2/api',
                'api_key_env': 'ETHERSCAN_API_KEY',
                'chain_id': 43114
            }
        }
        
        # 创建ABI目录
        self.abi_dir = os.path.join(os.path.dirname(__file__), 'abi')
        os.makedirs(self.abi_dir, exist_ok=True)
        print(f"📁 ABI保存目录: {self.abi_dir}")
    
    def get_network_config(self, network: str) -> Optional[Dict[str, Any]]:
        """获取网络配置"""
        network = network.lower()
        if network in self.network_configs:
            return self.network_configs[network]
        
        # 支持一些别名
        aliases = {
            'eth': 'ethereum',
            'mainnet': 'ethereum',
            'arb': 'arbitrum',
            'arbitrum_one': 'arbitrum',
            'bnb': 'bsc',
            'binance': 'bsc',
            'matic': 'polygon',
            'op': 'optimism',
            'avax': 'avalanche',
            'avalanche_c': 'avalanche'
        }
        
        if network in aliases:
            return self.network_configs[aliases[network]]
        
        return None
    
    def get_api_key(self, network_config: Dict[str, Any]) -> str:
        """获取API密钥 - 统一使用ETHERSCAN_API_KEY"""
        api_key = os.getenv('ETHERSCAN_API_KEY')
        if not api_key:
            api_key = 'YourApiKeyToken'
            print(f"⚠️ 未找到ETHERSCAN_API_KEY，使用默认API密钥")
        return api_key
    
    def fetch_contract_abi(self, network: str, contract_address: str, max_retries: int = 3) -> Optional[list]:
        """获取合约ABI"""
        network_config = self.get_network_config(network)
        if not network_config:
            print(f"❌ 不支持的网络: {network}")
            print(f"支持的网络: {', '.join(self.network_configs.keys())}")
            return None
        
        api_key = self.get_api_key(network_config)
        
        print(f"🔍 正在从 {network_config['name']} 获取合约ABI...")
        print(f"📍 合约地址: {contract_address}")
        print(f"🌐 API URL: {network_config['api_url']}")
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    print(f"⏳ 第{attempt + 1}次尝试 (等待 {wait_time}s)...")
                    time.sleep(wait_time)
                
                # 构建API请求参数
                params = {
                    'chainid': network_config['chain_id'],
                    'module': 'contract',
                    'action': 'getabi',
                    'address': contract_address,
                    'apikey': api_key
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                # 发送请求
                response = requests.get(
                    network_config['api_url'],
                    params=params,
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code != 200:
                    print(f"⚠️ HTTP请求失败: {response.status_code}")
                    continue
                
                data = response.json()
                
                if data.get('status') == '1' and data.get('result'):
                    try:
                        abi = json.loads(data['result'])
                        print(f"✅ 成功获取ABI，包含 {len(abi)} 个函数/事件")
                        return abi
                    except json.JSONDecodeError as e:
                        print(f"⚠️ ABI数据格式错误: {e}")
                        continue
                else:
                    error_msg = data.get('message', 'Unknown error')
                    result_msg = data.get('result', '')
                    print(f"⚠️ API返回错误:")
                    print(f"   状态: {data.get('status', '')}")
                    print(f"   消息: {error_msg}")
                    if result_msg:
                        print(f"   结果: {result_msg}")
                    
                    if attempt < max_retries - 1:
                        print(f"🔄 准备重试...")
                    continue
                    
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 网络请求异常: {e}")
                if attempt < max_retries - 1:
                    print(f"🔄 准备重试...")
                continue
            except Exception as e:
                print(f"⚠️ 获取ABI时发生未知错误: {e}")
                if attempt < max_retries - 1:
                    print(f"🔄 准备重试...")
                continue
        
        print(f"❌ 经过{max_retries}次尝试后仍无法获取ABI")
        return None
    
    def save_abi_to_file(self, abi: list, network: str, contract_address: str, contract_name: str = None) -> str:
        """保存ABI到文件"""
        # 生成文件名 - 保留完整合约地址
        if contract_name:
            filename = f"{network}_{contract_name}_{contract_address}.json"
        else:
            filename = f"{network}_{contract_address}.json"
        
        filepath = os.path.join(self.abi_dir, filename)
        
        # 准备保存的数据
        save_data = {
            'network': network,
            'contract_address': contract_address,
            'contract_name': contract_name or 'Unknown',
            'fetched_at': datetime.now().isoformat(),
            'abi_length': len(abi),
            'abi': abi
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 ABI已保存到: {filepath}")
        return filepath
    
    def analyze_abi(self, abi: list):
        """分析ABI内容"""
        print(f"\n📊 ABI分析:")
        print(f"{'='*50}")
        
        functions = []
        events = []
        constructors = []
        fallbacks = []
        
        for item in abi:
            item_type = item.get('type', 'unknown')
            if item_type == 'function':
                functions.append(item)
            elif item_type == 'event':
                events.append(item)
            elif item_type == 'constructor':
                constructors.append(item)
            elif item_type in ['fallback', 'receive']:
                fallbacks.append(item)
        
        print(f"🔧 函数数量: {len(functions)}")
        print(f"📡 事件数量: {len(events)}")
        print(f"🏗️ 构造函数: {len(constructors)}")
        print(f"🔄 回退函数: {len(fallbacks)}")
        
        if functions:
            print(f"\n🔧 主要函数:")
            for i, func in enumerate(functions[:10], 1):
                func_name = func.get('name', 'unnamed')
                inputs = func.get('inputs', [])
                input_types = [inp.get('type', 'unknown') for inp in inputs]
                signature = f"{func_name}({','.join(input_types)})"
                stateMutability = func.get('stateMutability', 'unknown')
                print(f"   {i:2d}. {signature} [{stateMutability}]")
            
            if len(functions) > 10:
                print(f"   ... 还有 {len(functions) - 10} 个函数")
        
        if events:
            print(f"\n📡 主要事件:")
            for i, event in enumerate(events[:5], 1):
                event_name = event.get('name', 'unnamed')
                inputs = event.get('inputs', [])
                input_types = [inp.get('type', 'unknown') for inp in inputs]
                signature = f"{event_name}({','.join(input_types)})"
                print(f"   {i:2d}. {signature}")
            
            if len(events) > 5:
                print(f"   ... 还有 {len(events) - 5} 个事件")
        
        print(f"{'='*50}")
    
    def list_saved_abis(self):
        """列出已保存的ABI文件"""
        print(f"\n📁 已保存的ABI文件:")
        print(f"{'='*60}")
        
        if not os.path.exists(self.abi_dir):
            print("📝 还没有保存任何ABI文件")
            return
        
        abi_files = [f for f in os.listdir(self.abi_dir) if f.endswith('.json')]
        
        if not abi_files:
            print("📝 还没有保存任何ABI文件")
            return
        
        abi_files.sort()
        
        for i, filename in enumerate(abi_files, 1):
            filepath = os.path.join(self.abi_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                network = data.get('network', 'unknown')
                contract_name = data.get('contract_name', 'Unknown')
                contract_address = data.get('contract_address', 'Unknown')
                fetched_at = data.get('fetched_at', 'Unknown')
                abi_length = data.get('abi_length', 0)
                
                print(f"   {i:2d}. {filename}")
                print(f"       🌐 网络: {network}")
                print(f"       📛 合约名: {contract_name}")
                print(f"       📍 地址: {contract_address}")
                print(f"       📊 ABI长度: {abi_length}")
                print(f"       🕒 获取时间: {fetched_at}")
                print()
                
            except Exception as e:
                print(f"   {i:2d}. {filename} (读取失败: {e})")
        
        print(f"{'='*60}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='合约ABI获取工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python abi_fetcher.py ethereum 0xdAC17F958D2ee523a2206206994597C13D831ec7 --name USDT
  python abi_fetcher.py arbitrum 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1 --name WETH
  python abi_fetcher.py bsc 0x55d398326f99059fF775485246999027B3197955 --name USDT_BSC
  python abi_fetcher.py --list

支持的网络:
  ethereum, eth, mainnet     - Ethereum Mainnet
  arbitrum, arb             - Arbitrum One
  base                      - Base
  bsc, bnb, binance        - BNB Smart Chain
  polygon, matic           - Polygon
  optimism, op             - Optimism
  avalanche, avax          - Avalanche C-Chain
        """
    )
    
    parser.add_argument('network', nargs='?', help='区块链网络名称')
    parser.add_argument('address', nargs='?', help='合约地址')
    parser.add_argument('--name', '-n', help='合约名称（用于文件命名）')
    parser.add_argument('--list', '-l', action='store_true', help='列出已保存的ABI文件')
    parser.add_argument('--analyze', '-a', action='store_true', help='分析ABI内容')
    
    args = parser.parse_args()
    
    print("🔍 合约ABI获取工具")
    print("=" * 50)
    
    fetcher = ABIFetcher()
    
    if args.list:
        fetcher.list_saved_abis()
        return
    
    if not args.network or not args.address:
        parser.print_help()
        return
    
    # 获取ABI
    abi = fetcher.fetch_contract_abi(args.network, args.address)
    
    if abi:
        # 分析ABI（如果指定了analyze参数）
        if args.analyze:
            fetcher.analyze_abi(abi)
        
        # 保存ABI
        filepath = fetcher.save_abi_to_file(abi, args.network, args.address, args.name)
        
        print(f"\n✅ 操作完成!")
        print(f"📄 ABI文件: {filepath}")
        print(f"📊 包含 {len(abi)} 个ABI项目")
        
        if not args.analyze:
            print(f"\n💡 提示: 使用 --analyze 参数可以查看ABI详细分析")
    else:
        print(f"\n❌ 获取ABI失败")

if __name__ == "__main__":
    main()