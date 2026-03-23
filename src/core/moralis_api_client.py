#!/usr/bin/env python3
"""
Moralis API客户端 - 专门处理DeFi协议识别和地址查询
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入requests (如果可用)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    print("⚠️ 未安装 requests 库，Moralis API功能将被禁用")
    HAS_REQUESTS = False

class MoralisAPIClient:
    """Moralis API客户端 - 用于查询地址信息和识别DeFi协议"""
    
    def __init__(self):
        self.moralis_api_key = os.getenv('moralis_api_key', os.getenv('MORALIS_API_KEY', 'YourApiKeyToken'))
        self.base_url = "https://deep-index.moralis.io/api/v2"
        
        # 初始化请求会话
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'X-API-Key': self.moralis_api_key,
                'Content-Type': 'application/json'
            })
        else:
            self.session = None
        
        # 网络配置
        self.network_configs = {
            'ethereum': {
                'name': 'Ethereum Mainnet',
                'chain_id': 1,
                'moralis_chain': 'eth',
                'native_token': 'ETH'
            },
            'polygon': {
                'name': 'Polygon',
                'chain_id': 137,
                'moralis_chain': 'polygon',
                'native_token': 'MATIC'
            },
            'bsc': {
                'name': 'Binance Smart Chain',
                'chain_id': 56,
                'moralis_chain': 'bsc',
                'native_token': 'BNB'
            },
            'arbitrum': {
                'name': 'Arbitrum One',
                'chain_id': 42161,
                'moralis_chain': 'arbitrum',
                'native_token': 'ETH'
            },
            'base': {
                'name': 'Base',
                'chain_id': 8453,
                'moralis_chain': 'base',
                'native_token': 'ETH'
            }
        }
        
        # DeFi协议映射
        self.defi_protocols = {
            'uniswap': {'name': 'Uniswap', 'type': 'DEX', 'keywords': ['uniswap', 'uni']},
            'sushiswap': {'name': 'SushiSwap', 'type': 'DEX', 'keywords': ['sushiswap', 'sushi']},
            'compound': {'name': 'Compound', 'type': 'Lending', 'keywords': ['compound', 'comp']},
            'aave': {'name': 'Aave', 'type': 'Lending', 'keywords': ['aave']},
            'pancakeswap': {'name': 'PancakeSwap', 'type': 'DEX', 'keywords': ['pancakeswap', 'pancake']},
            'curve': {'name': 'Curve', 'type': 'DEX', 'keywords': ['curve']},
            'balancer': {'name': 'Balancer', 'type': 'DEX', 'keywords': ['balancer']},
            'makerdao': {'name': 'MakerDAO', 'type': 'Lending', 'keywords': ['makerdao', 'maker']},
        }
    
    def is_api_available(self) -> bool:
        """检查Moralis API是否可用"""
        return (HAS_REQUESTS and 
                self.session is not None and 
                self.moralis_api_key and 
                self.moralis_api_key != 'YourApiKeyToken')
    
    def get_network_config(self, network: str) -> Optional[Dict]:
        """获取网络配置"""
        return self.network_configs.get(network.lower())
    
    def identify_defi_protocol(self, label: str, entity: str = None) -> Dict:
        """识别DeFi协议"""
        if not label:
            return {'is_defi': False, 'protocol': None, 'type': None, 'optimized_label': label}
        
        label_lower = label.lower()
        entity_lower = (entity or '').lower()
        
        # 检测各种DeFi协议
        for protocol_key, protocol_info in self.defi_protocols.items():
            for keyword in protocol_info['keywords']:
                if keyword in label_lower:
                    # 优化标签显示
                    if ':' in label:
                        optimized_label = f"{protocol_info['name']}: {label.split(':')[-1].strip()}"
                    else:
                        optimized_label = label
                    
                    return {
                        'is_defi': True,
                        'protocol': protocol_info['name'],
                        'type': protocol_info['type'],
                        'optimized_label': optimized_label
                    }
        
        # 检测通用DeFi关键词
        defi_keywords = ['pool', 'liquidity', 'lp', 'vault', 'yield', 'farm', 'bridge']
        if any(keyword in label_lower for keyword in defi_keywords):
            # 如果有实体名称，优先使用
            if entity and entity not in label:
                optimized_label = f"{entity}: {label.split(':')[-1].strip()}" if ':' in label else label
            else:
                optimized_label = label
            
            return {
                'is_defi': True,
                'protocol': entity,
                'type': 'DeFi',
                'optimized_label': optimized_label
            }
        
        # 不是DeFi协议
        # 但如果有实体信息，也可以优化显示
        if entity and entity not in label:
            optimized_label = f"{entity}: {label}"
        else:
            optimized_label = label
        
        return {
            'is_defi': False,
            'protocol': None,
            'type': None,
            'optimized_label': optimized_label
        }
    
    def query_address_transactions(self, address: str, network: str = 'ethereum', limit: int = 5) -> Optional[Dict]:
        """查询地址交易信息"""
        if not self.is_api_available():
            return None
        
        network_config = self.get_network_config(network)
        if not network_config:
            print(f"⚠️ Moralis不支持网络: {network}")
            return None
        
        try:
            chain_name = network_config['moralis_chain']
            tx_url = f"{self.base_url}/{address}"
            tx_params = {
                'chain': chain_name,
                'limit': limit
            }
            
            response = self.session.get(tx_url, params=tx_params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ 交易查询失败 {response.status_code}: {response.text[:100]}")
                return None
                
        except Exception as e:
            print(f"⚠️ 交易查询异常: {e}")
            return None
    
    def query_erc20_metadata(self, address: str, network: str = 'ethereum') -> Optional[Dict]:
        """查询ERC20代币元数据"""
        if not self.is_api_available():
            return None
        
        network_config = self.get_network_config(network)
        if not network_config:
            return None
        
        try:
            chain_name = network_config['moralis_chain']
            token_url = f"{self.base_url}/erc20/{address}/metadata"
            token_params = {
                'chain': chain_name
            }
            
            response = self.session.get(token_url, params=token_params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            return None
    
    def query_address_info(self, address: str, network: str = 'ethereum') -> Optional[Dict]:
        """查询地址信息 - 包含DeFi协议识别"""
        if not self.is_api_available():
            print(f"⚠️ Moralis API不可用")
            return None
        
        try:
            # 1. 查询交易信息获取地址标签
            tx_data = self.query_address_transactions(address, network, 5)
            
            if tx_data and tx_data.get('result'):
                transactions = tx_data['result']
                first_tx = transactions[0]
                
                to_address_label = first_tx.get('to_address_label')
                to_address_entity = first_tx.get('to_address_entity')
                
                if to_address_label:
                    # 识别DeFi协议
                    defi_info = self.identify_defi_protocol(to_address_label, to_address_entity)
                    
                    # 确定合约类型
                    if defi_info['is_defi']:
                        contract_type = 'defi_protocol'
                    else:
                        contract_type = 'contract'
                    
                    return {
                        'label': defi_info['optimized_label'],
                        'type': contract_type,
                        'source': f'moralis_{network.lower()}',
                        'contract_name': to_address_entity,
                        'is_verified': True,
                        'defi_info': defi_info
                    }
            
            # 2. 尝试查询ERC20代币信息
            token_info = self.query_erc20_metadata(address, network)
            if token_info:
                token_name = token_info.get('name')
                token_symbol = token_info.get('symbol')
                
                if token_name and token_symbol:
                    return {
                        'label': f"{token_name} ({token_symbol})",
                        'type': 'erc20_token',
                        'source': f'moralis_{network.lower()}',
                        'contract_name': token_name,
                        'is_verified': True,
                        'defi_info': {'is_defi': False, 'protocol': None, 'type': None}
                    }
            
            # 没有找到任何信息
            return None
            
        except Exception as e:
            print(f"⚠️ Moralis API查询异常: {e}")
            return None
    
    def test_api_connection(self, network: str = 'ethereum') -> bool:
        """测试API连接"""
        if not self.is_api_available():
            print("❌ Moralis API不可用")
            return False
        
        try:
            # 使用一个已知的地址测试
            test_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT合约
            result = self.query_address_info(test_address, network)
            
            if result:
                print(f"✅ Moralis API连接正常")
                print(f"   测试结果: {result.get('label')}")
                return True
            else:
                print("❌ Moralis API测试失败")
                return False
                
        except Exception as e:
            print(f"❌ Moralis API连接测试异常: {e}")
            return False

# 便捷函数
def create_moralis_client() -> MoralisAPIClient:
    """创建Moralis API客户端"""
    return MoralisAPIClient()

def query_address_with_moralis(address: str, network: str = 'ethereum') -> Optional[Dict]:
    """使用Moralis API查询地址信息的便捷函数"""
    client = create_moralis_client()
    return client.query_address_info(address, network)

if __name__ == "__main__":
    # 测试代码
    print("🔍 Moralis API客户端测试")
    print("=" * 50)
    
    client = MoralisAPIClient()
    
    # 测试API连接
    if client.test_api_connection():
        # 测试DeFi协议识别
        test_address = "0xc7bbec68d12a0d1830360f8ec58fa599ba1b0e9b"  # Uniswap V3 Pool
        result = client.query_address_info(test_address, 'ethereum')
        
        if result:
            print(f"\n🎯 DeFi协议识别测试:")
            print(f"   地址: {test_address}")
            print(f"   标签: {result.get('label')}")
            print(f"   类型: {result.get('type')}")
            print(f"   DeFi信息: {result.get('defi_info')}")
        else:
            print("❌ DeFi协议识别测试失败")
    else:
        print("❌ 无法连接到Moralis API")