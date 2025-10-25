#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地址交集分析工具
分析USDT分析结果JSON文件和Concrete Stable地址列表TXT文件中的共同地址
"""

import json
import re
import os
from datetime import datetime
from typing import Set, List, Dict, Tuple
from collections import defaultdict


class AddressIntersectionAnalyzer:
    """地址交集分析器"""
    
    def __init__(self, json_file_path: str, txt_file_path: str):
        """
        初始化分析器
        
        Args:
            json_file_path: USDT分析结果JSON文件路径
            txt_file_path: Concrete Stable地址列表TXT文件路径
        """
        self.json_file_path = json_file_path
        self.txt_file_path = txt_file_path
        self.json_addresses = set()
        self.txt_addresses = set()
        self.intersection_addresses = set()
        self.json_address_details = {}
        self.txt_address_details = {}
        
    def extract_addresses_from_json(self) -> Set[str]:
        """从JSON文件中提取所有地址"""
        print(f"📖 读取JSON文件: {self.json_file_path}")
        
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            addresses = set()
            address_details = defaultdict(list)
            
            # 从transactions中提取from和to地址
            if 'all_transactions' in data:
                for tx in data['all_transactions']:
                    from_addr = tx.get('from', '').lower()
                    to_addr = tx.get('to', '').lower()
                    amount = tx.get('amount_usdt', 0)
                    timestamp = tx.get('timestamp', '')
                    datetime_str = tx.get('datetime', '')
                    
                    if from_addr:
                        addresses.add(from_addr)
                        address_details[from_addr].append({
                            'type': 'from',
                            'amount': amount,
                            'timestamp': timestamp,
                            'datetime': datetime_str,
                            'hash': tx.get('hash', '')
                        })
                    
                    if to_addr:
                        addresses.add(to_addr)
                        address_details[to_addr].append({
                            'type': 'to',
                            'amount': amount,
                            'timestamp': timestamp,
                            'datetime': datetime_str,
                            'hash': tx.get('hash', '')
                        })
            
            # 从filtered_contracts中提取地址（如果有）
            if 'filtered_contracts' in data:
                for contract in data['filtered_contracts']:
                    if 'address' in contract:
                        addr = contract['address'].lower()
                        addresses.add(addr)
                        address_details[addr].append({
                            'type': 'contract',
                            'interactions': contract.get('interactions', 0),
                            'total_amount': contract.get('total_amount', 0)
                        })
            
            self.json_addresses = addresses
            self.json_address_details = dict(address_details)
            
            print(f"   ✅ 从JSON文件提取到 {len(addresses)} 个地址")
            return addresses
            
        except Exception as e:
            print(f"   ❌ 读取JSON文件失败: {e}")
            return set()
    
    def extract_addresses_from_txt(self) -> Set[str]:
        """从TXT文件中提取所有地址"""
        print(f"📖 读取TXT文件: {self.txt_file_path}")
        
        try:
            with open(self.txt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            addresses = set()
            address_details = {}
            
            # 使用正则表达式匹配地址和USDT金额
            # 匹配格式: 序号. 0x地址 - 金额 USDT
            pattern = r'^\s*\d+\.\s+(0x[a-fA-F0-9]{40})\s+-\s+([\d,]+\.?\d*)\s+USDT'
            
            for line in content.split('\n'):
                match = re.match(pattern, line.strip())
                if match:
                    addr = match.group(1).lower()
                    amount_str = match.group(2).replace(',', '')
                    try:
                        amount = float(amount_str)
                        addresses.add(addr)
                        address_details[addr] = {
                            'usdt_amount': amount,
                            'original_line': line.strip()
                        }
                    except ValueError:
                        continue
            
            self.txt_addresses = addresses
            self.txt_address_details = address_details
            
            print(f"   ✅ 从TXT文件提取到 {len(addresses)} 个地址")
            return addresses
            
        except Exception as e:
            print(f"   ❌ 读取TXT文件失败: {e}")
            return set()
    
    def find_intersection(self) -> Set[str]:
        """找出两个文件中的共同地址"""
        print(f"\n🔍 查找共同地址...")
        
        intersection = self.json_addresses.intersection(self.txt_addresses)
        self.intersection_addresses = intersection
        
        print(f"   ✅ 找到 {len(intersection)} 个共同地址")
        return intersection
    
    def analyze_common_addresses(self) -> List[Dict]:
        """分析共同地址的详细信息"""
        print(f"\n📊 分析共同地址详细信息...")
        
        common_analysis = []
        
        for addr in self.intersection_addresses:
            analysis = {
                'address': addr,
                'json_details': self.json_address_details.get(addr, []),
                'txt_details': self.txt_address_details.get(addr, {}),
                'summary': {}
            }
            
            # 分析JSON中的活动
            json_details = self.json_address_details.get(addr, [])
            if json_details:
                total_amount_as_from = sum(item['amount'] for item in json_details if item.get('type') == 'from')
                total_amount_as_to = sum(item['amount'] for item in json_details if item.get('type') == 'to')
                tx_count = len([item for item in json_details if item.get('type') in ['from', 'to']])
                
                analysis['summary'] = {
                    'transaction_count': tx_count,
                    'total_sent': total_amount_as_from,
                    'total_received': total_amount_as_to,
                    'net_flow': total_amount_as_to - total_amount_as_from
                }
            
            # 添加TXT中的USDT余额信息
            txt_details = self.txt_address_details.get(addr, {})
            if txt_details:
                analysis['summary']['concrete_stable_amount'] = txt_details.get('usdt_amount', 0)
            
            common_analysis.append(analysis)
        
        # 按交易金额排序
        common_analysis.sort(key=lambda x: x['summary'].get('concrete_stable_amount', 0), reverse=True)
        
        return common_analysis
    
    def generate_report(self, analysis_results: List[Dict]) -> str:
        """生成分析报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        report_lines = [
            "# 地址交集分析报告",
            f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# JSON文件: {os.path.basename(self.json_file_path)}",
            f"# TXT文件: {os.path.basename(self.txt_file_path)}",
            "",
            f"## 分析概要",
            f"- JSON文件地址总数: {len(self.json_addresses)}",
            f"- TXT文件地址总数: {len(self.txt_addresses)}",
            f"- 共同地址数量: {len(self.intersection_addresses)}",
            f"- 重叠率: {len(self.intersection_addresses) / max(len(self.json_addresses), 1) * 100:.2f}%",
            "",
            "## 共同地址详细信息",
            ""
        ]
        
        for i, addr_info in enumerate(analysis_results, 1):
            addr = addr_info['address']
            summary = addr_info['summary']
            txt_details = addr_info['txt_details']
            
            report_lines.extend([
                f"### {i}. {addr}",
                f"**Concrete Stable余额**: {txt_details.get('usdt_amount', 0):,.2f} USDT",
                ""
            ])
            
            if summary:
                if summary.get('transaction_count', 0) > 0:
                    report_lines.extend([
                        f"**USDT交易活动**:",
                        f"- 交易笔数: {summary.get('transaction_count', 0)}",
                        f"- 发送总额: {summary.get('total_sent', 0):,.2f} USDT",
                        f"- 接收总额: {summary.get('total_received', 0):,.2f} USDT",
                        f"- 净流入: {summary.get('net_flow', 0):,.2f} USDT",
                        ""
                    ])
                
                # 显示具体交易
                json_details = addr_info['json_details']
                if json_details and len(json_details) <= 10:  # 只显示前10笔交易
                    report_lines.append("**交易详情**:")
                    for detail in json_details[:10]:
                        if detail.get('type') in ['from', 'to']:
                            direction = "发送" if detail['type'] == 'from' else "接收"
                            report_lines.append(f"- {direction}: {detail.get('amount', 0):,.2f} USDT ({detail.get('datetime', 'N/A')})")
                    report_lines.append("")
            
            report_lines.append("---")
            report_lines.append("")
        
        return '\n'.join(report_lines)
    
    def save_results(self, analysis_results: List[Dict]) -> Tuple[str, str]:
        """保存分析结果到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细报告
        report_filename = f"temp/address_intersection_report_{timestamp}.md"
        report_content = self.generate_report(analysis_results)
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # 保存JSON格式的详细数据
        json_filename = f"temp/address_intersection_data_{timestamp}.json"
        json_data = {
            'analysis_time': datetime.now().isoformat(),
            'source_files': {
                'json_file': self.json_file_path,
                'txt_file': self.txt_file_path
            },
            'statistics': {
                'json_addresses_count': len(self.json_addresses),
                'txt_addresses_count': len(self.txt_addresses),
                'intersection_count': len(self.intersection_addresses),
                'overlap_rate': len(self.intersection_addresses) / max(len(self.json_addresses), 1) * 100
            },
            'intersection_addresses': list(self.intersection_addresses),
            'detailed_analysis': analysis_results
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return report_filename, json_filename
    
    def analyze(self) -> None:
        """执行完整的分析流程"""
        print("🔗 地址交集分析工具")
        print("=" * 50)
        
        # 提取地址
        self.extract_addresses_from_json()
        self.extract_addresses_from_txt()
        
        # 查找交集
        intersection = self.find_intersection()
        
        if not intersection:
            print("❌ 没有找到共同地址")
            return
        
        # 分析共同地址
        analysis_results = self.analyze_common_addresses()
        
        # 保存结果
        report_file, json_file = self.save_results(analysis_results)
        
        # 显示摘要
        print(f"\n📋 分析完成！")
        print(f"   📄 详细报告: {report_file}")
        print(f"   📊 JSON数据: {json_file}")
        
        print(f"\n🏆 TOP 5 共同地址 (按Concrete Stable余额排序):")
        for i, addr_info in enumerate(analysis_results[:5], 1):
            addr = addr_info['address']
            concrete_amount = addr_info['txt_details'].get('usdt_amount', 0)
            tx_count = addr_info['summary'].get('transaction_count', 0)
            print(f"   {i}. {addr}")
            print(f"      💰 Concrete Stable: {concrete_amount:,.2f} USDT")
            print(f"      📊 USDT交易: {tx_count} 笔")


def main():
    """主函数"""
    import sys
    
    # 默认文件路径
    default_json = "temp/usdt_analysis_20241024_20251025_143319.json"
    default_txt = "temp/concrete_stable_addresses_20251024_153119.txt"
    
    print("🔗 地址交集分析工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("📖 功能说明:")
        print("  分析USDT分析结果JSON文件和Concrete Stable地址列表TXT文件中的共同地址")
        print("  找出同时出现在两个文件中的地址，并提供详细的交集分析")
        print()
        print("📝 使用方法:")
        print(f"  python {sys.argv[0]} [json_file] [txt_file]")
        print()
        print("📋 示例:")
        print(f"  python {sys.argv[0]}")
        print(f"  python {sys.argv[0]} temp/usdt_analysis.json temp/addresses.txt")
        print()
        print("📊 分析内容:")
        print("  - 提取两个文件中的所有地址")
        print("  - 找出共同地址")
        print("  - 分析每个共同地址的USDT交易活动")
        print("  - 对比Concrete Stable余额和USDT交易记录")
        print("  - 生成详细的分析报告")
        return
    
    # 获取文件路径
    json_file = sys.argv[1] if len(sys.argv) > 1 else default_json
    txt_file = sys.argv[2] if len(sys.argv) > 2 else default_txt
    
    # 检查文件是否存在
    if not os.path.exists(json_file):
        print(f"❌ JSON文件不存在: {json_file}")
        return
    
    if not os.path.exists(txt_file):
        print(f"❌ TXT文件不存在: {txt_file}")
        return
    
    # 执行分析
    try:
        analyzer = AddressIntersectionAnalyzer(json_file, txt_file)
        analyzer.analyze()
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")


if __name__ == "__main__":
    main()