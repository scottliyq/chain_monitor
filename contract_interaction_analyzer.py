#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合约交互分析工具
继承TokenDepositAnalyzer，增加合约地址参数
查询指定网络、代币、时间范围内与给定合约交互过的地址
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from web3 import Web3
from decimal import Decimal

# 导入父类
from token_deposit_analyzer import TokenDepositAnalyzer

# 导入地址标签查询器
try:
    from sqlite_address_querier import SQLiteAddressLabelQuerier
    HAS_ADDRESS_QUERIER = True
except ImportError:
    print("⚠️ sqlite_address_querier.py 未找到，地址标签功能将被禁用")
    HAS_ADDRESS_QUERIER = False

class ContractInteractionAnalyzer(TokenDepositAnalyzer):
    """合约交互分析器，继承TokenDepositAnalyzer"""
    
    def __init__(self, contract_address, start_time=None, end_time=None, min_amount=None, network="ethereum", token="USDT"):
        """初始化合约交互分析器
        
        Args:
            contract_address (str): 目标合约地址
            start_time (str): 开始时间，格式如 "2025-10-24 00:00:00"
            end_time (str): 结束时间，格式如 "2025-10-24 23:59:59"
            min_amount (float): 最小转账金额，默认100
            network (str): 区块链网络 ("ethereum", "arbitrum", "base", "bsc")，默认"ethereum"
            token (str): 代币名称 ("USDT", "USDC", "DAI", 等)，默认"USDT"
        """
        # 验证合约地址
        if not contract_address or not contract_address.startswith('0x') or len(contract_address) != 42:
            raise ValueError(f"无效的合约地址: {contract_address}")
        
        self.target_contract_address = Web3.to_checksum_address(contract_address)
        
        # 调用父类构造函数，降低默认最小金额到100
        if min_amount is None:
            min_amount = 100  # 降低默认最小金额以获取更多交互数据
        
        super().__init__(start_time, end_time, min_amount, network, token)
        
        # 设置logger（确保从父类继承）
        self.logger = logging.getLogger(__name__)
        
        # 初始化地址标签查询器（在类初始化时打开连接）
        self.address_querier = None
        if HAS_ADDRESS_QUERIER:
            try:
                self.address_querier = SQLiteAddressLabelQuerier('address_labels.db')
                self.logger.info("🏷️ 地址标签查询器已启用")
            except Exception as e:
                self.logger.warning(f"⚠️ 地址标签查询器初始化失败: {e}")
        
        # 获取目标合约信息
        self.target_contract_info = self._get_target_contract_info()
        
        self.logger.info(f"🎯 目标合约地址: {self.target_contract_address}")
        self.logger.info(f"📋 合约名称: {self.target_contract_info.get('name', 'Unknown')}")
        self.logger.info(f"🔍 分析目标: 查找与此合约交互过的地址")
        self.logger.info("")
    
    def __del__(self):
        """析构函数，关闭数据库连接"""
        if hasattr(self, 'address_querier') and self.address_querier:
            try:
                self.address_querier.close()
            except:
                pass
    
    def _get_target_contract_info(self):
        """获取目标合约信息"""
        try:
            # 检查是否为合约地址
            is_contract, address_type = self.is_contract_address(self.target_contract_address)
            
            if not is_contract:
                self.logger.warning(f"⚠️ 警告: {self.target_contract_address} 可能不是合约地址")
            
            # 获取合约名称
            contract_name = self.get_contract_name(self.target_contract_address)
            
            # 获取地址标签（如果可用）
            address_label = "Unknown"
            if self.address_querier:
                try:
                    label_info = self.address_querier.get_address_label(self.target_contract_address, self.network, is_contract_checker=self.is_contract_address)
                    address_label = label_info.get('label', contract_name)
                except:
                    address_label = contract_name
            else:
                address_label = contract_name
            
            return {
                'address': self.target_contract_address,
                'name': contract_name,
                'label': address_label,
                'is_contract': is_contract,
                'address_type': address_type
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取合约信息失败: {e}")
            return {
                'address': self.target_contract_address,
                'name': 'Unknown',
                'label': 'Unknown',
                'is_contract': True,
                'address_type': 'Contract'
            }
    
    def analyze_contract_interactions(self):
        """分析与目标合约的交互"""
        try:
            self.logger.info(f"🚀 开始分析与合约 {self.target_contract_address} 的{self.token}交互...")
            self.logger.info(f"⏰ 查询{self.start_time_str} 到 {self.end_time_str} UTC的{self.token}转账")
            self.logger.info(f"📊 筛选大于{self.min_amount} {self.token}的转账")
            self.logger.info("=" * 80)
            
            # 使用优化的分段查询获取已筛选的大额转账记录
            self.logger.info(f"🔄 使用优化分段查询方式获取大额转账记录...")
            large_transfers = self.get_usdt_transfers_by_time_segments(segment_minutes=10)
            
            if not large_transfers:
                self.logger.error("❌ 未找到任何大额转账记录")
                return self._generate_empty_result()
            
            self.logger.info(f"� 获取到总计 {len(large_transfers)} 笔大额{self.token}转账")
            self.logger.info(f"   💵 总金额: {sum(t['amount_usdt'] for t in large_transfers):,.2f} {self.token}")
            self.logger.info(f"   � 平均金额: {sum(t['amount_usdt'] for t in large_transfers) / len(large_transfers):,.2f} {self.token}")
            
            # 筛选与目标合约交互的转账
            contract_interactions = self._filter_contract_interactions(large_transfers)
            
            if not contract_interactions:
                self.logger.error(f"❌ 未发现与合约 {self.target_contract_address} 的交互")
                return self._generate_empty_result()
            
            self.logger.info(f"🎯 与目标合约交互的转账: {len(contract_interactions)} 笔")
            
            # 分析交互地址
            interaction_analysis = self._analyze_interaction_addresses(contract_interactions)
            
            # 获取交易详情
            detailed_interactions = self._enrich_with_transaction_details(contract_interactions)
            
            # 计算统计信息
            stats = self._calculate_interaction_stats(contract_interactions, interaction_analysis)
            
            # 显示结果
            self._format_interaction_results(detailed_interactions, interaction_analysis, stats)
            
            # 保存结果
            self._save_interaction_results(detailed_interactions, interaction_analysis, stats)
            
            self.logger.info(f"\n✅ 合约交互分析完成!")
            
            return {
                'interactions': detailed_interactions,
                'analysis': interaction_analysis,
                'statistics': stats
            }
            
        except Exception as e:
            self.logger.error(f"❌ 分析失败: {e}")
            raise Exception(f"合约交互分析失败: {e}")
    
    def _filter_contract_interactions(self, transfers):
        """筛选与目标合约交互的转账"""
        contract_interactions = []
        
        self.logger.info(f"🔍 筛选与合约 {self.target_contract_address} 的交互...")
        
        for transfer in transfers:
            # 检查转账的发送方或接收方是否为目标合约
            from_addr = Web3.to_checksum_address(transfer['from'])
            to_addr = Web3.to_checksum_address(transfer['to'])
            
            if (from_addr == self.target_contract_address or 
                to_addr == self.target_contract_address):
                
                # 标记交互类型
                if to_addr == self.target_contract_address:
                    transfer['interaction_type'] = 'deposit'  # 转入目标合约
                    transfer['user_address'] = from_addr
                else:
                    transfer['interaction_type'] = 'withdraw'  # 从目标合约转出
                    transfer['user_address'] = to_addr
                
                contract_interactions.append(transfer)
        
        return contract_interactions
    
    def _analyze_interaction_addresses(self, interactions):
        """分析交互地址"""
        self.logger.info(f"🔍 分析交互地址...")
        
        user_stats = defaultdict(lambda: {
            'total_deposit': 0,
            'total_withdraw': 0,
            'deposit_count': 0,
            'withdraw_count': 0,
            'total_amount': 0,
            'total_count': 0,
            'first_interaction': None,
            'last_interaction': None,
            'address_info': {}
        })
        
        interaction_types = Counter()
        
        for interaction in interactions:
            user_addr = interaction['user_address']
            interaction_type = interaction['interaction_type']
            amount = interaction['amount_usdt']
            timestamp = int(interaction['timeStamp'])
            
            # 统计交互类型
            interaction_types[interaction_type] += 1
            
            # 统计用户数据
            user_data = user_stats[user_addr]
            
            if interaction_type == 'deposit':
                user_data['total_deposit'] += amount
                user_data['deposit_count'] += 1
            else:  # withdraw
                user_data['total_withdraw'] += amount
                user_data['withdraw_count'] += 1
            
            user_data['total_amount'] += amount
            user_data['total_count'] += 1
            
            # 更新时间范围
            if user_data['first_interaction'] is None or timestamp < user_data['first_interaction']:
                user_data['first_interaction'] = timestamp
            if user_data['last_interaction'] is None or timestamp > user_data['last_interaction']:
                user_data['last_interaction'] = timestamp
        
        # 获取地址信息（合约检查和标签）
        self.logger.info(f"🏷️ 获取地址信息和标签...")
        for user_addr in user_stats.keys():
            try:
                # 检查是否为合约地址
                is_contract, addr_type = self.is_contract_address(user_addr)
                
                address_info = {
                    'is_contract': is_contract,
                    'address_type': addr_type,
                    'label': 'Unknown',
                    'contract_name': 'Unknown'
                }
                
                if is_contract:
                    # 获取合约名称
                    contract_name = self.get_contract_name(user_addr)
                    address_info['contract_name'] = contract_name
                    address_info['label'] = contract_name
                
                # 获取地址标签（如果可用）
                if self.address_querier:
                    try:
                        label_info = self.address_querier.get_address_label(user_addr, self.network, is_contract_checker=self.is_contract_address)
                        if label_info.get('label') != 'Unknown Address':
                            address_info['label'] = label_info.get('label', address_info['label'])
                    except:
                        pass
                
                user_stats[user_addr]['address_info'] = address_info
                
            except Exception as e:
                self.logger.warning(f"⚠️ 获取地址信息失败 {user_addr}: {e}")
                user_stats[user_addr]['address_info'] = {
                    'is_contract': False,
                    'address_type': 'Unknown',
                    'label': 'Unknown',
                    'contract_name': 'Unknown'
                }
            
            time.sleep(0.05)  # 避免RPC限制
        
        return {
            'user_statistics': dict(user_stats),
            'interaction_types': dict(interaction_types),
            'unique_users': len(user_stats),
            'total_interactions': len(interactions)
        }
    
    def _enrich_with_transaction_details(self, interactions):
        """为交互添加交易详情"""
        self.logger.info(f"🔍 获取交易详情...")
        
        enriched_interactions = []
        
        for i, interaction in enumerate(interactions, 1):
            if i % 10 == 0 or i == len(interactions):
                self.logger.info(f"   处理进度: {i}/{len(interactions)}")
            
            # 获取交易详情
            tx_details = self.get_transaction_details(interaction['hash'])
            
            enriched_interaction = interaction.copy()
            
            if tx_details:
                enriched_interaction['tx_details'] = {
                    'method_name': tx_details.get('method_name', 'unknown'),
                    'method_selector': tx_details.get('method_selector'),
                    'gas': tx_details.get('gas', 0),
                    'gas_price': tx_details.get('gas_price', 0)
                }
            else:
                enriched_interaction['tx_details'] = {
                    'method_name': 'unknown',
                    'method_selector': None,
                    'gas': 0,
                    'gas_price': 0
                }
            
            enriched_interactions.append(enriched_interaction)
            time.sleep(0.05)  # 避免RPC限制
        
        return enriched_interactions
    
    def _calculate_interaction_stats(self, interactions, analysis):
        """计算交互统计信息"""
        total_deposit = sum(
            tx['amount_usdt'] for tx in interactions 
            if tx['interaction_type'] == 'deposit'
        )
        total_withdraw = sum(
            tx['amount_usdt'] for tx in interactions 
            if tx['interaction_type'] == 'withdraw'
        )
        
        # 时间分布
        hour_distribution = defaultdict(int)
        for interaction in interactions:
            hour = datetime.fromtimestamp(int(interaction['timeStamp']), tz=timezone.utc).hour
            hour_distribution[hour] += 1
        
        # 金额分布
        amount_ranges = {
            f"100-1K {self.token}": 0,
            f"1K-10K {self.token}": 0,
            f"10K-100K {self.token}": 0,
            f"100K-1M {self.token}": 0,
            f"1M+ {self.token}": 0
        }
        
        for interaction in interactions:
            amount = interaction['amount_usdt']
            if amount >= 1000000:
                amount_ranges[f"1M+ {self.token}"] += 1
            elif amount >= 100000:
                amount_ranges[f"100K-1M {self.token}"] += 1
            elif amount >= 10000:
                amount_ranges[f"10K-100K {self.token}"] += 1
            elif amount >= 1000:
                amount_ranges[f"1K-10K {self.token}"] += 1
            else:
                amount_ranges[f"100-1K {self.token}"] += 1
        
        query_date = datetime.fromtimestamp(self.start_time, tz=timezone.utc).strftime('%Y-%m-%d')
        
        return {
            'query_date': query_date,
            'target_contract': self.target_contract_info,
            'total_interactions': len(interactions),
            'unique_users': analysis['unique_users'],
            'total_deposit': total_deposit,
            'total_withdraw': total_withdraw,
            'net_flow': total_deposit - total_withdraw,
            'deposit_count': analysis['interaction_types'].get('deposit', 0),
            'withdraw_count': analysis['interaction_types'].get('withdraw', 0),
            'hour_distribution': dict(hour_distribution),
            'amount_ranges': amount_ranges,
            'min_amount': self.min_amount,
            'network': self.network,
            'token': self.token
        }
    
    def _format_interaction_results(self, interactions, analysis, stats):
        """格式化并显示交互分析结果"""
        self.logger.info(f"📊 合约交互分析结果")
        self.logger.info("=" * 80)
        self.logger.info(f"🎯 目标合约: {stats['target_contract']['label']}")
        self.logger.info(f"🏠 合约地址: {stats['target_contract']['address']}")
        self.logger.info(f"⏰ 分析时间: {stats['query_date']} UTC 全天")
        self.logger.info(f"🌐 网络: {self.network_config['name']}")
        self.logger.info(f"🪙 代币: {self.token}")
        self.logger.info(f"💰 最小金额: {stats['min_amount']:,} {self.token}")
        self.logger.info("=" * 80)
        
        self.logger.info(f"📈 交互统计:")
        self.logger.info(f"   💰 总交互数: {stats['total_interactions']} 笔")
        self.logger.info(f"   👥 唯一用户数: {stats['unique_users']} 个")
        self.logger.info(f"   ⬇️  存入次数: {stats['deposit_count']} 笔")
        self.logger.info(f"   ⬆️  提取次数: {stats['withdraw_count']} 笔")
        self.logger.info(f"   💵 总存入: {stats['total_deposit']:,.2f} {self.token}")
        self.logger.info(f"   💸 总提取: {stats['total_withdraw']:,.2f} {self.token}")
        self.logger.info(f"   📊 净流入: {stats['net_flow']:,.2f} {self.token}")
        
        # 显示TOP用户
        user_stats = analysis['user_statistics']
        top_users = sorted(
            user_stats.items(),
            key=lambda x: x[1]['total_amount'],
            reverse=True
        )[:10]
        
        self.logger.info(f"\n🏆 交互金额最大的前10个地址:")
        self.logger.info("-" * 80)
        for i, (addr, data) in enumerate(top_users, 1):
            addr_info = data['address_info']
            self.logger.info(f"#{i}. {addr_info['label']}")
            self.logger.info(f"     🏠 地址: {addr}")
            self.logger.info(f"     🏷️ 类型: {addr_info['address_type']}")
            self.logger.info(f"     💰 总金额: {data['total_amount']:,.2f} {self.token}")
            self.logger.info(f"     📊 总次数: {data['total_count']} 次")
            self.logger.info(f"     ⬇️  存入: {data['deposit_count']} 次, {data['total_deposit']:,.2f} {self.token}")
            self.logger.info(f"     ⬆️  提取: {data['withdraw_count']} 次, {data['total_withdraw']:,.2f} {self.token}")
            
            if data['first_interaction'] and data['last_interaction']:
                first_time = datetime.fromtimestamp(data['first_interaction'], tz=timezone.utc)
                last_time = datetime.fromtimestamp(data['last_interaction'], tz=timezone.utc)
                self.logger.info(f"     ⏰ 首次: {first_time.strftime('%H:%M:%S')} UTC")
                self.logger.info(f"     ⏰ 最后: {last_time.strftime('%H:%M:%S')} UTC")
            self.logger.info("")
        
        # 显示金额分布
        self.logger.info(f"📈 金额分布:")
        for range_name, count in stats['amount_ranges'].items():
            if count > 0:
                self.logger.info(f"   {range_name}: {count} 笔")
        
        # 显示时间分布
        if stats['hour_distribution']:
            self.logger.info(f"\n⏰ 24小时分布 (UTC时间，显示最活跃的8个时段):")
            sorted_hours = sorted(stats['hour_distribution'].items(), key=lambda x: x[1], reverse=True)
            for hour, count in sorted_hours[:8]:
                self.logger.info(f"   {hour:02d}:00-{hour:02d}:59: {count} 笔")
    
    def _save_interaction_results(self, interactions, analysis, stats, output_dir="temp"):
        """保存交互分析结果到文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            contract_short = stats['target_contract']['address'][-8:].lower()
            
            # 保存详细数据
            result = {
                'analysis_time': datetime.now().isoformat(),
                'query_date': stats['query_date'],
                'target_contract': stats['target_contract'],
                'network': stats['network'],
                'token': stats['token'],
                'min_amount': stats['min_amount'],
                'address_labels_enabled': HAS_ADDRESS_QUERIER and self.address_querier is not None,
                'statistics': stats,
                'user_analysis': {
                    'total_unique_users': analysis['unique_users'],
                    'user_details': [
                        {
                            'address': addr,
                            'label': data['address_info']['label'],
                            'address_type': data['address_info']['address_type'],
                            'is_contract': data['address_info']['is_contract'],
                            'total_amount': data['total_amount'],
                            'total_interactions': data['total_count'],
                            'deposit_count': data['deposit_count'],
                            'withdraw_count': data['withdraw_count'],
                            'total_deposit': data['total_deposit'],
                            'total_withdraw': data['total_withdraw'],
                            'net_deposit': data['total_deposit'] - data['total_withdraw'],
                            'first_interaction': data['first_interaction'],
                            'last_interaction': data['last_interaction']
                        }
                        for addr, data in analysis['user_statistics'].items()
                    ]
                },
                'all_interactions': [
                    {
                        'hash': tx['hash'],
                        'user_address': tx['user_address'],
                        'interaction_type': tx['interaction_type'],
                        'amount': tx['amount_usdt'],
                        'timestamp': tx['timeStamp'],
                        'datetime': datetime.fromtimestamp(int(tx['timeStamp']), tz=timezone.utc).isoformat(),
                        'method_name': tx.get('tx_details', {}).get('method_name', 'unknown'),
                        'gas_used': tx.get('gasUsed', '0'),
                        'gas_price': tx.get('gasPrice', '0')
                    }
                    for tx in interactions
                ]
            }
            
            # 保存JSON文件
            json_filename = f"{self.network}_{self.token.lower()}_contract_{contract_short}_interaction_{stats['query_date'].replace('-', '')}_{timestamp}.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            
            # 保存简化报告
            txt_filename = f"{self.network}_{self.token.lower()}_contract_{contract_short}_interaction_{stats['query_date'].replace('-', '')}_{timestamp}.txt"
            txt_filepath = os.path.join(output_dir, txt_filename)
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"合约交互分析报告\n")
                f.write(f"{'='*50}\n")
                f.write(f"分析时间: {datetime.now()}\n")
                f.write(f"目标合约: {stats['target_contract']['label']}\n")
                f.write(f"合约地址: {stats['target_contract']['address']}\n")
                f.write(f"网络: {self.network_config['name']}\n")
                f.write(f"代币: {self.token}\n")
                f.write(f"查询日期: {stats['query_date']} UTC全天\n")
                f.write(f"最小金额: {stats['min_amount']:,} {self.token}\n")
                f.write(f"总交互数: {stats['total_interactions']} 笔\n")
                f.write(f"唯一用户数: {stats['unique_users']} 个\n")
                f.write(f"总存入: {stats['total_deposit']:,.2f} {self.token}\n")
                f.write(f"总提取: {stats['total_withdraw']:,.2f} {self.token}\n")
                f.write(f"净流入: {stats['net_flow']:,.2f} {self.token}\n")
                f.write(f"地址标签功能: {'启用' if HAS_ADDRESS_QUERIER else '禁用'}\n\n")
                
                # 写入用户详情
                user_stats = analysis['user_statistics']
                top_users = sorted(
                    user_stats.items(),
                    key=lambda x: x[1]['total_amount'],
                    reverse=True
                )
                
                f.write(f"交互用户详情 (按交互金额排序):\n")
                f.write(f"{'-'*70}\n")
                for i, (addr, data) in enumerate(top_users, 1):
                    addr_info = data['address_info']
                    f.write(f"{i}. {addr_info['label']}\n")
                    f.write(f"   地址: {addr}\n")
                    f.write(f"   类型: {addr_info['address_type']}\n")
                    f.write(f"   总金额: {data['total_amount']:,.2f} {self.token}\n")
                    f.write(f"   总次数: {data['total_count']} 次\n")
                    f.write(f"   存入: {data['deposit_count']} 次, {data['total_deposit']:,.2f} {self.token}\n")
                    f.write(f"   提取: {data['withdraw_count']} 次, {data['total_withdraw']:,.2f} {self.token}\n\n")
            
            self.logger.info(f"\n💾 结果已保存:")
            self.logger.info(f"   📄 详细数据: {json_filepath}")
            self.logger.info(f"   📝 文本报告: {txt_filepath}")
            
            return json_filepath, txt_filepath
            
        except Exception as e:
            self.logger.error(f"⚠️ 保存文件失败: {e}")
            return None, None
    
    def _generate_empty_result(self):
        """生成空结果"""
        query_date = datetime.fromtimestamp(self.start_time, tz=timezone.utc).strftime('%Y-%m-%d')
        
        empty_stats = {
            'query_date': query_date,
            'target_contract': self.target_contract_info,
            'total_interactions': 0,
            'unique_users': 0,
            'total_deposit': 0,
            'total_withdraw': 0,
            'net_flow': 0,
            'deposit_count': 0,
            'withdraw_count': 0,
            'hour_distribution': {},
            'amount_ranges': {},
            'min_amount': self.min_amount,
            'network': self.network,
            'token': self.token
        }
        
        empty_analysis = {
            'user_statistics': {},
            'interaction_types': {},
            'unique_users': 0,
            'total_interactions': 0
        }
        
        self._format_interaction_results([], empty_analysis, empty_stats)
        self._save_interaction_results([], empty_analysis, empty_stats)
        
        return {
            'interactions': [],
            'analysis': empty_analysis,
            'statistics': empty_stats
        }

def main():
    """主函数"""
    print("🎯 合约交互分析工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("📖 功能说明:")
        print("  分析指定时间范围内与给定合约交互过的地址")
        print("  支持多个区块链网络和多种代币")
        print("  统计存入/提取行为和交互模式")
        print()
        print("📝 使用方法:")
        print(f"  python {sys.argv[0]} contract_address [start_time_utc] [end_time_utc] [min_amount] [network] [token]")
        print()
        print("🎯 必需参数:")
        print("  contract_address  - 目标合约地址 (42位十六进制，以0x开头)")
        print()
        print("🌐 支持的网络:")
        print("  - ethereum (默认) - 以太坊主网")
        print("  - arbitrum       - Arbitrum One")
        print("  - base           - Base")
        print("  - bsc            - BNB Smart Chain")
        print()
        print("🪙 支持的代币:")
        print("  - USDT (默认)    - Tether USD")
        print("  - USDC           - USD Coin")
        print("  - DAI            - Dai Stablecoin")
        print("  - WETH           - Wrapped Ether")
        print("  - 其他ERC20代币   - 需要在address_constant.py中配置")
        print()
        print("🕐 UTC时间格式:")
        print("  - YYYY-MM-DD HH:MM:SS  (如: 2025-10-24 00:00:00)")
        print("  - 默认: 2025-10-24 00:00:00 到 2025-10-24 23:59:59")
        print()
        print("💰 最小金额:")
        print("  - 数字形式，单位为所选代币 (如: 100, 1000, 10000)")
        print("  - 默认值: 100 (代币单位)")
        print()
        print("📊 分析内容:")
        print("  - 与目标合约的所有代币交互")
        print("  - 存入/提取行为统计")
        print("  - 交互用户地址分析")
        print("  - 时间分布和金额分布")
        print("  - 用户标签和合约识别")
        print()
        print("📋 示例:")
        print(f"  # 分析Uniswap V3 USDT/USDC池交互")
        print(f"  python {sys.argv[0]} 0x11b815efB8f581194ae79006d24E0d814B7697F6")
        print(f"  # 分析Compound USDT市场交互")
        print(f"  python {sys.argv[0]} 0x3Eb91D237e491E2Ac6683320c4AEDCaBcdFDD7F "
               "'2025-10-24 00:00:00' '2025-10-24 23:59:59' 1000")
        print(f"  # 分析Arbitrum网络合约交互")
        print(f"  python {sys.argv[0]} 0xContractAddress "
               "'2025-10-24 00:00:00' '2025-10-24 23:59:59' 100 arbitrum USDC")
        return
    
    try:
        # 解析命令行参数
        if len(sys.argv) < 2:
            print("❌ 错误: 请提供合约地址")
            print(f"使用方法: python {sys.argv[0]} contract_address [start_time] [end_time] [min_amount] [network] [token]")
            print(f"获取帮助: python {sys.argv[0]} --help")
            sys.exit(1)
        
        contract_address = sys.argv[1]
        start_time = sys.argv[2] if len(sys.argv) > 2 else None
        end_time = sys.argv[3] if len(sys.argv) > 3 else None
        min_amount = float(sys.argv[4]) if len(sys.argv) > 4 else None
        network = sys.argv[5] if len(sys.argv) > 5 else "ethereum"
        token = sys.argv[6] if len(sys.argv) > 6 else "USDT"
        
        print(f"🎯 开始分析合约交互:")
        print(f"   📍 合约地址: {contract_address}")
        print(f"   🌐 网络: {network}")
        print(f"   🪙 代币: {token}")
        if start_time and end_time:
            print(f"   ⏰ 时间范围: {start_time} 到 {end_time} UTC")
        if min_amount:
            print(f"   💰 最小金额: {min_amount} {token}")
        print()
        
        # 创建分析器
        analyzer = ContractInteractionAnalyzer(
            contract_address=contract_address,
            start_time=start_time,
            end_time=end_time,
            min_amount=min_amount,
            network=network,
            token=token
        )
        
        # 执行分析
        result = analyzer.analyze_contract_interactions()
        
        print(f"\n✅ 分析完成!")
        print(f"   📊 总交互数: {result['statistics']['total_interactions']}")
        print(f"   👥 唯一用户: {result['statistics']['unique_users']}")
        print(f"   💰 净流入: {result['statistics']['net_flow']:,.2f} {token}")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()