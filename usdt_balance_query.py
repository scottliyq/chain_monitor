#!/usr/bin/env python3
"""
USDT余额查询工具
从.env文件读取RPC配置，查询指定地址的USDT余额
"""

import sys
import os
from web3 import Web3
from decimal import Decimal
import json
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class USDTBalanceQuery:
    def __init__(self):
        """初始化USDT余额查询器"""
        # USDT合约地址 (Ethereum主网)
        self.USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        
        # 从环境变量获取配置
        self.rpc_url = self._get_rpc_url()
        self.network_id = self._get_network_id()
        
        print(f"🔧 配置信息:")
        print(f"   RPC URL: {self.rpc_url}")
        print(f"   Network ID: {self.network_id}")
        print(f"   USDT合约: {self.USDT_CONTRACT_ADDRESS}")
        print()
        
        # 初始化Web3连接
        self.web3 = None
        self.usdt_contract = None
        self._init_web3()
        
        # USDT合约ABI (简化版，只包含必要函数)
        self.usdt_abi = [
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
            }
        ]
        
        # 创建合约实例
        self._init_contract()
    
    def _get_rpc_url(self):
        """从环境变量获取RPC URL"""
        rpc_url = os.getenv('WEB3_RPC_URL')
        if not rpc_url:
            # 备选方案
            if os.getenv('WEB3_ALCHEMY_PROJECT_ID'):
                return f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('WEB3_ALCHEMY_PROJECT_ID')}"
            elif os.getenv('WEB3_INFURA_PROJECT_ID'):
                return f"https://mainnet.infura.io/v3/{os.getenv('WEB3_INFURA_PROJECT_ID')}"
            else:
                raise ValueError("❌ 未找到RPC URL配置，请在.env文件中设置 WEB3_RPC_URL")
        
        return rpc_url.strip()
    
    def _get_network_id(self):
        """从环境变量获取Network ID"""
        network_id = os.getenv('WEB3_NETWORK_ID', '1')  # 默认为主网
        try:
            return int(network_id)
        except ValueError:
            print(f"⚠️ 无效的Network ID: {network_id}，使用默认值: 1")
            return 1
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            print(f"🔄 连接到RPC节点...")
            
            # 设置连接超时
            provider = Web3.HTTPProvider(
                self.rpc_url,
                request_kwargs={'timeout': 30}
            )
            self.web3 = Web3(provider)
            
            # 检查连接 - 使用更兼容的方法
            try:
                # 尝试获取区块号来验证连接
                chain_id = self.web3.eth.chain_id
                block_number = self.web3.eth.block_number
                
                print(f"✅ 连接成功!")
                print(f"   链ID: {chain_id}")
                print(f"   当前区块: {block_number:,}")
                
                # 检查网络ID是否匹配
                if chain_id != self.network_id:
                    print(f"⚠️ 网络ID不匹配! 配置: {self.network_id}, 实际: {chain_id}")
                    
            except Exception as conn_error:
                raise Exception(f"连接验证失败: {conn_error}")
            
        except Exception as e:
            raise Exception(f"❌ Web3连接失败: {e}")
    
    def _init_contract(self):
        """初始化USDT合约实例"""
        try:
            self.usdt_contract = self.web3.eth.contract(
                address=self.USDT_CONTRACT_ADDRESS,
                abi=self.usdt_abi
            )
            
            # 验证合约
            symbol = self.usdt_contract.functions.symbol().call()
            decimals = self.usdt_contract.functions.decimals().call()
            
            print(f"✅ USDT合约连接成功!")
            print(f"   代币符号: {symbol}")
            print(f"   精度: {decimals}")
            print()
            
        except Exception as e:
            raise Exception(f"❌ USDT合约初始化失败: {e}")
    
    def get_balance(self, address):
        """查询指定地址的USDT余额
        
        Args:
            address (str): 要查询的地址
            
        Returns:
            dict: 包含余额信息的字典
        """
        try:
            # 验证地址格式 - 使用更兼容的方法
            print(f"🔍 验证地址格式: {address}")
            
            # 检查地址基本格式
            if not address or not isinstance(address, str):
                raise ValueError(f"地址不能为空或必须是字符串")
            
            if not address.startswith('0x'):
                raise ValueError(f"地址必须以0x开头")
            
            if len(address) != 42:
                raise ValueError(f"地址长度必须是42个字符，当前长度: {len(address)}")
            
            try:
                # 使用Web3的内置方法验证和转换地址
                if Web3.isAddress(address):
                    checksum_address = Web3.toChecksumAddress(address)
                    print(f"✅ 地址验证成功: {checksum_address}")
                else:
                    raise ValueError(f"地址格式无效")
            except Exception as addr_error:
                raise ValueError(f"无效的地址格式: {address}, 错误: {addr_error}")
            
            print(f"🔍 查询地址: {checksum_address}")
            
            # 查询USDT余额
            usdt_balance_raw = self.usdt_contract.functions.balanceOf(checksum_address).call()
            usdt_decimals = self.usdt_contract.functions.decimals().call()
            usdt_balance = Decimal(usdt_balance_raw) / Decimal(10 ** usdt_decimals)
            
            # 查询ETH余额
            eth_balance_wei = self.web3.eth.get_balance(checksum_address)
            eth_balance = Web3.fromWei(eth_balance_wei, 'ether')
            
            # 获取当前区块信息
            current_block = self.web3.eth.block_number
            block_info = self.web3.eth.get_block(current_block)
            
            # 构造结果
            result = {
                'address': checksum_address,
                'usdt_balance': float(usdt_balance),
                'usdt_balance_raw': usdt_balance_raw,
                'usdt_decimals': usdt_decimals,
                'eth_balance': float(eth_balance),
                'eth_balance_wei': eth_balance_wei,
                'block_number': current_block,
                'block_timestamp': block_info['timestamp'],
                'network_id': self.network_id,
                'chain_id': self.web3.eth.chain_id,
                'rpc_url': self.rpc_url,
                'query_time': int(time.time())
            }
            
            return result
            
        except Exception as e:
            raise Exception(f"查询余额失败: {e}")
    
    def format_result(self, result):
        """格式化并显示查询结果"""
        print(f"📊 余额查询结果")
        print(f"{'='*60}")
        print(f"🏠 地址: {result['address']}")
        print(f"💰 USDT余额: {result['usdt_balance']:,.6f} USDT")
        print(f"⛽ ETH余额: {result['eth_balance']:.6f} ETH")
        print(f"📦 区块高度: {result['block_number']:,}")
        print(f"🕐 区块时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result['block_timestamp']))}")
        print(f"🌐 网络ID: {result['network_id']} (链ID: {result['chain_id']})")
        print(f"🔗 RPC端点: {result['rpc_url']}")
        print(f"{'='*60}")
        
        # 显示原始数据
        print(f"\n📋 原始数据:")
        print(f"   USDT原始余额: {result['usdt_balance_raw']}")
        print(f"   USDT精度: {result['usdt_decimals']}")
        print(f"   ETH原始余额: {result['eth_balance_wei']} wei")
    
    def save_result(self, result, output_dir="temp"):
        """保存查询结果到JSON文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            address_suffix = result['address'][-8:]
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"usdt_balance_{address_suffix}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 结果已保存到: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")
            return None

def main():
    """主函数"""
    print("🔍 USDT余额查询工具 (环境变量配置版)")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("📖 使用方法:")
        print(f"  python {sys.argv[0]} <地址>")
        print()
        print("📝 示例:")
        print(f"  python {sys.argv[0]} 0x1234...5678")
        print(f"  python {sys.argv[0]} 0xF977814e90dA44bFA03b6295A0616a897441aceC")
        print()
        print("🔧 环境变量配置 (.env文件):")
        print("  WEB3_RPC_URL=http://127.0.0.1:8545")
        print("  WEB3_NETWORK_ID=1337")
        print("  # 或者使用远程RPC:")
        print("  # WEB3_RPC_URL=https://eth.llamarpc.com")
        print("  # WEB3_NETWORK_ID=1")
        print()
        print("🎯 一些测试地址:")
        print("  Ganache默认账户: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
        print("  Binance热钱包: 0xF977814e90dA44bFA03b6295A0616a897441aceC")
        print("  Concrete_STABLE: 0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        return
    
    address = sys.argv[1].strip()
    
    try:
        # 创建查询器实例
        query = USDTBalanceQuery()
        
        # 查询余额
        result = query.get_balance(address)
        
        # 显示结果
        query.format_result(result)
        
        # 保存结果
        query.save_result(result)
        
        print(f"\n✅ 查询完成!")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()