#!/usr/bin/env python3
"""
Concrete_STABLE 相关地址交互分析器
读取地址列表文件，分析这些地址在过去24小时的交互情况
"""

import os
import sys
import time
import requests
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict, Counter
from dotenv import load_dotenv

load_dotenv()

# USDT 合约地址 (ERC-20)
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

class AddressListAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.etherscan.io/v2/api"
        self.addresses = []
        self.interaction_data = defaultdict(lambda: defaultdict(int))
        self.common_interactions = Counter()
        
    def read_address_file(self, file_path):
        """读取地址文件"""
        addresses = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 使用正则表达式提取地址
            address_pattern = r'0x[a-fA-F0-9]{40}'
            found_addresses = re.findall(address_pattern, content)
            
            # 去重并过滤掉 Concrete_STABLE 地址本身
            concrete_stable = "0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f"
            addresses = list(set([addr.lower() for addr in found_addresses 
                                if addr.lower() != concrete_stable.lower()]))
            
            print(f"📋 从文件中读取到 {len(addresses)} 个唯一地址")
            self.addresses = addresses
            
            return addresses
            
        except Exception as e:
            print(f"❌ 读取文件出错: {e}")
            return []
    
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
    
    def get_address_transfers_24h(self, address, start_block, end_block):
        """获取指定地址在24小时内的转账记录"""
        params = {
            'chainid': '1',
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': USDT_CONTRACT_ADDRESS,
            'address': address,
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
                return []
                
        except Exception as e:
            print(f"⚠️ 获取地址 {address[:10]}... 转账记录失败: {e}")
            return []
    
    def analyze_address_interactions(self, batch_size=50, rest_minutes=1, max_addresses=None):
        """分析地址交互情况 - 支持批量处理和休息时间"""
        print("🔍 开始分析地址交互情况...")
        print("=" * 80)
        
        # 获取区块范围
        latest_block = self.get_latest_block()
        if not latest_block:
            return
        
        blocks_per_hour = 240  # 约 15 秒一个块
        start_block = latest_block - (24 * blocks_per_hour)
        
        print(f"📊 分析区块范围: {start_block:,} - {latest_block:,} (最近24小时)")
        print(f"📋 待分析地址总数量: {len(self.addresses)}")
        
        # 确定要分析的地址
        analyze_addresses = self.addresses
        if max_addresses and max_addresses < len(self.addresses):
            analyze_addresses = self.addresses[:max_addresses]
            print(f"⚠️ 限制分析地址数量为: {max_addresses}")
        
        total_addresses = len(analyze_addresses)
        
        # 计算批次信息
        total_batches = (total_addresses + batch_size - 1) // batch_size
        
        print(f"🔄 批量处理计划:")
        print(f"   📦 批次大小: {batch_size} 个地址")
        print(f"   🛌 休息时间: {rest_minutes} 分钟")
        print(f"   � 总批次数: {total_batches}")
        print(f"   ⏱️ 预计总时间: {total_batches * rest_minutes:.1f} 分钟 (不含分析时间)")
        
        # 存储所有交互对手
        all_counterparts = Counter()
        address_interactions = {}
        
        # 开始批量处理
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_addresses)
            batch_addresses = analyze_addresses[start_idx:end_idx]
            
            print(f"\n" + "="*60)
            print(f"🔥 处理批次 {batch_num + 1}/{total_batches}")
            print(f"📋 地址范围: {start_idx + 1} - {end_idx} (共 {len(batch_addresses)} 个)")
            print("="*60)
            
            # 处理当前批次的地址
            for i, address in enumerate(batch_addresses, 1):
                global_index = start_idx + i
                print(f"📊 总进度: {global_index}/{total_addresses} | 批次进度: {i}/{len(batch_addresses)} - {address[:10]}...{address[-6:]}")
                
                # 获取转账记录
                transfers = self.get_address_transfers_24h(address, start_block, latest_block)
                
                if not transfers:
                    continue
                
                # 分析交互对手
                counterparts = set()
                sent_to = Counter()
                received_from = Counter()
                
                for tx in transfers:
                    try:
                        from_addr = tx['from'].lower()
                        to_addr = tx['to'].lower()
                        amount = float(Decimal(tx['value']) / Decimal(10**6))
                        
                        # 如果当前地址是发送方
                        if from_addr == address:
                            counterparts.add(to_addr)
                            sent_to[to_addr] += amount
                            all_counterparts[to_addr] += 1
                        
                        # 如果当前地址是接收方
                        if to_addr == address:
                            counterparts.add(from_addr)
                            received_from[from_addr] += amount
                            all_counterparts[from_addr] += 1
                            
                    except (ValueError, KeyError):
                        continue
                
                address_interactions[address] = {
                    'counterparts': counterparts,
                    'sent_to': dict(sent_to),
                    'received_from': dict(received_from),
                    'total_counterparts': len(counterparts)
                }
                
                # API 限制 - 每个请求间隔
                time.sleep(0.2)
            
            # 批次完成提示
            print(f"✅ 批次 {batch_num + 1} 完成! 已分析 {end_idx} / {total_addresses} 个地址")
            
            # 如果不是最后一个批次，则休息
            if batch_num < total_batches - 1:
                rest_seconds = rest_minutes * 60
                print(f"💤 休息 {rest_minutes} 分钟以避免API限制...")
                print(f"⏰ 下一批次将在 {rest_seconds} 秒后开始")
                
                # 显示倒计时
                for remaining in range(rest_seconds, 0, -10):
                    if remaining % 30 == 0 or remaining <= 10:
                        print(f"   ⏳ 剩余休息时间: {remaining} 秒")
                    time.sleep(10 if remaining > 10 else remaining)
                    if remaining <= 10:
                        break
                
                print(f"🚀 休息结束，继续下一批次...")
        
        print(f"\n🎉 所有批次处理完成!")
        print(f"📊 总计分析了 {len(address_interactions)} 个地址")
        
        return address_interactions, all_counterparts
    
    def find_common_interactions(self, address_interactions, min_interactions=2):
        """找出被多个地址交互过的共同地址"""
        print(f"\n🔍 查找共同交互地址 (至少与 {min_interactions} 个地址交互)...")
        
        # 统计每个地址被多少个源地址交互过
        interaction_count = Counter()
        
        for source_addr, data in address_interactions.items():
            for counterpart in data['counterparts']:
                interaction_count[counterpart] += 1
        
        # 筛选出共同交互地址
        common_addresses = {addr: count for addr, count in interaction_count.items() 
                          if count >= min_interactions}
        
        return common_addresses
    
    def display_results(self, address_interactions, common_addresses):
        """显示分析结果"""
        print(f"\n" + "=" * 100)
        print("📊 地址交互分析结果")
        print("=" * 100)
        
        total_analyzed = len(address_interactions)
        total_interactions = sum(len(data['counterparts']) for data in address_interactions.values())
        
        print(f"🎯 分析地址数量: {total_analyzed}")
        print(f"🔗 总交互次数: {total_interactions}")
        print(f"🤝 共同交互地址: {len(common_addresses)}")
        
        if not common_addresses:
            print("\n✅ 没有发现被多个地址共同交互的地址")
            return
        
        # 按交互次数排序显示共同地址
        sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
        
        # 🎯 重点显示TOP 5共同交互地址
        print(f"\n🏆 TOP 5 共同交互地址 (最重要):")
        print("=" * 100)
        
        for i, (addr, count) in enumerate(sorted_common[:5], 1):
            percentage = (count / total_analyzed) * 100
            print(f"\n🥇 #{i}. {addr}")
            print(f"   📊 交互统计: 被 {count} 个地址交互 ({percentage:.1f}%)")
            print(f"   🔗 Etherscan: https://etherscan.io/address/{addr}")
            
            # 如果交互次数很高，给出特殊标注
            if percentage >= 50:
                print(f"   🚨 高度可疑: 超过一半的地址都与此地址交互!")
            elif percentage >= 30:
                print(f"   ⚠️  高度关注: 大量地址与此地址交互")
            elif percentage >= 15:
                print(f"   💡 重点关注: 较多地址与此地址交互")
        
        print(f"\n📋 完整TOP 20共同交互地址:")
        print("-" * 100)
        
        for i, (addr, count) in enumerate(sorted_common[:20], 1):
            percentage = (count / total_analyzed) * 100
            if i <= 5:
                print(f"{i:2d}. {addr} - 被 {count} 个地址交互 ({percentage:.1f}%) ⭐")
            else:
                print(f"{i:2d}. {addr} - 被 {count} 个地址交互 ({percentage:.1f}%)")
        
        # 分析高频交互地址
        high_freq_threshold = max(5, total_analyzed // 10)  # 至少5个或10%的地址
        high_freq_addresses = [addr for addr, count in common_addresses.items() 
                             if count >= high_freq_threshold]
        
        if high_freq_addresses:
            print(f"\n🚨 高频交互地址 (被至少 {high_freq_threshold} 个地址交互):")
            print("-" * 80)
            
            for addr in high_freq_addresses:
                count = common_addresses[addr]
                percentage = (count / total_analyzed) * 100
                star = "⭐" if addr in [item[0] for item in sorted_common[:5]] else ""
                print(f"   🔥 {addr} - {count} 次交互 ({percentage:.1f}%) {star}")
        
        # 🎯 生成TOP 5的详细分析摘要
        print(f"\n" + "=" * 100)
        print("🎯 TOP 5 地址分析摘要")
        print("=" * 100)
        
        for i, (addr, count) in enumerate(sorted_common[:5], 1):
            percentage = (count / total_analyzed) * 100
            risk_level = "🚨极高" if percentage >= 50 else "⚠️高" if percentage >= 30 else "💡中等" if percentage >= 15 else "📊一般"
            print(f"#{i}. {addr[:10]}...{addr[-6:]} - {count}次交互 ({percentage:.1f}%) - 风险等级: {risk_level}")
        
        # 保存详细结果
        self.save_interaction_results(address_interactions, common_addresses, sorted_common[:5])
    
    def save_interaction_results(self, address_interactions, common_addresses, top5_addresses=None):
        """保存交互分析结果"""
        try:
            # 确保 temp 目录存在
            os.makedirs('temp', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存详细JSON结果
            json_filename = f"temp/address_interactions_analysis_{timestamp}.json"
            
            # 准备TOP 5数据
            top5_data = []
            if top5_addresses:
                for i, (addr, count) in enumerate(top5_addresses, 1):
                    percentage = (count / len(address_interactions)) * 100
                    risk_level = "极高" if percentage >= 50 else "高" if percentage >= 30 else "中等" if percentage >= 15 else "一般"
                    top5_data.append({
                        "rank": i,
                        "address": addr,
                        "interaction_count": count,
                        "percentage": round(percentage, 2),
                        "risk_level": risk_level
                    })
            
            result_data = {
                'analysis_time': datetime.now().isoformat(),
                'analysis_period': '24 hours',
                'total_addresses_analyzed': len(address_interactions),
                'summary': {
                    'total_interactions': sum(len(data['counterparts']) for data in address_interactions.values()),
                    'common_addresses_count': len(common_addresses),
                    'high_frequency_addresses': [addr for addr, count in common_addresses.items() if count >= 5]
                },
                'top5_most_common_interactions': top5_data,
                'common_interactions': dict(common_addresses),
                'detailed_interactions': {
                    addr: {
                        'total_counterparts': data['total_counterparts'],
                        'counterparts_list': list(data['counterparts'])
                    } for addr, data in address_interactions.items()
                }
            }
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存到: {json_filename}")
            
            # 保存简化的共同地址列表
            txt_filename = f"temp/common_interaction_addresses_{timestamp}.txt"
            
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Concrete_STABLE 相关地址的共同交互地址列表\n")
                f.write(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 分析期间: 过去24小时\n")
                f.write(f"# 分析地址数: {len(address_interactions)}\n")
                f.write(f"# 共同交互地址数: {len(common_addresses)}\n\n")
                
                # 特别标注TOP 5
                f.write("="*80 + "\n")
                f.write("🏆 TOP 5 最重要的共同交互地址\n")
                f.write("="*80 + "\n")
                
                if top5_addresses:
                    for i, (addr, count) in enumerate(top5_addresses, 1):
                        percentage = (count / len(address_interactions)) * 100
                        risk_level = "极高" if percentage >= 50 else "高" if percentage >= 30 else "中等" if percentage >= 15 else "一般"
                        f.write(f"#{i}. {addr} - {count} 次交互 ({percentage:.1f}%) - 风险等级: {risk_level}\n")
                        f.write(f"    🔗 https://etherscan.io/address/{addr}\n\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("📋 完整共同交互地址列表\n")
                f.write("="*80 + "\n")
                
                sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
                
                for i, (addr, count) in enumerate(sorted_common, 1):
                    percentage = (count / len(address_interactions)) * 100
                    star = " ⭐" if i <= 5 else ""
                    f.write(f"{i:3d}. {addr} - {count} 次交互 ({percentage:.1f}%){star}\n")
            
            print(f"📝 共同地址列表已保存到: {txt_filename}")
            
            # 保存单独的TOP 5文件
            top5_filename = f"temp/top5_critical_addresses_{timestamp}.txt"
            
            with open(top5_filename, 'w', encoding='utf-8') as f:
                f.write(f"# TOP 5 最关键的共同交互地址\n")
                f.write(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 基于 {len(address_interactions)} 个 Concrete_STABLE 相关地址的交互分析\n\n")
                
                if top5_addresses:
                    for i, (addr, count) in enumerate(top5_addresses, 1):
                        percentage = (count / len(address_interactions)) * 100
                        risk_level = "极高" if percentage >= 50 else "高" if percentage >= 30 else "中等" if percentage >= 15 else "一般"
                        f.write(f"#{i}. {addr}\n")
                        f.write(f"   交互次数: {count} 次\n")
                        f.write(f"   交互比例: {percentage:.1f}%\n")
                        f.write(f"   风险等级: {risk_level}\n")
                        f.write(f"   Etherscan: https://etherscan.io/address/{addr}\n")
                        f.write(f"   建议: {'需要重点调查' if percentage >= 30 else '值得关注'}\n\n")
            
            print(f"🎯 TOP 5 关键地址已保存到: {top5_filename}")
            
        except Exception as e:
            print(f"⚠️ 保存结果时出错: {e}")

def main():
    """主函数"""
    print("🚀 Concrete_STABLE 相关地址交互分析器 - 增强版")
    print("=" * 70)
    
    # 检查 API 密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    
    if len(sys.argv) >= 2:
        # 命令行模式
        file_path = sys.argv[1]
        batch_size = int(sys.argv[2]) if len(sys.argv) >= 3 else 50
        rest_minutes = int(sys.argv[3]) if len(sys.argv) >= 4 else 1
        max_addresses = int(sys.argv[4]) if len(sys.argv) >= 5 else None
    else:
        # 交互模式
        file_path = input("请输入地址文件路径 (默认: temp/concrete_stable_addresses_20251024_153119.txt): ").strip()
        if not file_path:
            file_path = "temp/concrete_stable_addresses_20251024_153119.txt"
        
        try:
            batch_size = int(input("批次大小 (默认 50): ") or "50")
            rest_minutes = int(input("批次间休息时间(分钟) (默认 1): ") or "1")
            max_addresses_input = input("最大分析地址数 (默认分析全部，输入数字限制): ").strip()
            max_addresses = int(max_addresses_input) if max_addresses_input else None
        except ValueError:
            batch_size = 50
            rest_minutes = 1
            max_addresses = None
    
    if not api_key:
        if len(sys.argv) < 2:
            api_key = input("请输入 Etherscan API 密钥: ").strip()
        if not api_key:
            print("❌ API 密钥不能为空")
            return
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    try:
        # 创建分析器
        analyzer = AddressListAnalyzer(api_key)
        
        # 读取地址文件
        addresses = analyzer.read_address_file(file_path)
        if not addresses:
            print("❌ 没有读取到有效地址")
            return
        
        print(f"\n⚙️ 分析配置:")
        print(f"   📁 地址文件: {file_path}")
        print(f"   📋 总地址数: {len(addresses)}")
        print(f"   📦 批次大小: {batch_size}")
        print(f"   💤 休息时间: {rest_minutes} 分钟")
        if max_addresses:
            print(f"   🔢 限制数量: {max_addresses}")
        else:
            print(f"   🔢 分析范围: 全部地址")
        
        # 确认开始
        if len(sys.argv) < 2:  # 交互模式才需要确认
            confirm = input(f"\n确认开始分析? (y/N): ").strip().lower()
            if confirm != 'y':
                print("👋 分析已取消")
                return
        
        print(f"\n🚀 开始批量分析...")
        start_time = time.time()
        
        # 分析交互情况
        address_interactions, all_counterparts = analyzer.analyze_address_interactions(
            batch_size=batch_size, 
            rest_minutes=rest_minutes, 
            max_addresses=max_addresses
        )
        
        if not address_interactions:
            print("❌ 没有获取到交互数据")
            return
        
        # 查找共同交互地址
        common_addresses = analyzer.find_common_interactions(address_interactions, min_interactions=2)
        
        # 显示结果
        analyzer.display_results(address_interactions, common_addresses)
        
        # 显示总耗时
        end_time = time.time()
        total_time = end_time - start_time
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = int(total_time % 60)
        
        print(f"\n⏱️ 总分析时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"🎉 分析完成！")
        
    except KeyboardInterrupt:
        print(f"\n👋 分析已停止")
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()