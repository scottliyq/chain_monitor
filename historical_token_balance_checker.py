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
        
        # 设置检查地址（单地址模式才需要）
        if address_to_check:
            self.address_to_check = Web3.to_checksum_address(address_to_check)
        else:
            self.address_to_check = None
        
        self.logger.info(f"🚀 初始化历史代币余额查询器")
        self.logger.info(f"   目标时间: {self.target_time_str} UTC")
        self.logger.info(f"   代币: {self.token}")
        self.logger.info(f"   网络: {self.network}")
        if self.address_to_check:
            self.logger.info(f"   查询地址: {self.address_to_check}")
        else:
            self.logger.info("   查询模式: 批量查询")
        
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
            
            self.logger.info(f"📦 目标时间 {self.target_time_str} UTC 对应的区块号: {target_block}")
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
    
    def get_token_balance_for_address(self, address, block_number):
        """查询指定地址在指定区块的代币余额"""
        try:
            # ERC20 balanceOf 函数签名
            balance_of_signature = "0x70a08231"  # balanceOf(address)
            
            # 构造调用数据
            padded_address = address[2:].zfill(64)  # 移除0x并填充到64位
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
            
            return {
                "address": address,
                "balance_wei": balance_wei,
                "balance_tokens": balance_tokens
            }
            
        except Exception as e:
            self.logger.debug(f"查询地址 {address} 余额失败: {e}")
            return {
                "address": address,
                "balance_wei": 0,
                "balance_tokens": Decimal(0)
            }
    
    def get_token_holders_from_events(self, from_block=0, to_block=None):
        """通过分析Transfer事件获取所有代币持有人地址"""
        self.logger.info(f"📊 正在分析 {self.token} 合约的Transfer事件以获取持有人列表...")
        
        if to_block is None:
            to_block = 'latest'
        
        try:
            # ERC20 Transfer 事件签名: Transfer(address indexed from, address indexed to, uint256 value)
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            
            # 分批查询事件，避免API限制
            chunk_size = 10000  # 每次查询的区块范围
            all_holders = set()
            
            current_from = from_block
            while current_from <= to_block if isinstance(to_block, int) else True:
                current_to = min(current_from + chunk_size - 1, to_block) if isinstance(to_block, int) else current_from + chunk_size - 1
                
                self.logger.info(f"   查询区块范围: {current_from:,} - {current_to:,}")
                
                try:
                    # 查询Transfer事件
                    logs = self.web3.eth.get_logs({
                        'fromBlock': current_from,
                        'toBlock': current_to,
                        'address': self.TOKEN_CONTRACT_ADDRESS,
                        'topics': [transfer_topic]
                    })
                    
                    # 解析事件获取地址
                    for log in logs:
                        if len(log['topics']) >= 3:
                            # from地址（可能为0x0，表示铸币）
                            from_addr = "0x" + log['topics'][1].hex()[-40:]
                            # to地址
                            to_addr = "0x" + log['topics'][2].hex()[-40:]
                            
                            # 添加非零地址到持有人集合
                            if from_addr != "0x0000000000000000000000000000000000000000":
                                all_holders.add(Web3.to_checksum_address(from_addr))
                            if to_addr != "0x0000000000000000000000000000000000000000":
                                all_holders.add(Web3.to_checksum_address(to_addr))
                    
                    self.logger.info(f"   发现 {len(logs)} 个Transfer事件，当前总持有人数: {len(all_holders)}")
                    
                except Exception as e:
                    self.logger.warning(f"   查询区块 {current_from}-{current_to} 失败: {e}")
                
                current_from = current_to + 1
                
                # 如果是查询到latest，需要获取当前最新区块号来判断是否结束
                if not isinstance(to_block, int):
                    try:
                        latest_block = self.web3.eth.block_number
                        if current_from > latest_block:
                            break
                    except:
                        break
            
            self.logger.info(f"✅ 事件分析完成，总共发现 {len(all_holders)} 个唯一持有人地址")
            return list(all_holders)
            
        except Exception as e:
            self.logger.error(f"❌ 获取代币持有人列表失败: {e}")
            raise
    
    def find_addresses_with_balance_above(self, min_balance_tokens, max_addresses=1000):
        """
        查询指定时间的代币余额大于指定数量的所有地址
        
        Args:
            min_balance_tokens (float): 最小余额阈值（以代币为单位）
            max_addresses (int): 最大返回地址数量，避免过多结果
            
        Returns:
            list: 包含地址和余额信息的列表
        """
        self.logger.info(f"🔍 查询 {self.target_time_str} 时 {self.token} 余额 > {min_balance_tokens:,.6f} 的所有地址")
        
        try:
            # 1. 获取目标区块号
            target_block = self.get_target_block_number()
            
            # 2. 获取所有代币持有人
            self.logger.info(f"📊 获取 {self.token} 合约的所有持有人...")
            all_holders = self.get_token_holders_from_events(to_block=target_block)
            
            if not all_holders:
                self.logger.warning("⚠️ 未找到任何代币持有人")
                return []
            
            self.logger.info(f"📋 开始检查 {len(all_holders)} 个持有人在区块 {target_block:,} 的余额...")
            
            # 3. 批量查询余额并过滤
            qualified_addresses = []
            min_balance_wei = Decimal(min_balance_tokens) * Decimal(10 ** self.token_decimals)
            
            for i, address in enumerate(all_holders, 1):
                if i % 100 == 0:
                    self.logger.info(f"   进度: {i}/{len(all_holders)} ({i/len(all_holders)*100:.1f}%)")
                
                balance_info = self.get_token_balance_for_address(address, target_block)
                
                if balance_info['balance_wei'] >= min_balance_wei:
                    qualified_addresses.append({
                        "address": address,
                        "balance_tokens": float(balance_info['balance_tokens']),
                        "balance_wei": str(balance_info['balance_wei']),
                        "block_number": target_block,
                        "target_time": self.target_time_str,
                        "token": self.token,
                        "network": self.network,
                        "token_contract": self.TOKEN_CONTRACT_ADDRESS
                    })
                    
                    self.logger.debug(f"   ✅ {address}: {balance_info['balance_tokens']:,.6f} {self.token}")
                    
                    # 限制结果数量
                    if len(qualified_addresses) >= max_addresses:
                        self.logger.info(f"   🛑 达到最大地址数量限制: {max_addresses}")
                        break
            
            # 按余额降序排序
            qualified_addresses.sort(key=lambda x: x['balance_tokens'], reverse=True)
            
            self.logger.info(f"✅ 查询完成:")
            self.logger.info(f"   检查地址数: {min(len(all_holders), max_addresses)}")
            self.logger.info(f"   符合条件地址数: {len(qualified_addresses)}")
            self.logger.info(f"   最小余额要求: {min_balance_tokens:,.6f} {self.token}")
            
            if qualified_addresses:
                self.logger.info(f"   余额最高地址: {qualified_addresses[0]['address']} ({qualified_addresses[0]['balance_tokens']:,.6f} {self.token})")
                self.logger.info(f"   余额最低地址: {qualified_addresses[-1]['address']} ({qualified_addresses[-1]['balance_tokens']:,.6f} {self.token})")
            
            return qualified_addresses
            
        except Exception as e:
            self.logger.error(f"❌ 查询余额大于阈值的地址失败: {e}")
            raise
    
    def save_result(self, result):
        """保存查询结果到JSON文件"""
        try:
            # 创建results目录
            results_dir = 'results'
            os.makedirs(results_dir, exist_ok=True)
            
            # 生成文件名
            if isinstance(result, list):
                # 批量查询结果
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"token_holders_above_threshold_{self.network}_{self.token}_{timestamp}.json"
                
                # 添加汇总信息
                summary = {
                    "query_info": {
                        "target_time": self.target_time_str,
                        "token": self.token,
                        "network": self.network,
                        "total_qualified_addresses": len(result),
                        "query_timestamp": datetime.now().isoformat(),
                        "min_balance_required": result[0].get('min_balance_required') if result else None
                    },
                    "results": result
                }
                result_to_save = summary
            else:
                # 单地址查询结果
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                address_short = result['address'][:10] if result.get('address') else 'unknown'
                filename = f"balance_check_{self.network}_{self.token}_{address_short}_{timestamp}.json"
                result_to_save = result
            
            file_path = os.path.join(results_dir, filename)
            
            # 保存到JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result_to_save, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"� 结果已保存到: {file_path}")
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"❌ 保存结果失败: {e}")
            raise
    
    def run(self, mode='single', min_balance=None, max_addresses=1000):
        """
        执行余额查询
        
        Args:
            mode (str): 查询模式 - 'single' 单地址查询, 'batch' 批量查询大户
            min_balance (float): 批量查询时的最小余额阈值
            max_addresses (int): 批量查询时的最大返回地址数
        """
        try:
            if mode == 'single':
                if not self.address_to_check:
                    raise ValueError("单地址查询模式需要提供查询地址")
                
                self.logger.info(f"🚀 开始单地址余额查询...")
                
                # 获取目标区块号
                target_block = self.get_target_block_number()
                
                # 查询余额
                result = self.get_token_balance_at_block(target_block)
                
                # 保存结果
                self.save_result(result)
                
                return result
                
            elif mode == 'batch':
                if min_balance is None:
                    raise ValueError("批量查询模式需要提供最小余额阈值")
                
                self.logger.info(f"🚀 开始批量查询余额大户...")
                
                # 查询余额大于阈值的地址
                results = self.find_addresses_with_balance_above(min_balance, max_addresses)
                
                # 保存结果
                if results:
                    # 添加查询参数到结果中
                    for result in results:
                        result['min_balance_required'] = min_balance
                    
                    self.save_result(results)
                else:
                    self.logger.info("📭 未找到符合条件的地址")
                
                return results
                
            else:
                raise ValueError(f"不支持的查询模式: {mode}. 支持的模式: 'single', 'batch'")
                
        except Exception as e:
            self.logger.error(f"❌ 历史代币余额查询失败: {e}")
            raise

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description='历史代币余额查询工具')
    parser.add_argument('--time', required=True, help='目标时间 (格式: "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('--token', required=True, help='代币名称 (如: USDT, USDC, LINK)')
    parser.add_argument('--network', required=True, help='网络名称 (如: ethereum, arbitrum, base, bsc)')
    parser.add_argument('--mode', choices=['single', 'batch'], default='single', 
                       help='查询模式: single=单地址查询, batch=批量查询大户')
    parser.add_argument('--address', help='要查询余额的地址 (single模式必需)')
    parser.add_argument('--min-balance', type=float, help='最小余额阈值 (batch模式必需)')
    parser.add_argument('--max-addresses', type=int, default=1000, help='最大返回地址数 (batch模式，默认1000)')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.mode == 'single' and not args.address:
        parser.error("single模式需要提供 --address 参数")
    if args.mode == 'batch' and args.min_balance is None:
        parser.error("batch模式需要提供 --min-balance 参数")
    
    # 设置日志
    logger = setup_logging()
    
    try:
        logger.info(f"🚀 开始历史代币余额查询")
        logger.info(f"   目标时间: {args.time}")
        logger.info(f"   代币: {args.token}")
        logger.info(f"   网络: {args.network}")
        logger.info(f"   查询模式: {args.mode}")
        if args.mode == 'single':
            logger.info(f"   查询地址: {args.address}")
        else:
            logger.info(f"   最小余额: {args.min_balance}")
            logger.info(f"   最大地址数: {args.max_addresses}")
        logger.info("")
        
        # 创建查询器并执行
        checker = HistoricalTokenBalanceChecker(
            target_time=args.time,
            token=args.token,
            network=args.network,
            address_to_check=args.address
        )
        
        result = checker.run(
            mode=args.mode,
            min_balance=args.min_balance,
            max_addresses=args.max_addresses
        )
        
        logger.info(f"✅ 程序执行完成")
        
    except KeyboardInterrupt:
        logger.info("🛑 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()