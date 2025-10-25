#!/usr/bin/env python3
"""
历史代币余额查询工具
根据指定的历史时间、代币名称和网络，查询对应区块高度的代币余额
支持多个区块链网络和多种代币
重用token_deposit_analyzer.py的方法和配置
"""

import sys
import os
import json
import logging
import argparse
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from web3 import Web3
from decimal import Decimal
from dotenv import load_dotenv
from block_time_converter import BlockTimeConverter
from address_constant import TOKEN_CONTRACTS, get_token_address, get_token_decimals

# 加载环境变量
load_dotenv()

# 配置日志
def setup_logging():
    """设置日志配置，支持控制台输出和每日轮转的文件输出"""
    # 创建logs目录
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 清除可能已存在的处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（每日轮转）
    log_file = os.path.join(log_dir, 'historical_balance_checker.log')
    file_handler = TimedRotatingFileHandler(
        log_file, 
        when='midnight', 
        interval=1, 
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 防止日志重复
    logger.propagate = False
    
    return logger

class HistoricalTokenBalanceChecker:
    """历史代币余额查询器"""
    
    def __init__(self, target_time, token, network, address_to_check):
        """
        初始化历史代币余额查询器
        
        Args:
            target_time (str): 目标时间 (格式: "YYYY-MM-DD HH:MM:SS")
            token (str): 代币名称 (如: "USDT", "USDC", "LINK")
            network (str): 网络名称 (如: "ethereum", "arbitrum", "base", "bsc")
            address_to_check (str): 要查询余额的地址
        """
        self.logger = logging.getLogger(__name__)
        
        # 基本配置
        self.target_time_str = target_time
        self.token = token.upper()
        self.network = network.lower()
        self.address_to_check = Web3.to_checksum_address(address_to_check)
        
        self.logger.info(f"🚀 初始化历史代币余额查询器")
        self.logger.info(f"   目标时间: {self.target_time_str} UTC")
        self.logger.info(f"   代币: {self.token}")
        self.logger.info(f"   网络: {self.network}")
        self.logger.info(f"   查询地址: {self.address_to_check}")
        
        # 获取网络配置
        self.network_config = self._get_network_config(self.network)
        
        # 获取代币合约地址
        self.TOKEN_CONTRACT_ADDRESS = get_token_address(self.network, self.token)
        if not self.TOKEN_CONTRACT_ADDRESS:
            raise ValueError(f"网络 '{self.network}' 不支持代币 '{self.token}' 或地址未配置")
        
        # API配置（根据网络选择）
        self.api_config = self._get_api_config(self.network)
        
        # 初始化区块时间转换器（传入网络特定的API配置）
        self.block_converter = BlockTimeConverter(self.api_config)
        
        # Web3配置
        self.rpc_url = self._get_rpc_url()
        self.web3 = self._init_web3()
        
        # 获取代币小数位数
        self.token_decimals = get_token_decimals(self.network, self.token)
        
        self.logger.info(f"🔧 配置信息:")
        self.logger.info(f"   网络: {self.network_config['name']} (Chain ID: {self.network_config['chain_id']})")
        self.logger.info(f"   {self.token}合约: {self.TOKEN_CONTRACT_ADDRESS}")
        self.logger.info(f"   {self.token}小数位数: {self.token_decimals}")
        self.logger.info(f"   API端点: {self.api_config['base_url']}")
        self.logger.info(f"   API密钥: {'***' + self.api_config['api_key'][-4:] if len(self.api_config['api_key']) > 4 else 'YourApiKeyToken'}")
        self.logger.info(f"   RPC URL: {self.rpc_url}")
        self.logger.info("")
        
    def _get_network_config(self, network):
        """获取网络配置信息"""
        network_configs = {
            "ethereum": {
                "name": "Ethereum Mainnet",
                "chain_id": 1,
                "native_token": "ETH",
                "block_time": 12,  # 秒
            },
            "arbitrum": {
                "name": "Arbitrum One",
                "chain_id": 42161,
                "native_token": "ETH",
                "block_time": 0.25,  # 秒
            },
            "base": {
                "name": "Base",
                "chain_id": 8453,
                "native_token": "ETH",
                "block_time": 2,  # 秒
            },
            "bsc": {
                "name": "BNB Smart Chain",
                "chain_id": 56,
                "native_token": "BNB",
                "block_time": 3,  # 秒
            }
        }
        
        if network not in network_configs:
            raise ValueError(f"不支持的网络: {network}. 支持的网络: {list(network_configs.keys())}")
        
        return network_configs[network]
    
    def _get_api_config(self, network):
        """获取不同网络的API配置"""
        api_configs = {
            "ethereum": {
                "base_url": "https://api.etherscan.io/v2/api",
                "api_key_env": "ETHERSCAN_API_KEY",
                "chain_id": 1
            },
            "arbitrum": {
                "base_url": "https://api.etherscan.io/v2/api",  # 统一使用etherscan的v2端点
                "api_key_env": "ARBISCAN_API_KEY",  # 可以回退到ETHERSCAN_API_KEY
                "chain_id": 42161
            },
            "base": {
                "base_url": "https://api.etherscan.io/v2/api",  # 统一使用etherscan的v2端点
                "api_key_env": "BASESCAN_API_KEY",  # 可以回退到ETHERSCAN_API_KEY
                "chain_id": 8453
            },
            "bsc": {
                "base_url": "https://api.etherscan.io/v2/api",  # 统一使用etherscan的v2端点
                "api_key_env": "BSCSCAN_API_KEY",  # 可以回退到ETHERSCAN_API_KEY
                "chain_id": 56
            }
        }
        
        config = api_configs[network]
        
        # 尝试获取特定网络的API密钥，如果没有则回退到通用密钥
        api_key = os.getenv(config["api_key_env"]) or os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        
        return {
            "base_url": config["base_url"],
            "api_key": api_key,
            "chain_id": config["chain_id"]
        }
    
    def _get_rpc_url(self):
        """从环境变量获取RPC URL，支持多网络"""
        # 根据网络获取对应的环境变量名
        network_rpc_env = {
            "ethereum": "WEB3_RPC_URL",
            "arbitrum": "ARBITRUM_RPC_URL", 
            "base": "BASE_RPC_URL",
            "bsc": "BSC_RPC_URL"
        }
        
        # 优先使用网络特定的RPC URL
        rpc_env_name = network_rpc_env.get(self.network, "WEB3_RPC_URL")
        rpc_url = os.getenv(rpc_env_name)
        
        # 如果没有网络特定的RPC URL，回退到通用的WEB3_RPC_URL
        if not rpc_url:
            rpc_url = os.getenv("WEB3_RPC_URL")
        
        if not rpc_url:
            raise ValueError(f"未找到 {rpc_env_name} 或 WEB3_RPC_URL 环境变量")
        
        return rpc_url
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not web3.is_connected():
                raise ConnectionError(f"无法连接到RPC节点: {self.rpc_url}")
            
            self.logger.info(f"✅ Web3连接成功: {self.rpc_url}")
            return web3
        except Exception as e:
            self.logger.error(f"❌ Web3连接失败: {e}")
            raise
    
    def get_target_block_number(self):
        """根据目标时间获取对应的区块号"""
        self.logger.info(f"🔄 正在查询目标时间对应的区块号...")
        
        try:
            # 使用BlockTimeConverter查询区块号
            target_timestamp = self.block_converter.datetime_to_timestamp(self.target_time_str)
            target_block = self.block_converter.get_block_by_timestamp(target_timestamp)
            
            self.logger.info(f"📦 目标时间 {self.target_time_str} UTC 对应的区块号: {target_block:,}")
            return target_block
            
        except Exception as e:
            self.logger.error(f"⚠️ 获取目标区块号失败: {e}")
            raise
    
    def get_token_balance_at_block(self, block_number):
        """查询指定区块高度的代币余额"""
        self.logger.info(f"💰 正在查询区块 {block_number:,} 的 {self.token} 余额...")
        
        try:
            # ERC20 balanceOf 函数签名
            balance_of_signature = "0x70a08231"  # balanceOf(address)
            
            # 构造调用数据
            padded_address = self.address_to_check[2:].zfill(64)  # 移除0x并填充到64位
            call_data = balance_of_signature + padded_address
            
            # 构造调用
            call_params = {
                "to": self.TOKEN_CONTRACT_ADDRESS,
                "data": call_data
            }
            
            # 在指定区块高度调用
            result = self.web3.eth.call(call_params, block_identifier=block_number)
            
            # 解析结果
            balance_wei = int(result.hex(), 16)
            balance_tokens = Decimal(balance_wei) / Decimal(10 ** self.token_decimals)
            
            self.logger.info(f"✅ 查询成功:")
            self.logger.info(f"   地址: {self.address_to_check}")
            self.logger.info(f"   区块号: {block_number:,}")
            self.logger.info(f"   原始余额: {balance_wei:,} wei")
            self.logger.info(f"   格式化余额: {balance_tokens:,.6f} {self.token}")
            
            return {
                "address": self.address_to_check,
                "block_number": block_number,
                "target_time": self.target_time_str,
                "token": self.token,
                "network": self.network,
                "balance_wei": str(balance_wei),
                "balance_tokens": str(balance_tokens),
                "token_decimals": self.token_decimals,
                "token_contract": self.TOKEN_CONTRACT_ADDRESS
            }
            
        except Exception as e:
            self.logger.error(f"❌ 查询代币余额失败: {e}")
            raise
    
    def save_result(self, result):
        """保存查询结果到文件"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"{self.network}_{self.token}_balance_{timestamp}"
        
        # 创建结果目录
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)
        
        # 保存JSON格式
        json_file = os.path.join(results_dir, f"{filename_base}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # 保存可读格式
        txt_file = os.path.join(results_dir, f"{filename_base}.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"历史代币余额查询结果\n")
            f.write(f"=" * 50 + "\n\n")
            f.write(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            f.write(f"目标时间: {result['target_time']} UTC\n")
            f.write(f"网络: {self.network_config['name']}\n")
            f.write(f"代币: {result['token']}\n")
            f.write(f"代币合约: {result['token_contract']}\n")
            f.write(f"查询地址: {result['address']}\n")
            f.write(f"目标区块号: {result['block_number']:,}\n")
            f.write(f"代币小数位数: {result['token_decimals']}\n")
            f.write(f"\n余额信息:\n")
            f.write(f"  原始余额: {result['balance_wei']} wei\n")
            f.write(f"  格式化余额: {result['balance_tokens']} {result['token']}\n")
        
        self.logger.info(f"📁 结果已保存:")
        self.logger.info(f"   JSON文件: {json_file}")
        self.logger.info(f"   文本文件: {txt_file}")
        
        return json_file, txt_file
    
    def run(self):
        """执行完整的历史余额查询流程"""
        try:
            # 1. 获取目标区块号
            target_block = self.get_target_block_number()
            
            # 2. 查询代币余额
            result = self.get_token_balance_at_block(target_block)
            
            # 3. 保存结果
            json_file, txt_file = self.save_result(result)
            
            self.logger.info(f"🎉 历史代币余额查询完成!")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 历史代币余额查询失败: {e}")
            raise

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description='历史代币余额查询工具')
    parser.add_argument('--time', required=True, help='目标时间 (格式: "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('--token', required=True, help='代币名称 (如: USDT, USDC, LINK)')
    parser.add_argument('--network', required=True, help='网络名称 (如: ethereum, arbitrum, base, bsc)')
    parser.add_argument('--address', required=True, help='要查询余额的地址')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging()
    
    try:
        logger.info(f"🚀 开始历史代币余额查询")
        logger.info(f"   目标时间: {args.time}")
        logger.info(f"   代币: {args.token}")
        logger.info(f"   网络: {args.network}")
        logger.info(f"   查询地址: {args.address}")
        logger.info("")
        
        # 创建查询器并执行
        checker = HistoricalTokenBalanceChecker(
            target_time=args.time,
            token=args.token,
            network=args.network,
            address_to_check=args.address
        )
        
        result = checker.run()
        
        logger.info(f"✅ 程序执行完成")
        
    except KeyboardInterrupt:
        logger.info("🛑 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()