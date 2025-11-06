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
    
    def get_implementation_address(self, network: str, proxy_address: str) -> Optional[str]:
        """获取代理合约的实现合约地址"""
        network_config = self.get_network_config(network)
        if not network_config:
            return None
        
        api_key = self.get_api_key(network_config)
        
        try:
            # 使用Etherscan API获取合约源代码信息
            params = {
                'chainid': network_config['chain_id'],
                'module': 'contract',
                'action': 'getsourcecode',
                'address': proxy_address,
                'apikey': api_key
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(
                network_config['api_url'],
                params=params,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('result'):
                    result = data['result'][0]
                    
                    # 检查是否是代理合约
                    implementation = result.get('Implementation', '')
                    proxy_info = result.get('Proxy', '0')
                    
                    if implementation and implementation != '':
                        print(f"🔍 检测到代理合约!")
                        print(f"   代理地址: {proxy_address}")
                        print(f"   实现地址: {implementation}")
                        return implementation
                    elif proxy_info == '1':
                        print(f"⚠️ 检测到代理合约但未找到实现地址")
                        return None
                        
        except Exception as e:
            print(f"⚠️ 检查代理合约时出错: {e}")
        
        return None
    
    def fetch_contract_abi(self, network: str, contract_address: str, max_retries: int = 3, check_proxy: bool = True) -> Optional[list]:
        """获取合约ABI
        
        Args:
            network: 网络名称
            contract_address: 合约地址
            max_retries: 最大重试次数
            check_proxy: 是否检查代理合约并获取实现合约的ABI
        """
        network_config = self.get_network_config(network)
        if not network_config:
            print(f"❌ 不支持的网络: {network}")
            print(f"支持的网络: {', '.join(self.network_configs.keys())}")
            return None
        
        # 检查是否是代理合约
        original_address = contract_address
        if check_proxy:
            implementation_address = self.get_implementation_address(network, contract_address)
            if implementation_address:
                print(f"🔄 将获取实现合约的ABI: {implementation_address}")
                contract_address = implementation_address
            else:
                print(f"✅ 不是代理合约或直接使用当前地址")
        
        api_key = self.get_api_key(network_config)
        
        print(f"🔍 正在从 {network_config['name']} 获取合约ABI...")
        print(f"📍 合约地址: {contract_address}")
        if original_address != contract_address:
            print(f"📍 原始地址: {original_address} (代理)")
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
    
    def save_abi_to_file(self, abi: list, network: str, contract_address: str, contract_name: Optional[str] = None, 
                         proxy_address: Optional[str] = None) -> str:
        """保存ABI到文件
        
        Args:
            abi: 合约ABI
            network: 网络名称
            contract_address: 实现合约地址
            contract_name: 合约名称（可选）
            proxy_address: 代理合约地址（如果是代理合约）
        """
        # 生成文件名 - 保留完整合约地址
        # 如果是代理合约，使用代理地址作为文件名，但标注为实现合约的ABI
        display_address = proxy_address if proxy_address else contract_address
        
        if contract_name:
            filename = f"{network}_{contract_name}_{display_address}.json"
        else:
            filename = f"{network}_{display_address}.json"
        
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
        
        # 如果是代理合约，添加代理信息
        if proxy_address:
            save_data['is_proxy'] = True
            save_data['proxy_address'] = proxy_address
            save_data['implementation_address'] = contract_address
            print(f"📝 标记为代理合约:")
            print(f"   代理地址: {proxy_address}")
            print(f"   实现地址: {contract_address}")
        
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
    parser.add_argument('--no-proxy-check', action='store_true', help='不检查代理合约，直接获取当前地址的ABI')
    
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
    
    # 先检查是否是代理合约（除非用户指定不检查）
    original_address = args.address
    implementation_address = None
    
    if not args.no_proxy_check:
        implementation_address = fetcher.get_implementation_address(args.network, original_address)
    else:
        print(f"⚠️ 跳过代理合约检查，直接获取当前地址的ABI")
    
    # 获取ABI (check_proxy参数控制是否在fetch时检查代理)
    abi = fetcher.fetch_contract_abi(args.network, args.address, check_proxy=not args.no_proxy_check)
    
    if abi:
        # 分析ABI（如果指定了analyze参数）
        if args.analyze:
            fetcher.analyze_abi(abi)
        
        # 保存ABI - 如果是代理合约，传递代理地址信息
        if implementation_address:
            # 使用实现合约地址获取ABI，但文件名使用代理地址
            filepath = fetcher.save_abi_to_file(
                abi, 
                args.network, 
                implementation_address,  # 实现合约地址
                args.name, 
                proxy_address=original_address  # 代理地址
            )
        else:
            # 普通合约
            filepath = fetcher.save_abi_to_file(abi, args.network, original_address, args.name)
        
        print(f"\n✅ 操作完成!")
        print(f"📄 ABI文件: {filepath}")
        print(f"📊 包含 {len(abi)} 个ABI项目")
        
        if not args.analyze:
            print(f"\n💡 提示: 使用 --analyze 参数可以查看ABI详细分析")
    else:
        print(f"\n❌ 获取ABI失败")

if __name__ == "__main__":
    main()