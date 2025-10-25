#!/usr/bin/env python3
"""
USDT交易分析工具
分析2024年10月24日UTC全天的USDT转账（大于1000 USDT），
列出交互数量大于10的所有合约，按交互数量排序
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from web3 import Web3
from decimal import Decimal
from collections import defaultdict, Counter
from dotenv import load_dotenv
from block_time_converter import BlockTimeConverter
from address_constant import KNOWN_CONTRACTS, USDT_CONTRACT_ADDRESS

# 加载环境变量
load_dotenv()

class USDTDepositAnalyzer:
    def __init__(self, start_time=None, end_time=None, min_amount=None):
        """初始化USDT Deposit分析器
        
        Args:
            start_time (str): 开始时间，格式如 "2025-10-24 00:00:00"
            end_time (str): 结束时间，格式如 "2025-10-24 23:59:59"
            min_amount (float): 最小转账金额（USDT），默认1000
        """
        # 初始化区块时间转换器
        self.block_converter = BlockTimeConverter()
        
        # 合约地址（从地址常量文件导入）
        self.USDT_CONTRACT_ADDRESS = USDT_CONTRACT_ADDRESS
        
        # API配置
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.etherscan_api_url = "https://api.etherscan.io/v2/api"  # 使用V2 API
        
        # Web3配置
        self.rpc_url = self._get_rpc_url()
        self.web3 = self._init_web3()
        
        # 时间配置 - 从参数获取或使用默认值（所有时间均为UTC）
        if start_time and end_time:
            self.start_time_str = start_time
            self.end_time_str = end_time
            print(f"📅 使用参数指定的UTC时间范围:")
            print(f"   开始时间: {start_time} UTC")
            print(f"   结束时间: {end_time} UTC")
        else:
            # 默认使用2025年10月24日UTC时间
            self.start_time_str = "2025-10-24 00:00:00"
            self.end_time_str = "2025-10-24 23:59:59"
            print(f"📅 使用默认UTC时间范围:")
            print(f"   开始时间: {self.start_time_str} UTC")
            print(f"   结束时间: {self.end_time_str} UTC")
        
        print(f"\n🔄 开始转换UTC时间为时间戳...")
        # 使用BlockTimeConverter转换UTC时间为时间戳
        self.start_time = self.block_converter.datetime_to_timestamp(self.start_time_str)
        self.current_time = self.block_converter.datetime_to_timestamp(self.end_time_str)
        
        # 使用BlockTimeConverter获取对应的区块号范围
        print(f"🚀 开始查询时间对应的区块号范围...")
        try:
            self.start_block, self.end_block, _ = self.block_converter.get_block_range(self.start_time_str, self.end_time_str)
            print(f"📦 查询到区块范围: {self.start_block:,} 到 {self.end_block:,} ({self.end_block - self.start_block + 1:,} 个区块)")
        except Exception as e:
            print(f"⚠️ 获取区块范围失败: {e}")
            print(f"   使用默认区块范围（2024年10月24日）")
            # 返回2024年10月24日的已知区块范围
            self.start_block, self.end_block = 21031733, 21038905
        
        # 分析配置
        if min_amount is not None:
            self.min_amount = float(min_amount)
            print(f"💰 使用参数指定的最小金额: {self.min_amount} USDT")
        else:
            self.min_amount = 1000  # 默认1000 USDT
            print(f"💰 使用默认最小金额: {self.min_amount} USDT")
        
        self.usdt_decimals = 6  # USDT是6位小数
        
        print(f"🔧 配置信息:")
        print(f"   USDT合约: {self.USDT_CONTRACT_ADDRESS}")
        print(f"   Etherscan API: {'***' + self.etherscan_api_key[-4:] if len(self.etherscan_api_key) > 4 else 'YourApiKeyToken'}")
        print(f"   RPC URL: {self.rpc_url}")
        print(f"   查询时间范围: {self.start_time_str} 到 {self.end_time_str} UTC")
        print(f"   查询区块范围: {self.start_block:,} 到 {self.end_block:,}")
        print(f"   分析范围: 转账金额 >= {self.min_amount} USDT")
        print()
    
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
                # 使用免费的公共RPC端点
                return "https://eth.llamarpc.com"
        
        return rpc_url.strip()
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            provider = Web3.HTTPProvider(
                self.rpc_url,
                request_kwargs={'timeout': 30}
            )
            web3 = Web3(provider)
            
            # 验证连接
            chain_id = web3.eth.chain_id
            if chain_id != 1:
                print(f"⚠️ 警告: 当前连接的不是以太坊主网 (Chain ID: {chain_id})")
            else:
                print(f"✅ 成功连接以太坊主网")
            
            return web3
            
        except Exception as e:
            print(f"⚠️ Web3连接失败: {e}")
            return None
    
    def is_contract_address(self, address):
        """检查地址是否为合约地址"""
        try:
            if self.web3:
                # 转换为checksum地址
                checksum_address = self.web3.to_checksum_address(address)
                code = self.web3.eth.get_code(checksum_address)
                return len(code) > 2  # 不只是'0x'
            else:
                # 如果没有Web3连接，假设是合约（保守估计）
                return True
        except Exception as e:
            print(f"   ⚠️ 检查合约地址失败 {address}: {e}")
            return False
    
    def get_usdt_transfers_by_time_segments(self, segment_minutes=10):
        """分段获取USDT转账记录，避开Etherscan 10000条记录限制
        
        Args:
            segment_minutes (int): 每段查询的时间长度（分钟）
            
        Returns:
            list: 所有转账记录列表
        """
        print(f"🔄 开始分段查询USDT转账（每段 {segment_minutes} 分钟）")
        
        all_transfers = []
        segment_seconds = segment_minutes * 60
        current_start = self.start_time
        segment_count = 0
        
        while current_start < self.current_time:
            segment_count += 1
            current_end = min(current_start + segment_seconds, self.current_time)
            
            # 显示当前查询的时间段
            start_dt = datetime.fromtimestamp(current_start, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(current_end, tz=timezone.utc)
            print(f"\n📍 第{segment_count}段: {start_dt.strftime('%H:%M:%S')} - {end_dt.strftime('%H:%M:%S')} UTC")
            
            try:
                # 使用BlockTimeConverter获取当前时间段的区块范围
                start_block = self.block_converter.get_block_by_timestamp(current_start, 'before')
                end_block = self.block_converter.get_block_by_timestamp(current_end, 'after')
                
                if start_block is None or end_block is None:
                    print(f"   ⚠️ 无法获取区块范围，跳过此时间段")
                    current_start = current_end
                    continue
                
                print(f"   📦 区块范围: {start_block:,} - {end_block:,}")
                
                # 查询当前时间段的转账
                segment_transfers = self._get_usdt_transfers_for_blocks(start_block, end_block)
                
                if segment_transfers:
                    # 过滤出确实在目标时间范围内的转账
                    filtered_transfers = []
                    for transfer in segment_transfers:
                        tx_timestamp = int(transfer['timeStamp'])
                        if current_start <= tx_timestamp <= current_end:
                            filtered_transfers.append(transfer)
                    
                    print(f"   ✅ 获取到 {len(segment_transfers)} 笔转账，筛选后 {len(filtered_transfers)} 笔在目标时间内")
                    all_transfers.extend(filtered_transfers)
                else:
                    print(f"   📝 此时间段无转账记录")
                
                # 添加延时避免API限制
                import time
                time.sleep(0.2)  # 200ms延时
                
            except Exception as e:
                print(f"   ❌ 查询第{segment_count}段时出错: {e}")
            
            current_start = current_end
        
        print(f"\n🎯 分段查询完成！")
        print(f"   📊 总段数: {segment_count}")
        print(f"   📦 总转账数: {len(all_transfers)}")
        
        # 按时间戳降序排序
        all_transfers.sort(key=lambda x: int(x['timeStamp']), reverse=True)
        
        return all_transfers
    
    def _get_usdt_transfers_for_blocks(self, start_block, end_block):
        """获取指定区块范围内的USDT转账记录
        
        Args:
            start_block (int): 开始区块号
            end_block (int): 结束区块号
            
        Returns:
            list: 转账记录列表
        """
        try:
            params = {
                'chainid': 1,  # 以太坊主网
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': self.USDT_CONTRACT_ADDRESS,
                'startblock': start_block,
                'endblock': end_block,
                'page': 1,
                'offset': 10000,  # 单次查询最大条数
                'sort': 'desc',
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=30)
            data = response.json()
            
            if data['status'] == '1':
                return data['result']
            else:
                print(f"   ⚠️ API错误: {data.get('message', 'Unknown error')}")
                return []
                
        except Exception as e:
            print(f"   ❌ 查询区块范围转账失败: {e}")
            return []

    def get_usdt_transfers(self, page=1, per_page=5000):
        """获取USDT转账记录 (旧方法，保留兼容性)
        
        Args:
            page (int): 页码
            per_page (int): 每页数量 (最大5000，确保page×per_page≤10000)
            
        Returns:
            list: 转账记录列表
        """
        try:
            print(f"🔍 获取USDT转账记录 (页码: {page})")
            
            # 使用动态获取的区块范围
            start_block = self.start_block
            end_block = self.end_block
            
            params = {
                'chainid': 1,  # 以太坊主网 - V2 API新增参数
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': self.USDT_CONTRACT_ADDRESS,
                'startblock': start_block,
                'endblock': end_block,
                'page': page,
                'offset': per_page,
                'sort': 'desc',
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=30)
            data = response.json()
            
            print(f"   API响应状态: {data.get('status')}, 消息: {data.get('message')}")
            
            if data['status'] == '1':
                transfers = data['result']
                print(f"   📦 获取到 {len(transfers)} 笔转账")
                return transfers
            else:
                print(data)
                print(f"   ❌ API错误: {data.get('message', 'Unknown error')}")
                return []
                
        except Exception as e:
            print(f"   ❌ 获取转账失败: {e}")
            return []
    
    def filter_recent_transfers(self, transfers):
        """筛选指定时间范围UTC的转账"""
        target_transfers = []
        
        print(f"🔍 检查转账时间戳范围...")
        if transfers:
            first_tx = transfers[0]
            last_tx = transfers[-1]
            first_time = datetime.fromtimestamp(int(first_tx['timeStamp']), tz=timezone.utc)
            last_time = datetime.fromtimestamp(int(last_tx['timeStamp']), tz=timezone.utc)
            print(f"   第一笔交易时间: {first_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   最后一笔交易时间: {last_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   目标开始时间: {datetime.fromtimestamp(self.start_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"   目标结束时间: {datetime.fromtimestamp(self.current_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        for transfer in transfers:
            tx_timestamp = int(transfer['timeStamp'])
            
            # 检查是否在目标时间范围内
            if self.start_time <= tx_timestamp < self.current_time:
                target_transfers.append(transfer)
            elif tx_timestamp < self.start_time:
                # 如果时间戳小于开始时间且是降序，可以停止
                print(f"   ⏹️ 时间戳 {tx_timestamp} 早于开始时间 {self.start_time}，停止搜索")
                break
        
        print(f"🕐 指定时间范围的转账: {len(target_transfers)} 笔")
        return target_transfers
    
    def filter_large_amounts(self, transfers):
        """筛选大于1000 USDT的转账"""
        large_transfers = []
        
        for transfer in transfers:
            try:
                # USDT是6位小数
                amount = Decimal(transfer['value']) / Decimal(10 ** self.usdt_decimals)
                transfer['amount_usdt'] = float(amount)
                
                # 筛选大于1000 USDT的转账
                if amount >= self.min_amount:
                    large_transfers.append(transfer)
            except:
                continue
        
        print(f"💰 大于{self.min_amount} USDT的转账: {len(large_transfers)} 笔")
        return large_transfers
    
    def get_transaction_details(self, tx_hash):
        """获取交易详情，包括方法名"""
        try:
            if not self.web3:
                return None
            
            # 获取交易详情
            tx = self.web3.eth.get_transaction(tx_hash)
            
            # 解析方法名
            method_name = "unknown"
            if tx.input and len(tx.input) >= 10:
                # 获取方法选择器（前4字节）
                method_selector = tx.input[:10]
                
                # 常见的方法选择器映射
                method_selectors = {
                    "0xa9059cbb": "transfer",
                    "0x23b872dd": "transferFrom", 
                    "0x095ea7b3": "approve",
                    "0xb6b55f25": "deposit",
                    "0xe2bbb158": "deposit",  # 带参数的deposit
                    "0x47e7ef24": "deposit",  # 另一种deposit签名
                    "0x6e553f65": "deposit",  # ERC4626 deposit
                    "0xd0e30db0": "deposit",  # 简单deposit()
                    "0x2e1a7d4d": "withdraw",
                    "0x3ccfd60b": "withdraw",
                    "0x441a3e70": "multicall",
                    "0x5ae401dc": "multicall",
                    "0xac9650d8": "multicall"
                }
                
                method_name = method_selectors.get(method_selector, f"unknown({method_selector})")
            
            return {
                'method_name': method_name,
                'method_selector': method_selector if 'method_selector' in locals() else None,
                'to': tx.to,
                'from': tx['from'],
                'gas': tx.gas,
                'gas_price': tx.gasPrice,
                'input_data': tx.input
            }
            
        except Exception as e:
            print(f"   ⚠️ 获取交易详情失败 {tx_hash[:10]}...: {e}")
            return None
    
    def analyze_deposit_transactions(self, transfers):
        """分析deposit交易"""
        print(f"🔍 分析交易方法名和接收合约...")
        
        deposit_transfers = []
        method_counter = Counter()
        contract_counter = Counter()
        
        # 预定义的DeFi协议合约地址（常见的支持USDT deposit的协议）
        known_defi_contracts = {
            '0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9': 'Aave LendingPool',
            '0xf650C3d88D12dB855b8bf7D11Be6C55A4e07dCC9': 'Compound cUSDT',
            '0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7': 'Curve 3Pool',
            '0x7Da96a3891Add058AdA2E826306D812C638D87a6': 'Yearn USDT Vault',
            '0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B': 'MakerDAO Vault',
            '0x111111125421cA6dc452d289314280a0f8842A65': '1inch Router',
            '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD': 'Uniswap Labs',
            '0xE592427A0AEce92De3Edee1F18E0157C05861564': 'Uniswap V3 Router',
            '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45': 'Uniswap V3 Router 2',
            '0x80a64c6D7f12C47B7c66c5B4E20E72bc1FCd5d9e': 'Curve Factory',
            '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F': 'SushiSwap Router',
            '0x6B175474E89094C44Da98b954EedeAC495271d0F': 'DAI Token',
            '0x853d955aCEf822Db058eb8505911ED77F175b99e': 'FRAX Token'
        }
        
        for i, transfer in enumerate(transfers, 1):
            if i % 10 == 0 or i == len(transfers):
                print(f"   处理进度: {i}/{len(transfers)}")
            
            to_address = transfer['to']
            
            # 检查是否转入已知的DeFi协议
            is_defi_protocol = to_address in known_defi_contracts
            
            # 获取交易详情来分析方法
            tx_details = self.get_transaction_details(transfer['hash'])
            method_name = "transfer"  # USDT转账默认是transfer方法
            
            if tx_details:
                transfer['tx_details'] = tx_details
                method_name = tx_details['method_name']
                method_counter[method_name] += 1
            
            # 统计接收合约
            if is_defi_protocol:
                contract_name = known_defi_contracts[to_address]
                contract_counter[contract_name] += 1
                
                # 如果是转入DeFi协议的USDT，认为是deposit操作
                transfer['contract_name'] = contract_name
                transfer['is_defi_deposit'] = True
                deposit_transfers.append(transfer)
                print(f"   🏦 发现DeFi deposit: {transfer['amount_usdt']:,.0f} USDT → {contract_name}")
            else:
                # 检查是否是合约地址
                try:
                    if self.web3:
                        code = self.web3.eth.get_code(to_address)
                        if len(code) > 2:  # 是合约
                            contract_name = self.get_contract_name(to_address)
                            if 'pool' in contract_name.lower() or 'vault' in contract_name.lower() or 'staking' in contract_name.lower():
                                # 可能是DeFi相关合约
                                transfer['contract_name'] = contract_name
                                transfer['is_defi_deposit'] = True
                                deposit_transfers.append(transfer)
                                contract_counter[contract_name] += 1
                                print(f"   🏦 发现潜在DeFi deposit: {transfer['amount_usdt']:,.0f} USDT → {contract_name}")
                except:
                    pass
            
            # 添加延迟避免RPC限制
            time.sleep(0.05)
        
        print(f"\n📊 交易方法统计:")
        for method, count in method_counter.most_common(10):
            print(f"   {method}: {count} 笔")
        
        print(f"\n🏦 DeFi协议统计:")
        for contract, count in contract_counter.most_common(10):
            print(f"   {contract}: {count} 笔")
        
        print(f"\n🏦 DeFi Deposit交易: {len(deposit_transfers)} 笔")
        return deposit_transfers
    
    def analyze_destination_contracts(self, deposit_transfers):
        """分析转入地址，统计合约地址"""
        print(f"🔍 分析转入地址...")
        
        # 统计转入地址
        destination_counter = Counter()
        contract_info = {}
        
        for transfer in deposit_transfers:
            to_address = transfer['to']
            destination_counter[to_address] += 1
            
            # 检查是否是合约地址
            if to_address not in contract_info:
                try:
                    if self.web3:
                        code = self.web3.eth.get_code(to_address)
                        is_contract = len(code) > 2  # 不只是'0x'
                        contract_info[to_address] = {
                            'is_contract': is_contract,
                            'code_size': len(code),
                            'name': 'Unknown'
                        }
                        
                        # 如果是合约，尝试获取名称
                        if is_contract:
                            contract_name = self.get_contract_name(to_address)
                            contract_info[to_address]['name'] = contract_name
                    else:
                        contract_info[to_address] = {
                            'is_contract': True,  # 假设是合约
                            'code_size': 0,
                            'name': 'Unknown'
                        }
                except Exception as e:
                    print(f"   ⚠️ 检查地址失败 {to_address}: {e}")
                    contract_info[to_address] = {
                        'is_contract': True,
                        'code_size': 0,
                        'name': 'Unknown'
                    }
        
        # 只保留合约地址
        contract_destinations = {
            addr: count for addr, count in destination_counter.items()
            if contract_info.get(addr, {}).get('is_contract', False)
        }
        
        print(f"📋 转入的合约地址数量: {len(contract_destinations)}")
        
        # 获取前5名
        top_5_contracts = Counter(contract_destinations).most_common(5)
        
        return top_5_contracts, contract_info, destination_counter
    
    def get_contract_name(self, contract_address):
        """从Etherscan获取合约名称"""
        try:
            params = {
                'chainid': 1,  # 以太坊主网 - V2 API新增参数
                'module': 'contract',
                'action': 'getsourcecode',
                'address': contract_address,
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == '1' and data['result']:
                source_info = data['result'][0]
                contract_name = source_info.get('ContractName', 'Unknown')
                return contract_name if contract_name else 'Unknown'
            
            return 'Unknown'
            
        except Exception as e:
            return 'Unknown'
    
    def calculate_statistics(self, deposit_transfers, top_5_contracts):
        """计算统计信息"""
        # 总金额统计
        total_amount = sum(transfer['amount_usdt'] for transfer in deposit_transfers)
        
        # 时间分布（UTC小时）
        hour_distribution = defaultdict(int)
        for transfer in deposit_transfers:
            hour = datetime.fromtimestamp(int(transfer['timeStamp']), tz=timezone.utc).hour
            hour_distribution[hour] += 1
        
        # 金额分布
        amount_ranges = {
            "1M-5M": 0,
            "5M-10M": 0, 
            "10M-50M": 0,
            "50M+": 0
        }
        
        for transfer in deposit_transfers:
            amount = transfer['amount_usdt']
            if 1000000 <= amount < 5000000:
                amount_ranges["1M-5M"] += 1
            elif 5000000 <= amount < 10000000:
                amount_ranges["5M-10M"] += 1
            elif 10000000 <= amount < 50000000:
                amount_ranges["10M-50M"] += 1
            else:
                amount_ranges["50M+"] += 1
        
        return {
            'total_amount': total_amount,
            'total_transactions': len(deposit_transfers),
            'hour_distribution': dict(hour_distribution),
            'amount_ranges': amount_ranges,
            'average_amount': total_amount / len(deposit_transfers) if deposit_transfers else 0
        }
    
    def format_results(self, deposit_transfers, top_5_contracts, contract_info, stats):
        """格式化并显示结果"""
        print(f"\n📊 USDT大额Deposit交易分析结果")
        print(f"{'='*80}")
        print(f"⏰ 分析时间范围: 过去24小时")
        print(f"💰 最小金额: {self.min_amount:,} USDT")
        print(f"🏦 Deposit交易总数: {stats['total_transactions']:,} 笔")
        print(f"💵 总金额: {stats['total_amount']:,.2f} USDT")
        print(f"📈 平均金额: {stats['average_amount']:,.2f} USDT")
        print(f"{'='*80}")
        
        print(f"\n🏆 转入地址最多的合约前5名:")
        print(f"{'-'*80}")
        
        for i, (contract_address, count) in enumerate(top_5_contracts, 1):
            info = contract_info.get(contract_address, {})
            contract_name = info.get('name', 'Unknown')
            code_size = info.get('code_size', 0)
            
            # 计算总金额
            total_amount = sum(
                transfer['amount_usdt'] for transfer in deposit_transfers
                if Web3.to_checksum_address(transfer['to']) == contract_address
            )
            
            print(f"#{i}. {contract_name}")
            print(f"     🏠 地址: {contract_address}")
            print(f"     📊 转入次数: {count} 次")
            print(f"     💰 总金额: {total_amount:,.2f} USDT")
            print(f"     📏 代码大小: {code_size:,} bytes")
            print()
        
        print(f"📈 金额分布:")
        for range_name, count in stats['amount_ranges'].items():
            print(f"   {range_name} USDT: {count} 笔")
        
        print(f"\n⏰ 24小时分布 (显示活跃时段):")
        sorted_hours = sorted(stats['hour_distribution'].items(), key=lambda x: x[1], reverse=True)
        for hour, count in sorted_hours[:8]:  # 显示最活跃的8个小时
            print(f"   {hour:02d}:00-{hour:02d}:59: {count} 笔")
    
    def save_results(self, deposit_transfers, top_5_contracts, contract_info, stats, output_dir="temp"):
        """保存结果到文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存详细数据
            result = {
                'analysis_time': datetime.now().isoformat(),
                'query_period': '24 hours',
                'min_amount': self.min_amount,
                'statistics': stats,
                'top_5_contracts': [
                    {
                        'rank': i,
                        'address': addr,
                        'name': contract_info.get(addr, {}).get('name', 'Unknown'),
                        'transaction_count': count,
                        'total_amount': sum(
                            transfer['amount_usdt'] for transfer in deposit_transfers
                            if Web3.to_checksum_address(transfer['to']) == addr
                        ),
                        'is_contract': contract_info.get(addr, {}).get('is_contract', False),
                        'code_size': contract_info.get(addr, {}).get('code_size', 0)
                    }
                    for i, (addr, count) in enumerate(top_5_contracts, 1)
                ],
                'all_deposit_transactions': [
                    {
                        'hash': tx['hash'],
                        'from': tx['from'],
                        'to': tx['to'],
                        'amount_usdt': tx['amount_usdt'],
                        'timestamp': tx['timeStamp'],
                        'datetime': datetime.fromtimestamp(int(tx['timeStamp']), tz=timezone.utc).isoformat(),
                        'method_name': tx.get('tx_details', {}).get('method_name', 'unknown'),
                        'gas_used': tx.get('gasUsed', '0'),
                        'gas_price': tx.get('gasPrice', '0')
                    }
                    for tx in deposit_transfers
                ]
            }
            
            # 保存JSON文件
            json_filename = f"usdt_deposit_analysis_{timestamp}.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            
            # 保存简化报告
            txt_filename = f"usdt_deposit_analysis_{timestamp}.txt"
            txt_filepath = os.path.join(output_dir, txt_filename)
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"USDT大额Deposit交易分析报告\n")
                f.write(f"{'='*50}\n")
                f.write(f"分析时间: {datetime.now()}\n")
                f.write(f"查询范围: 过去24小时\n")
                f.write(f"最小金额: {self.min_amount:,} USDT\n")
                f.write(f"Deposit交易数: {stats['total_transactions']} 笔\n")
                f.write(f"总金额: {stats['total_amount']:,.2f} USDT\n")
                f.write(f"平均金额: {stats['average_amount']:,.2f} USDT\n\n")
                
                f.write(f"转入地址最多的合约前5名:\n")
                f.write(f"{'-'*50}\n")
                for i, (addr, count) in enumerate(top_5_contracts, 1):
                    info = contract_info.get(addr, {})
                    total_amount = sum(
                        transfer['amount_usdt'] for transfer in deposit_transfers
                        if Web3.to_checksum_address(transfer['to']) == addr
                    )
                    f.write(f"{i}. {info.get('name', 'Unknown')}\n")
                    f.write(f"   地址: {addr}\n")
                    f.write(f"   转入次数: {count} 次\n")
                    f.write(f"   总金额: {total_amount:,.2f} USDT\n\n")
            
            print(f"\n💾 结果已保存:")
            print(f"   📄 详细数据: {json_filepath}")
            print(f"   📝 文本报告: {txt_filepath}")
            
            return json_filepath, txt_filepath
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")
            return None, None
    
    def analyze_all_transfers(self, transfers):
        """分析所有转账，统计交互次数最多的合约"""
        print(f"🔍 分析所有转账交易，统计交互次数...")
        
        # 统计转入地址
        destination_counter = Counter()
        contract_info = {}
        
        for i, transfer in enumerate(transfers, 1):
            if i % 100 == 0 or i == len(transfers):
                print(f"   处理进度: {i}/{len(transfers)}")
            
            to_address = transfer['to']
            destination_counter[to_address] += 1
            
            # 检查是否是已知合约
            if to_address not in contract_info:
                contract_name = KNOWN_CONTRACTS.get(to_address, "Unknown")
                
                # 检查是否是合约地址
                is_contract = self.is_contract_address(to_address)
                
                contract_info[to_address] = {
                    'is_contract': is_contract,
                    'name': contract_name,
                    'total_amount': 0,
                    'transaction_count': 0
                }
            
            # 累加金额和交易次数
            contract_info[to_address]['total_amount'] += transfer['amount_usdt']
            contract_info[to_address]['transaction_count'] += 1
        
        # 只保留合约地址
        contract_destinations = {
            addr: contract_info[addr] for addr in destination_counter.keys()
            if contract_info[addr]['is_contract']
        }
        
        print(f"📋 转入的合约地址数量: {len(contract_destinations)}")
        
        return contract_destinations, destination_counter
    
    def analyze(self):
        """执行完整分析"""
        try:
            print(f"🚀 开始分析USDT交易...")
            print(f"⏰ 查询{self.start_time_str} 到 {self.end_time_str} UTC的USDT转账")
            print(f"📊 筛选大于{self.min_amount} USDT的转账")
            print(f"🎯 列出交互数量大于10的所有合约，按交互数量排序")
            print("=" * 60)
            
            # 使用分段查询获取USDT转账记录
            print(f"🔄 使用分段查询方式获取转账记录...")
            all_transfers = self.get_usdt_transfers_by_time_segments(segment_minutes=10)
            
            if not all_transfers:
                print("❌ 未找到任何转账记录")
                return
            
            print(f"📦 获取到总计 {len(all_transfers)} 笔USDT转账")
            
            # 处理大于指定金额的转账
            processed_transfers = self.filter_large_amounts(all_transfers)
            
            if not processed_transfers:
                print(f"❌ 未发现大于{self.min_amount} USDT的转账数据")
                return
            
            # 分析所有转账，统计合约交互
            contract_destinations, destination_counter = self.analyze_all_transfers(processed_transfers)
            
            if not contract_destinations:
                print(f"❌ 未发现转入合约地址的转账")
                return
            
            # 筛选交互数量大于10的合约，按交互数量排序
            filtered_contracts = [
                (addr, info) for addr, info in contract_destinations.items()
                if info['transaction_count'] > 10
            ]
            
            sorted_contracts = sorted(
                filtered_contracts,
                key=lambda x: x[1]['transaction_count'],
                reverse=True
            )
            
            print(f"\n🎯 交互数量大于10的合约: {len(sorted_contracts)} 个")
            
            # 计算统计信息
            stats = {
                'total_amount': sum(info['total_amount'] for info in contract_destinations.values()),
                'total_transactions': len(processed_transfers),
                'contract_count': len(contract_destinations),
                'filtered_contract_count': len(sorted_contracts),
                'average_amount': sum(transfer['amount_usdt'] for transfer in processed_transfers) / len(processed_transfers) if processed_transfers else 0,
                'query_date': '2024-10-24',
                'min_amount': self.min_amount,
                'min_interactions': 10
            }
            
            # 显示结果
            self.format_filtered_results(processed_transfers, sorted_contracts, stats)
            
            # 保存结果
            self.save_filtered_results(processed_transfers, sorted_contracts, stats)
            
            print(f"\n✅ 分析完成!")
            
        except Exception as e:
            raise Exception(f"分析失败: {e}")
    
    def format_filtered_results(self, all_transfers, sorted_contracts, stats):
        """格式化并显示筛选后的交易分析结果"""
        print(f"\n📊 USDT交易分析结果")
        print("=" * 80)
        print(f"⏰ 分析时间范围: {stats['query_date']} UTC 全天")
        print(f"💰 最小金额: {stats['min_amount']:,} USDT")
        print(f"� 最小交互次数: {stats['min_interactions']} 次")
        print(f"�🏦 总交易数: {stats['total_transactions']:,} 笔")
        print(f"💵 总金额: {stats['total_amount']:,.2f} USDT")
        print(f"📈 平均金额: {stats['average_amount']:,.2f} USDT")
        print(f"🏗️ 总合约数: {stats['contract_count']} 个")
        print(f"🎯 符合条件的合约数: {stats['filtered_contract_count']} 个")
        print("=" * 80)
        
        print(f"\n🏆 交互数量大于{stats['min_interactions']}的所有合约 (按交互数量排序):")
        print("-" * 80)
        for i, (address, info) in enumerate(sorted_contracts, 1):
            print(f"#{i}. {info['name']}")
            print(f"     🏠 地址: {address}")
            print(f"     📊 交互次数: {info['transaction_count']} 次")
            print(f"     💰 总金额: {info['total_amount']:,.2f} USDT")
            print(f"     📏 平均金额: {info['total_amount']/info['transaction_count']:,.2f} USDT")
            print(f"     📏 合约状态: {'✅ 已验证合约' if info['is_contract'] else '❌ 非合约地址'}")
            print()
        
        # 显示金额分布
        amount_ranges = {
            "1K-10K USDT": 0,
            "10K-100K USDT": 0,
            "100K-1M USDT": 0,
            "1M-10M USDT": 0,
            "> 10M USDT": 0
        }
        
        for transfer in all_transfers:
            amount = transfer['amount_usdt']
            if amount >= 10000000:
                amount_ranges["> 10M USDT"] += 1
            elif amount >= 1000000:
                amount_ranges["1M-10M USDT"] += 1
            elif amount >= 100000:
                amount_ranges["100K-1M USDT"] += 1
            elif amount >= 10000:
                amount_ranges["10K-100K USDT"] += 1
            elif amount >= 1000:
                amount_ranges["1K-10K USDT"] += 1
        
        print(f"📈 金额分布:")
        for range_name, count in amount_ranges.items():
            if count > 0:  # 只显示有数据的范围
                print(f"   {range_name}: {count} 笔")
        
        # 显示时间分布
        hour_distribution = {}
        for transfer in all_transfers:
            dt = datetime.fromtimestamp(int(transfer['timeStamp']), tz=timezone.utc)
            hour = dt.hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
        
        if hour_distribution:
            print(f"\n⏰ 24小时分布 (UTC时间，显示最活跃的8个时段):")
            sorted_hours = sorted(hour_distribution.items(), key=lambda x: x[1], reverse=True)
            for hour, count in sorted_hours[:8]:
                print(f"   {hour:02d}:00-{hour:02d}:59: {count} 笔")
    
    def save_filtered_results(self, all_transfers, sorted_contracts, stats, output_dir="temp"):
        """保存筛选后的结果到文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存详细数据
            result = {
                'analysis_time': datetime.now().isoformat(),
                'query_date': stats['query_date'],
                'query_period': f"{stats['query_date']} UTC全天",
                'min_amount': stats['min_amount'],
                'min_interactions': stats['min_interactions'],
                'statistics': stats,
                'filtered_contracts': [
                    {
                        'rank': i,
                        'address': addr,
                        'name': info['name'],
                        'transaction_count': info['transaction_count'],
                        'total_amount': info['total_amount'],
                        'average_amount': info['total_amount'] / info['transaction_count'],
                        'is_contract': info['is_contract']
                    }
                    for i, (addr, info) in enumerate(sorted_contracts, 1)
                ],
                'all_transactions': [
                    {
                        'hash': tx['hash'],
                        'from': tx['from'],
                        'to': tx['to'],
                        'amount_usdt': tx['amount_usdt'],
                        'timestamp': tx['timeStamp'],
                        'datetime': datetime.fromtimestamp(int(tx['timeStamp']), tz=timezone.utc).isoformat(),
                        'gas_used': tx.get('gasUsed', '0'),
                        'gas_price': tx.get('gasPrice', '0')
                    }
                    for tx in all_transfers
                ]
            }
            
            # 保存JSON文件
            json_filename = f"usdt_analysis_{stats['query_date'].replace('-', '')}_{timestamp}.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            
            # 保存简化报告
            txt_filename = f"usdt_analysis_{stats['query_date'].replace('-', '')}_{timestamp}.txt"
            txt_filepath = os.path.join(output_dir, txt_filename)
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"USDT交易分析报告\n")
                f.write(f"{'='*50}\n")
                f.write(f"分析时间: {datetime.now()}\n")
                f.write(f"查询日期: {stats['query_date']} UTC全天\n")
                f.write(f"最小金额: {stats['min_amount']:,} USDT\n")
                f.write(f"最小交互次数: {stats['min_interactions']} 次\n")
                f.write(f"总交易数: {stats['total_transactions']:,} 笔\n")
                f.write(f"总金额: {stats['total_amount']:,.2f} USDT\n")
                f.write(f"平均金额: {stats['average_amount']:,.2f} USDT\n")
                f.write(f"总合约数: {stats['contract_count']} 个\n")
                f.write(f"符合条件的合约数: {stats['filtered_contract_count']} 个\n\n")
                
                f.write(f"交互数量大于{stats['min_interactions']}的合约 (按交互数量排序):\n")
                f.write(f"{'-'*70}\n")
                for i, (addr, info) in enumerate(sorted_contracts, 1):
                    f.write(f"{i}. {info['name']}\n")
                    f.write(f"   地址: {addr}\n")
                    f.write(f"   交互次数: {info['transaction_count']} 次\n")
                    f.write(f"   总金额: {info['total_amount']:,.2f} USDT\n")
                    f.write(f"   平均金额: {info['total_amount']/info['transaction_count']:,.2f} USDT\n\n")
            
            print(f"\n💾 结果已保存:")
            print(f"   📄 详细数据: {json_filepath}")
            print(f"   📝 文本报告: {txt_filepath}")
            
            return json_filepath, txt_filepath
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")
            return None, None

def main():
    """主函数"""
    print("💰 USDT交易分析工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("📖 功能说明:")
        print("  分析指定UTC时间范围内的USDT转账")
        print("  筛选大于指定金额的交易")
        print("  列出交互数量大于10的所有合约，按交互数量排序")
        print()
        print("📝 使用方法:")
        print(f"  python {sys.argv[0]} [start_time_utc] [end_time_utc] [min_amount]")
        print()
        print("🕐 UTC时间格式:")
        print("  - YYYY-MM-DD HH:MM:SS  (如: 2025-10-24 00:00:00)")
        print("  - YYYY-MM-DDTHH:MM:SS  (如: 2025-10-24T00:00:00)")
        print("  - YYYY-MM-DD           (如: 2025-10-24，默认00:00:00)")
        print("  ⚠️  注意：所有时间均为UTC时间，请确保输入正确的UTC时间")
        print()
        print("💰 最小金额:")
        print("  - 数字形式，单位为USDT (如: 1000, 500, 10000)")
        print("  - 默认值: 1000 USDT")
        print()
        print("🔧 环境变量配置 (.env文件):")
        print("  ETHERSCAN_API_KEY=YourEtherscanApiKey")
        print("  WEB3_RPC_URL=https://eth.llamarpc.com")
        print()
        print("📊 分析内容:")
        print("  - 指定UTC时间范围的USDT转账记录")
        print("  - 筛选 >= 指定金额的转账")
        print("  - 统计转入合约地址的交互次数")
        print("  - 列出交互次数 > 10的所有合约")
        print("  - 按交互数量降序排列")
        print("  - 保存详细结果到文件")
        print()
        print("📋 示例:")
        print(f"  python {sys.argv[0]} '2025-10-24 00:00:00' '2025-10-24 23:59:59'")
        print(f"  python {sys.argv[0]} '2025-10-24' '2025-10-25' 500")
        print(f"  python {sys.argv[0]} '2024-10-24 00:00:00' '2024-10-24 23:59:59' 10000")
        print("  # 分析2024年10月24日UTC全天，筛选大于10000 USDT的交易")
        return
    
    try:
        # 获取参数
        start_time = None
        end_time = None
        min_amount = None
        
        if len(sys.argv) >= 3:
            start_time = sys.argv[1]
            end_time = sys.argv[2]
            print(f"📅 使用命令行参数:")
            print(f"   开始时间: {start_time}")
            print(f"   结束时间: {end_time}")
            
            # 检查是否提供了最小金额参数
            if len(sys.argv) >= 4:
                try:
                    min_amount = float(sys.argv[3])
                    print(f"   最小金额: {min_amount} USDT")
                except ValueError:
                    print(f"⚠️ 警告: 无效的最小金额参数 '{sys.argv[3]}'，使用默认值1000 USDT")
                    min_amount = None
        else:
            # 使用默认时间范围或交互式输入
            print("📝 未指定时间参数，将使用默认UTC时间范围 2025-10-24")
            print("   如需指定UTC时间，请使用: python usdt_deposit_analyzer.py '开始时间UTC' '结束时间UTC' [最小金额]")
            
            # 可选择交互式输入
            user_input = input("是否要手动输入UTC时间范围？(y/N): ").strip().lower()
            if user_input in ['y', 'yes']:
                print("请输入UTC时间（所有时间均为UTC时区）：")
                start_time = input("开始时间UTC (如 2025-10-24 00:00:00): ").strip()
                end_time = input("结束时间UTC (如 2025-10-24 23:59:59): ").strip()
                min_amount_input = input("最小金额USDT (如 1000，留空使用默认值): ").strip()
                
                if not start_time or not end_time:
                    print("❌ 时间不能为空，使用默认UTC时间范围")
                    start_time = None
                    end_time = None
                
                if min_amount_input:
                    try:
                        min_amount = float(min_amount_input)
                    except ValueError:
                        print(f"⚠️ 警告: 无效的最小金额 '{min_amount_input}'，使用默认值")
                        min_amount = None
        
        # 创建分析器实例
        analyzer = USDTDepositAnalyzer(start_time, end_time, min_amount)
        
        # 执行分析
        analyzer.analyze()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()