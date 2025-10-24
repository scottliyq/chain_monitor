#!/usr/bin/env python3
"""
简化版地址交互分析器 - 不依赖外部库
读取地址列表文件，使用内置库进行基础分析
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from collections import defaultdict, Counter

# USDT 合约地址 (ERC-20)
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

class SimpleAddressAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.etherscan.io/v2/api"
        self.addresses = []
        
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
    
    def make_api_request(self, params):
        """使用内置库发送API请求"""
        try:
            # 构建URL
            query_string = urllib.parse.urlencode(params)
            url = f"{self.base_url}?{query_string}"
            
            # 发送请求
            response = urllib.request.urlopen(url, timeout=30)
            data = response.read().decode('utf-8')
            
            return json.loads(data)
            
        except Exception as e:
            print(f"⚠️ API 请求失败: {e}")
            return None
    
    def get_latest_block(self):
        """获取最新区块号"""
        params = {
            'chainid': '1',
            'module': 'proxy',
            'action': 'eth_blockNumber',
            'apikey': self.api_key
        }
        
        try:
            data = self.make_api_request(params)
            
            if data and 'result' in data:
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
            data = self.make_api_request(params)
            
            if data and data['status'] == '1' and 'result' in data:
                return data['result']
            else:
                return []
                
        except Exception as e:
            print(f"⚠️ 获取地址 {address[:10]}... 转账记录失败: {e}")
            return []
    
    def analyze_sample_addresses(self, sample_size=10):
        """分析样本地址的交互情况"""
        print("🔍 开始分析样本地址交互情况...")
        print("=" * 80)
        
        # 获取区块范围
        latest_block = self.get_latest_block()
        if not latest_block:
            print("❌ 无法获取最新区块，使用预估值")
            latest_block = 20915000  # 大概的当前区块
        
        blocks_per_hour = 240  # 约 15 秒一个块
        start_block = latest_block - (24 * blocks_per_hour)
        
        print(f"📊 分析区块范围: {start_block:,} - {latest_block:,} (最近24小时)")
        
        # 取样本地址
        sample_addresses = self.addresses[:sample_size]
        print(f"📋 分析样本地址数量: {len(sample_addresses)}")
        
        # 存储交互统计
        all_counterparts = Counter()
        address_interactions = {}
        
        for i, address in enumerate(sample_addresses, 1):
            print(f"\n📊 分析进度: {i}/{len(sample_addresses)}")
            print(f"   地址: {address[:10]}...{address[-6:]}")
            
            # 获取转账记录
            transfers = self.get_address_transfers_24h(address, start_block, latest_block)
            
            if not transfers:
                print(f"   ❌ 没有交易记录")
                continue
            
            print(f"   ✅ 获取到 {len(transfers)} 笔交易")
            
            # 分析交互对手
            counterparts = set()
            
            for tx in transfers:
                try:
                    from_addr = tx['from'].lower()
                    to_addr = tx['to'].lower()
                    
                    # 如果当前地址是发送方
                    if from_addr == address:
                        counterparts.add(to_addr)
                        all_counterparts[to_addr] += 1
                    
                    # 如果当前地址是接收方
                    if to_addr == address:
                        counterparts.add(from_addr)
                        all_counterparts[from_addr] += 1
                        
                except (ValueError, KeyError) as e:
                    continue
            
            address_interactions[address] = {
                'counterparts': list(counterparts),
                'total_counterparts': len(counterparts),
                'total_transactions': len(transfers)
            }
            
            print(f"   🔗 交互地址数: {len(counterparts)}")
            
            # 简单延时避免API限制
            import time
            time.sleep(0.5)
        
        return address_interactions, all_counterparts
    
    def find_common_interactions(self, all_counterparts, min_interactions=2):
        """找出被多个地址交互过的共同地址"""
        print(f"\n🔍 查找共同交互地址 (至少 {min_interactions} 次交互)...")
        
        # 筛选出共同交互地址
        common_addresses = {addr: count for addr, count in all_counterparts.items() 
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
        print(f"🔗 总交互对手数: {total_interactions}")
        print(f"🤝 共同交互地址: {len(common_addresses)}")
        
        if not common_addresses:
            print("\n✅ 在样本中没有发现被多个地址共同交互的地址")
            return
        
        # 按交互次数排序显示共同地址
        sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n🏆 共同交互地址列表:")
        print("-" * 100)
        
        for i, (addr, count) in enumerate(sorted_common, 1):
            percentage = (count / total_analyzed) * 100
            print(f"{i:2d}. {addr}")
            print(f"    🔗 交互次数: {count} ({percentage:.1f}%)")
            print(f"    🌐 Etherscan: https://etherscan.io/address/{addr}")
            print()
        
        # 保存结果
        self.save_simple_results(address_interactions, common_addresses)
    
    def save_simple_results(self, address_interactions, common_addresses):
        """保存简化的分析结果"""
        try:
            # 确保 temp 目录存在
            os.makedirs('temp', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存结果文件
            txt_filename = f"temp/sample_interaction_analysis_{timestamp}.txt"
            
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Concrete_STABLE 相关地址样本交互分析\n")
                f.write(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 分析期间: 过去24小时\n")
                f.write(f"# 样本地址数: {len(address_interactions)}\n")
                f.write(f"# 共同交互地址数: {len(common_addresses)}\n\n")
                
                f.write("=== 样本地址交互情况 ===\n")
                for addr, data in address_interactions.items():
                    f.write(f"{addr}: {data['total_counterparts']} 个交互地址, {data['total_transactions']} 笔交易\n")
                
                f.write(f"\n=== 共同交互地址 ===\n")
                sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
                
                for i, (addr, count) in enumerate(sorted_common, 1):
                    percentage = (count / len(address_interactions)) * 100
                    f.write(f"{i:3d}. {addr} - {count} 次交互 ({percentage:.1f}%)\n")
            
            print(f"\n💾 分析结果已保存到: {txt_filename}")
            
        except Exception as e:
            print(f"⚠️ 保存结果时出错: {e}")

def main():
    """主函数"""
    print("🚀 简化版地址交互分析器")
    print("=" * 60)
    
    # 默认参数
    file_path = "temp/concrete_stable_addresses_20251024_153119.txt"
    sample_size = 10
    
    # 获取API密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("⚠️ 请设置环境变量 ETHERSCAN_API_KEY 或手动输入")
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
        analyzer = SimpleAddressAnalyzer(api_key)
        
        # 读取地址文件
        addresses = analyzer.read_address_file(file_path)
        if not addresses:
            print("❌ 没有读取到有效地址")
            return
        
        print(f"\n⚠️ 注意: 为避免API限制，只分析前 {sample_size} 个地址作为样本")
        
        # 分析样本交互情况
        address_interactions, all_counterparts = analyzer.analyze_sample_addresses(sample_size)
        
        if not address_interactions:
            print("❌ 没有获取到交互数据")
            return
        
        # 查找共同交互地址
        common_addresses = analyzer.find_common_interactions(all_counterparts, min_interactions=2)
        
        # 显示结果
        analyzer.display_results(address_interactions, common_addresses)
        
        print(f"\n🎉 样本分析完成！")
        print(f"💡 如需分析更多地址，请考虑使用付费API计划")
        
    except KeyboardInterrupt:
        print(f"\n👋 分析已停止")
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")

if __name__ == "__main__":
    main()