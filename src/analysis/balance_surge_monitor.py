#!/usr/bin/env python3
"""
USDT 余额激增监控工具
专门监控最近24小时USDT余额新增超过5M，且48小时前余额<100k的地址
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()



# USDT 合约地址 (ERC-20)
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

class USDTBalanceSurgeMonitor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.etherscan.io/v2/api"
        
    def get_latest_block(self):
        """获取最新区块号"""
        params = {
            'chainid': '1',
            'module': 'proxy',
            'action': 'eth_blockNumber',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'result' in data:
                return int(data['result'], 16)
            else:
                print(f"❌ 获取最新区块失败: {data}")
                return None
                
        except Exception as e:
            print(f"❌ 获取最新区块出错: {e}")
            return None
    
    def get_usdt_balance(self, address, block_number=None):
        """获取指定地址在指定区块的USDT余额"""
        params = {
            'chainid': '1',
            'module': 'account',
            'action': 'tokenbalance',
            'contractaddress': USDT_CONTRACT_ADDRESS,
            'address': address,
            'tag': 'latest' if block_number is None else hex(block_number),
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1' and 'result' in data:
                balance = Decimal(data['result']) / Decimal(10**6)
                return float(balance)
            else:
                return None
                
        except Exception as e:
            return None
    
    def get_recent_transfers(self, start_block, end_block):
        """获取指定区块范围内的USDT转账"""
        params = {
            'chainid': '1',
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': USDT_CONTRACT_ADDRESS,
            'startblock': start_block,
            'endblock': end_block,
            'page': 1,
            'offset': 10000,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1' and 'result' in data:
                return data['result']
            else:
                print(f"❌ 获取转账记录失败: {data.get('message', '未知错误')}")
                return []
                
        except Exception as e:
            print(f"❌ 获取转账记录出错: {e}")
            return []
    
    def get_address_interactions(self, target_address, start_block=None, end_block=None):
        """
        获取与指定地址交互过的所有地址
        
        Args:
            target_address: 目标地址
            start_block: 开始区块号 (None 表示从很早开始)
            end_block: 结束区块号 (None 表示最新区块)
        
        Returns:
            包含交互信息的字典
        """
        print(f"🔍 分析与地址 {target_address} 的所有 USDT 交互...")
        
        # 如果没有指定区块范围，获取一个合理的范围
        if end_block is None:
            end_block = self.get_latest_block()
            if not end_block:
                return {}
        
        if start_block is None:
            # 从最新区块往前推30天 (约 172800 个区块)
            blocks_per_day = 240 * 24  # 每天约5760个区块
            start_block = max(1, end_block - (30 * blocks_per_day))
        
        print(f"📊 分析区块范围: {start_block:,} - {end_block:,}")
        
        # 获取作为发送方的转账
        print(f"📤 获取从 {target_address} 发出的转账...")
        outgoing_transfers = self._get_transfers_from_address(target_address, start_block, end_block)
        
        # 获取作为接收方的转账  
        print(f"📥 获取发送到 {target_address} 的转账...")
        incoming_transfers = self._get_transfers_to_address(target_address, start_block, end_block)
        
        # 分析交互地址
        interactions = self._analyze_interactions(
            target_address, outgoing_transfers, incoming_transfers
        )
        
        return interactions
    
    def _get_transfers_from_address(self, from_address, start_block, end_block):
        """获取从指定地址发出的转账"""
        # 使用 Etherscan API 的 tokentx action，通过 address 参数获取
        # 注意：这会获取该地址的所有代币转账，然后我们筛选出作为发送方的
        params = {
            'chainid': '1',
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': USDT_CONTRACT_ADDRESS,
            'address': from_address,
            'startblock': start_block,
            'endblock': end_block,
            'page': 1,
            'offset': 10000,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1' and 'result' in data:
                # 筛选出作为发送方的转账
                outgoing = [tx for tx in data['result'] if tx['from'].lower() == from_address.lower()]
                print(f"   找到 {len(outgoing)} 条发出的转账")
                return outgoing
            else:
                print(f"   ⚠️ 获取发出转账失败: {data.get('message', '未知错误')}")
                return []
                
        except Exception as e:
            print(f"   ❌ 获取发出转账出错: {e}")
            return []
    
    def _get_transfers_to_address(self, to_address, start_block, end_block):
        """获取发送到指定地址的转账"""
        # 同样使用 address 参数，然后筛选出作为接收方的
        params = {
            'chainid': '1',
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': USDT_CONTRACT_ADDRESS,
            'address': to_address,
            'startblock': start_block,
            'endblock': end_block,
            'page': 1,
            'offset': 10000,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == '1' and 'result' in data:
                # 筛选出作为接收方的转账
                incoming = [tx for tx in data['result'] if tx['to'].lower() == to_address.lower()]
                print(f"   找到 {len(incoming)} 条接收的转账")
                return incoming
            else:
                print(f"   ⚠️ 获取接收转账失败: {data.get('message', '未知错误')}")
                return []
                
        except Exception as e:
            print(f"   ❌ 获取接收转账出错: {e}")
            return []
    
    def _analyze_interactions(self, target_address, outgoing_transfers, incoming_transfers):
        """分析交互数据"""
        print(f"\n📊 分析交互数据...")
        
        # 统计发送给其他地址的金额
        sent_to = {}
        for tx in outgoing_transfers:
            to_addr = tx['to'].lower()
            amount = float(Decimal(tx['value']) / Decimal(10**6))
            
            if to_addr not in sent_to:
                sent_to[to_addr] = {
                    'total_amount': 0,
                    'transaction_count': 0,
                    'transactions': []
                }
            
            sent_to[to_addr]['total_amount'] += amount
            sent_to[to_addr]['transaction_count'] += 1
            sent_to[to_addr]['transactions'].append({
                'hash': tx['hash'],
                'amount': amount,
                'timestamp': int(tx['timeStamp']),
                'formatted_time': datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 统计从其他地址接收的金额
        received_from = {}
        for tx in incoming_transfers:
            from_addr = tx['from'].lower()
            amount = float(Decimal(tx['value']) / Decimal(10**6))
            
            if from_addr not in received_from:
                received_from[from_addr] = {
                    'total_amount': 0,
                    'transaction_count': 0,
                    'transactions': []
                }
            
            received_from[from_addr]['total_amount'] += amount
            received_from[from_addr]['transaction_count'] += 1
            received_from[from_addr]['transactions'].append({
                'hash': tx['hash'],
                'amount': amount,
                'timestamp': int(tx['timeStamp']),
                'formatted_time': datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 找出所有交互过的地址
        all_interacted_addresses = set(sent_to.keys()) | set(received_from.keys())
        
        # 生成综合交互信息
        interactions = {}
        for addr in all_interacted_addresses:
            sent_info = sent_to.get(addr, {'total_amount': 0, 'transaction_count': 0, 'transactions': []})
            received_info = received_from.get(addr, {'total_amount': 0, 'transaction_count': 0, 'transactions': []})
            
            # 计算净流量 (正数表示对方给target更多，负数表示target给对方更多)
            net_flow = received_info['total_amount'] - sent_info['total_amount']
            
            interactions[addr] = {
                'address': addr,
                'sent_to_target': received_info['total_amount'],  # 该地址发送给target的总额
                'received_from_target': sent_info['total_amount'],  # 该地址从target接收的总额
                'net_flow_to_target': net_flow,  # 净流入target的金额
                'total_sent_transactions': received_info['transaction_count'],
                'total_received_transactions': sent_info['transaction_count'],
                'total_transactions': sent_info['transaction_count'] + received_info['transaction_count'],
                'sent_transactions': received_info['transactions'],
                'received_transactions': sent_info['transactions']
            }
        
        return {
            'target_address': target_address,
            'analysis_summary': {
                'total_interacted_addresses': len(all_interacted_addresses),
                'total_outgoing_transfers': len(outgoing_transfers),
                'total_incoming_transfers': len(incoming_transfers),
                'total_sent_amount': sum(info['total_amount'] for info in sent_to.values()),
                'total_received_amount': sum(info['total_amount'] for info in received_from.values())
            },
            'interactions': interactions
        }
    
    def display_interactions(self, interactions_data):
        """显示交互分析结果"""
        target = interactions_data['target_address']
        summary = interactions_data['analysis_summary']
        interactions = interactions_data['interactions']
        
        print(f"\n" + "=" * 100)
        print(f"📊 地址交互分析报告")
        print("=" * 100)
        print(f"🎯 目标地址: {target}")
        print(f"📈 交互地址总数: {summary['total_interacted_addresses']:,}")
        print(f"📤 发出转账次数: {summary['total_outgoing_transfers']:,}")
        print(f"📥 接收转账次数: {summary['total_incoming_transfers']:,}")
        print(f"💸 总发出金额: {summary['total_sent_amount']:,.2f} USDT")
        print(f"💰 总接收金额: {summary['total_received_amount']:,.2f} USDT")
        print(f"💹 净流量: {summary['total_received_amount'] - summary['total_sent_amount']:,.2f} USDT")
        
        if not interactions:
            print("\n✅ 没有发现任何 USDT 交互记录")
            return
        
        # 按交互总金额排序
        sorted_interactions = sorted(
            interactions.values(), 
            key=lambda x: abs(x['sent_to_target']) + abs(x['received_from_target']), 
            reverse=True
        )
        
        print(f"\n🏆 TOP 20 交互地址 (按交互总金额排序):")
        print("-" * 100)
        
        for i, interaction in enumerate(sorted_interactions[:20], 1):
            addr = interaction['address']
            sent_to_target = interaction['sent_to_target']
            received_from_target = interaction['received_from_target']
            net_flow = interaction['net_flow_to_target']
            total_txs = interaction['total_transactions']
            
            print(f"\n{i:2d}. 📍 {addr}")
            print(f"    💰 发送给目标: {sent_to_target:,.2f} USDT")
            print(f"    💸 从目标接收: {received_from_target:,.2f} USDT")
            print(f"    💹 净流入目标: {net_flow:,.2f} USDT")
            print(f"    📊 交易次数: {total_txs}")
            print(f"    🔗 查看地址: https://etherscan.io/address/{addr}")
        
        # 显示主要资金提供者
        print(f"\n💰 主要资金提供者 (发送给目标最多):")
        print("-" * 60)
        top_senders = sorted(
            [x for x in interactions.values() if x['sent_to_target'] > 0],
            key=lambda x: x['sent_to_target'],
            reverse=True
        )[:10]
        
        for i, sender in enumerate(top_senders, 1):
            print(f"{i:2d}. {sender['address'][:10]}...{sender['address'][-6:]}: {sender['sent_to_target']:,.2f} USDT")
        
        # 显示主要资金接收者
        print(f"\n💸 主要资金接收者 (从目标接收最多):")
        print("-" * 60)
        top_receivers = sorted(
            [x for x in interactions.values() if x['received_from_target'] > 0],
            key=lambda x: x['received_from_target'],
            reverse=True
        )[:10]
        
        for i, receiver in enumerate(top_receivers, 1):
            print(f"{i:2d}. {receiver['address'][:10]}...{receiver['address'][-6:]}: {receiver['received_from_target']:,.2f} USDT")
    
    def monitor_balance_surge(self, min_increase=5000000, min_48h_balance=100000):
        """
        监控余额激增的地址
        
        Args:
            min_increase: 最小增长金额 (USDT)
            min_48h_balance: 48小时前的最大余额阈值 (USDT)
        """
        print("🚀 USDT余额激增监控器")
        print("=" * 60)
        print(f"📊 监控条件:")
        print(f"   ✅ 最近24小时余额增长 ≥ {min_increase:,.0f} USDT")
        print(f"   ✅ 48小时前余额 < {min_48h_balance:,.0f} USDT")
        print("=" * 60)
        
        # 1. 获取区块信息
        print("\n🧱 获取区块信息...")
        latest_block = self.get_latest_block()
        if not latest_block:
            return []
        
        blocks_per_hour = 240  # 约15秒一个块
        block_24h_ago = latest_block - (24 * blocks_per_hour)
        block_48h_ago = latest_block - (48 * blocks_per_hour)
        
        print(f"📈 最新区块: {latest_block:,}")
        print(f"📉 24小时前: {block_24h_ago:,}")
        print(f"📉 48小时前: {block_48h_ago:,}")
        
        # 2. 获取24小时内的转账记录
        print(f"\n🔄 获取最近24小时的USDT转账...")
        transfers = self.get_recent_transfers(block_24h_ago, latest_block)
        if not transfers:
            return []
        
        print(f"📋 获取到 {len(transfers):,} 条转账记录")
        
        # 3. 统计各地址接收的USDT数量
        print(f"\n📊 统计地址接收金额...")
        address_received = {}
        
        for tx in transfers:
            try:
                to_address = tx['to'].lower()
                amount = float(Decimal(tx['value']) / Decimal(10**6))
                
                if to_address in address_received:
                    address_received[to_address] += amount
                else:
                    address_received[to_address] = amount
                    
            except (ValueError, KeyError):
                continue
        
        # 4. 筛选接收金额超过阈值的地址
        candidates = []
        for address, received in address_received.items():
            if received >= min_increase:
                candidates.append((address, received))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        print(f"🎯 找到 {len(candidates)} 个候选地址（24小时接收 ≥ {min_increase:,.0f} USDT）")
        
        if not candidates:
            print("✅ 没有符合接收金额条件的地址")
            return []
        
        # 显示候选地址
        print(f"\n📝 候选地址列表:")
        for i, (addr, received) in enumerate(candidates, 1):
            print(f"   {i}. {addr} - 接收 {received:,.2f} USDT")
        
        # if len(candidates) > 10:
        #     print(f"   ... 还有 {len(candidates) - 10} 个地址")
        
        # 5. 检查48小时前余额
        print(f"\n🔍 检查候选地址的历史余额...")
        qualified = []
        
        for i, (address, received_amount) in enumerate(candidates, 1):
            print(f"\n检查 {i}/{len(candidates)}: {address[:12]}...{address[-8:]}")
            
            # 获取48小时前余额
            balance_48h_ago = self.get_usdt_balance(address, block_48h_ago)
            if balance_48h_ago is None:
                print(f"   ⚠️  无法获取48小时前余额")
                continue
            
            # 获取当前余额
            current_balance = self.get_usdt_balance(address)
            if current_balance is None:
                print(f"   ⚠️  无法获取当前余额")
                continue
            
            # 计算增长
            balance_increase = current_balance - balance_48h_ago
            increase_ratio = (balance_increase / max(balance_48h_ago, 1)) * 100
            
            print(f"   📊 48小时前: {balance_48h_ago:,.2f} USDT")
            print(f"   📊 当前余额: {current_balance:,.2f} USDT")
            print(f"   📈 余额增长: {balance_increase:,.2f} USDT")
            print(f"   📥 24小时接收: {received_amount:,.2f} USDT")
            print(f"   📊 增长倍数: {increase_ratio:,.1f}%")
            
            # 检查是否符合条件
            if balance_48h_ago < min_48h_balance and balance_increase >= min_increase:
                qualified.append({
                    'address': address,
                    'balance_48h_ago': balance_48h_ago,
                    'current_balance': current_balance,
                    'balance_increase': balance_increase,
                    'received_24h': received_amount,
                    'increase_ratio': increase_ratio,
                    'etherscan_url': f"https://etherscan.io/address/{address}"
                })
                print(f"   ✅ 符合条件！")
            else:
                reasons = []
                if balance_48h_ago >= min_48h_balance:
                    reasons.append(f"48小时前余额过高")
                if balance_increase < min_increase:
                    reasons.append(f"增长不足")
                print(f"   ❌ 不符合: {', '.join(reasons)}")
            
            # API限制
            time.sleep(0.2)
        
        # 6. 显示最终结果
        self.display_results(qualified, min_increase, min_48h_balance)
        return qualified
    
    def display_results(self, qualified_addresses, min_increase, min_48h_balance):
        """显示监控结果"""
        if not qualified_addresses:
            print(f"\n" + "=" * 80)
            print("🔍 监控结果")
            print("=" * 80)
            print("✅ 没有发现符合所有条件的地址")
            print(f"   条件1: 48小时前余额 < {min_48h_balance:,.0f} USDT")
            print(f"   条件2: 余额增长 ≥ {min_increase:,.0f} USDT")
            return
        
        # 按增长比例排序
        qualified_addresses.sort(key=lambda x: x['increase_ratio'], reverse=True)
        
        print(f"\n" + "=" * 100)
        print(f"🎉 发现 {len(qualified_addresses)} 个符合条件的地址!")
        print("=" * 100)
        
        total_increase = sum(addr['balance_increase'] for addr in qualified_addresses)
        print(f"📊 总计余额增长: {total_increase:,.2f} USDT")
        print(f"📊 平均增长倍数: {sum(addr['increase_ratio'] for addr in qualified_addresses) / len(qualified_addresses):,.1f}%")
        
        for i, addr in enumerate(qualified_addresses, 1):
            print(f"\n🏆 #{i} 地址: {addr['address']}")
            print(f"   📊 48小时前余额: {addr['balance_48h_ago']:,.2f} USDT")
            print(f"   📊 当前余额: {addr['current_balance']:,.2f} USDT")
            print(f"   📈 余额增长: {addr['balance_increase']:,.2f} USDT")
            print(f"   📥 24小时接收: {addr['received_24h']:,.2f} USDT")
            print(f"   📊 增长倍数: {addr['increase_ratio']:,.1f}%")
            print(f"   🔗 查看详情: {addr['etherscan_url']}")
        
        # 保存结果
        self.save_results(qualified_addresses, min_increase, min_48h_balance)
    
    def save_results(self, results, min_increase, min_48h_balance):
        """保存结果到JSON文件"""
        try:
            # 确保 temp 目录存在
            import os
            os.makedirs('temp', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"temp/usdt_balance_surge_{timestamp}.json"
            
            data = {
                'query_time': datetime.now().isoformat(),
                'parameters': {
                    'min_increase': min_increase,
                    'min_48h_balance': min_48h_balance
                },
                'summary': {
                    'qualified_count': len(results),
                    'total_increase': sum(r['balance_increase'] for r in results)
                },
                'results': results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存到: {filename}")
            
        except Exception as e:
            print(f"⚠️ 保存文件时出错: {e}")

def main():
    """主函数"""
    api_key = os.getenv('ETHERSCAN_API_KEY')
    
    print("🚀 USDT 分析工具")
    print("=" * 50)
    print("请选择功能:")
    print("1. 📈 余额激增监控")
    print("2. 🔍 地址交互分析")
    print("3. 🎯 分析 Concrete_STABLE 地址")
    
    if len(sys.argv) >= 2 and sys.argv[1] not in ['1', '2', '3']:
        # 命令行模式 - 余额监控
        if not api_key:
            print("❌ 环境变量 ETHERSCAN_API_KEY 未设置")
            print("📝 获取免费 API 密钥: https://etherscan.io/apis")
            sys.exit(1)
        
        min_increase = float(sys.argv[1]) if len(sys.argv) >= 2 else 5000000
        min_48h_balance = float(sys.argv[2]) if len(sys.argv) >= 3 else 100000
        
        monitor = USDTBalanceSurgeMonitor(api_key)
        results = monitor.monitor_balance_surge(min_increase, min_48h_balance)
        
        if results:
            print(f"\n🎯 监控完成！发现 {len(results)} 个符合条件的地址")
        else:
            print(f"\n✅ 监控完成！未发现符合条件的地址")
        return
    
    # 交互模式
    if not api_key:
        api_key = input("请输入 Etherscan API 密钥: ").strip()
        if not api_key:
            print("❌ API 密钥不能为空")
            return
    
    choice = input("\n请选择功能 (1-3): ").strip()
    
    if choice == "1":
        # 余额激增监控
        try:
            min_increase = float(input("最小增长金额 (USDT, 默认 5000000): ") or "5000000")
            min_48h_balance = float(input("48小时前最大余额 (USDT, 默认 100000): ") or "100000")
        except ValueError:
            print("❌ 输入格式错误")
            return
        
        monitor = USDTBalanceSurgeMonitor(api_key)
        results = monitor.monitor_balance_surge(min_increase, min_48h_balance)
        
        if results:
            print(f"\n🎯 监控完成！发现 {len(results)} 个符合条件的地址")
        else:
            print(f"\n✅ 监控完成！未发现符合条件的地址")
            
    elif choice == "2":
        # 地址交互分析
        target_address = input("请输入要分析的地址: ").strip()
        if not target_address:
            print("❌ 地址不能为空")
            return
        
        # 可选的区块范围
        use_custom_range = input("是否指定区块范围？(y/N): ").strip().lower() == 'y'
        start_block = None
        end_block = None
        
        if use_custom_range:
            try:
                days_back = int(input("分析最近多少天的数据 (默认 30): ") or "30")
                monitor = USDTBalanceSurgeMonitor(api_key)
                latest_block = monitor.get_latest_block()
                if latest_block:
                    blocks_per_day = 240 * 24  # 每天约5760个区块
                    start_block = max(1, latest_block - (days_back * blocks_per_day))
                    end_block = latest_block
                    print(f"📊 将分析最近 {days_back} 天的数据")
            except ValueError:
                print("❌ 输入格式错误，使用默认范围")
        
        monitor = USDTBalanceSurgeMonitor(api_key)
        interactions = monitor.get_address_interactions(target_address, start_block, end_block)
        
        if interactions:
            monitor.display_interactions(interactions)
            
            # 保存结果
            try:
                # 确保 temp 目录存在
                import os
                os.makedirs('temp', exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"temp/address_interactions_{target_address[:10]}_{timestamp}.json"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(interactions, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 详细结果已保存到: {filename}")
                
            except Exception as e:
                print(f"⚠️ 保存文件时出错: {e}")
        else:
            print("❌ 无法获取交互数据")
            
    elif choice == "3":
        # 分析 Concrete_STABLE 地址
        print(f"\n🎯 分析 Concrete_STABLE 地址: {Concrete_STABLE}")
        
        # 可选的区块范围
        use_custom_range = input("是否指定分析范围？(y/N): ").strip().lower() == 'y'
        start_block = None
        end_block = None
        
        if use_custom_range:
            try:
                days_back = int(input("分析最近多少天的数据 (默认 30): ") or "30")
                monitor = USDTBalanceSurgeMonitor(api_key)
                latest_block = monitor.get_latest_block()
                if latest_block:
                    blocks_per_day = 240 * 24
                    start_block = max(1, latest_block - (days_back * blocks_per_day))
                    end_block = latest_block
                    print(f"📊 将分析最近 {days_back} 天的数据")
            except ValueError:
                print("❌ 输入格式错误，使用默认范围")
        
        monitor = USDTBalanceSurgeMonitor(api_key)
        interactions = monitor.get_address_interactions(Concrete_STABLE, start_block, end_block)
        
        if interactions:
            monitor.display_interactions(interactions)
            
            # 保存结果
            try:
                # 确保 temp 目录存在
                import os
                os.makedirs('temp', exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"temp/concrete_stable_interactions_{timestamp}.json"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(interactions, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 详细结果已保存到: {filename}")
                
            except Exception as e:
                print(f"⚠️ 保存文件时出错: {e}")
        else:
            print("❌ 无法获取交互数据")
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main()


# 历史兼容别名
BalanceSurgeMonitor = USDTBalanceSurgeMonitor
