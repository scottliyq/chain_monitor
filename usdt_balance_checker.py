#!/usr/bin/env python3
"""
USDT余额查询工具
支持配置RPC端点，查询任意地址的USDT余额
"""

import sys
from web3 import Web3
from decimal import Decimal
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

class USDTBalanceChecker:
    def __init__(self, rpc_url=None):
        """初始化USDT余额查询器
        
        Args:
            rpc_url (str): RPC端点URL，如果未提供则使用默认配置
        """
        # USDT合约地址 (Ethereum主网)
        self.USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        
        # 如果未提供RPC URL，尝试从环境变量或使用默认值
        if not rpc_url:
            rpc_url = self._get_default_rpc_url()
        
        self.rpc_url = rpc_url
        self.web3 = None
        self.usdt_contract = None
        
        # 尝试连接（带重试机制）
        self._connect_with_retry()
        
        print(f"✅ 成功连接到RPC: {rpc_url}")
        
        # USDT合约ABI (只需要balanceOf函数)
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
            }
        ]
        
        # 创建合约实例
        self.usdt_contract = self.web3.eth.contract(
            address=self.USDT_CONTRACT_ADDRESS,
            abi=self.usdt_abi
        )
    
    def _connect_with_retry(self):
        """带重试机制的连接方法"""
        # backup_rpcs = [
        #     "https://eth.llamarpc.com",
        #     "https://ethereum.publicnode.com",
        #     "https://eth.drpc.org"
        # ]
        
        # 首先尝试主要RPC
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.web3.is_connected():
                self._init_contract()
                return
        except Exception as e:
            print(f"⚠️ 主要RPC连接失败: {e}")
        
        # # 如果主要RPC失败，尝试备用RPC
        # for backup_rpc in backup_rpcs:
        #     if backup_rpc == self.rpc_url:  # 跳过已经尝试过的
        #         continue
        #     try:
        #         print(f"🔄 尝试备用RPC: {backup_rpc}")
        #         self.web3 = Web3(Web3.HTTPProvider(backup_rpc))
        #         if self.web3.is_connected():
        #             self.rpc_url = backup_rpc  # 更新为可用的RPC
        #             self._init_contract()
        #             return
        #     except Exception as e:
        #         print(f"⚠️ 备用RPC {backup_rpc} 连接失败: {e}")
        
        raise Exception("❌ 所有RPC端点都无法连接")
    
    def _init_contract(self):
        """初始化合约实例"""
        # 创建合约实例
        self.usdt_contract = self.web3.eth.contract(
            address=self.USDT_CONTRACT_ADDRESS,
            abi=self.usdt_abi
        )
    
    def _get_default_rpc_url(self):
        """获取默认RPC URL"""
        # 优先级: 环境变量 > 默认免费端点
        
        # 检查Alchemy API密钥
        if os.getenv('WEB3_ALCHEMY_PROJECT_ID'):
            return f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('WEB3_ALCHEMY_PROJECT_ID')}"
        
        # 检查Infura项目ID
        if os.getenv('WEB3_INFURA_PROJECT_ID'):
            return f"https://mainnet.infura.io/v3/{os.getenv('WEB3_INFURA_PROJECT_ID')}"
        
        # 检查自定义RPC URL
        if os.getenv('WEB3_RPC_URL'):
            return os.getenv('WEB3_RPC_URL')
        
        # 使用本地Ganache端点（如果可用）
        return "http://127.0.0.1:8545"
    
    def get_usdt_balance(self, address, max_retries=3):
        """查询指定地址的USDT余额
        
        Args:
            address (str): 要查询的地址
            max_retries (int): 最大重试次数
            
        Returns:
            dict: 包含余额信息的字典
        """
        for attempt in range(max_retries):
            try:
                # 验证地址格式
                if not self.web3.is_address(address):
                    raise ValueError(f"❌ 无效的地址格式: {address}")
                
                # 转换为校验和地址
                checksum_address = self.web3.to_checksum_address(address)
                
                # 查询USDT余额 (原始值，需要除以10^6)
                balance_raw = self.usdt_contract.functions.balanceOf(checksum_address).call()
                
                # USDT精度为6位小数
                balance_usdt = Decimal(balance_raw) / Decimal(10**6)
                
                # 查询ETH余额
                eth_balance_wei = self.web3.eth.get_balance(checksum_address)
                eth_balance = self.web3.from_wei(eth_balance_wei, 'ether')
                
                # 获取当前区块号
                current_block = self.web3.eth.block_number
                
                return {
                    'address': checksum_address,
                    'usdt_balance': float(balance_usdt),
                    'usdt_balance_raw': balance_raw,
                    'eth_balance': float(eth_balance),
                    'block_number': current_block,
                    'rpc_url': self.rpc_url
                }
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ 查询失败，正在重试 ({attempt + 1}/{max_retries}): {str(e)}")
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    raise Exception(f"❌ 查询余额失败 (已重试{max_retries}次): {str(e)}")
        
        raise Exception(f"❌ 查询余额失败: 超过最大重试次数")
    
    def format_balance_display(self, balance_info):
        """格式化余额显示"""
        print(f"\n📊 地址余额查询结果")
        print(f"{'='*50}")
        print(f"🏠 地址: {balance_info['address']}")
        print(f"💰 USDT余额: {balance_info['usdt_balance']:,.2f} USDT")
        print(f"⛽ ETH余额: {balance_info['eth_balance']:.4f} ETH")
        print(f"📦 区块高度: {balance_info['block_number']:,}")
        print(f"🔗 RPC端点: {balance_info['rpc_url']}")
        print(f"{'='*50}")

def main():
    """主函数"""
    print("🔍 USDT余额查询工具")
    print("=" * 40)
    
    # 解析命令行参数
    if len(sys.argv) < 2:
        print("📖 使用方法:")
        print(f"  python {sys.argv[0]} <地址> [RPC_URL]")
        print()
        print("📝 示例:")
        print(f"  python {sys.argv[0]} 0x1234...5678")
        print(f"  python {sys.argv[0]} 0x1234...5678 https://eth.llamarpc.com")
        print()
        print("🔧 环境变量配置:")
        print("  export WEB3_ALCHEMY_PROJECT_ID='your_alchemy_api_key'")
        print("  export WEB3_INFURA_PROJECT_ID='your_infura_project_id'")
        print("  export WEB3_RPC_URL='https://your-custom-rpc.com'")
        print()
        print("🎯 一些常用地址示例:")
        print("  Binance Hot Wallet: 0xF977814e90dA44bFA03b6295A0616a897441aceC")
        print("  Concrete_STABLE: 0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        return
    
    address = sys.argv[1]
    rpc_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # 创建查询器
        checker = USDTBalanceChecker(rpc_url)
        
        # 查询余额
        print(f"🔄 正在查询地址: {address}")
        balance_info = checker.get_usdt_balance(address)
        
        # 显示结果
        checker.format_balance_display(balance_info)
        
        # 保存到文件
        output_file = f"temp/usdt_balance_{address[-8:]}.json"
        os.makedirs('temp', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(balance_info, f, indent=2, ensure_ascii=False)
        
        print(f"💾 结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()