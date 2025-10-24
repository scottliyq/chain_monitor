#!/usr/bin/env python3
"""
基于现有工具的地址交互分析
直接使用已有的 balance_surge_monitor.py 中的方法
"""

import sys
import os
import re
from datetime import datetime
from collections import Counter

# 添加当前目录到路径以便导入
sys.path.append(os.getcwd())

from balance_surge_monitor import BalanceSurgeMonitor

def extract_addresses_from_file(file_path):
    """从文件中提取地址"""
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
        
        print(f"📋 从文件中提取到 {len(addresses)} 个唯一地址")
        return addresses
        
    except Exception as e:
        print(f"❌ 读取文件出错: {e}")
        return []

def analyze_address_list_interactions(api_key, addresses, max_analyze=20):
    """分析地址列表的交互情况"""
    
    # 创建监控器实例
    monitor = BalanceSurgeMonitor(api_key)
    
    print(f"🔍 开始分析地址交互情况...")
    print(f"📊 总地址数: {len(addresses)}")
    print(f"📋 实际分析数: {min(max_analyze, len(addresses))} (API限制)")
    print("=" * 80)
    
    # 限制分析数量
    analyze_addresses = addresses[:max_analyze]
    
    # 存储所有交互数据
    all_interactions = {}
    all_counterparts = Counter()
    
    for i, address in enumerate(analyze_addresses, 1):
        print(f"\n📊 进度: {i}/{len(analyze_addresses)} - {address[:10]}...{address[-6:]}")
        
        try:
            # 使用已有的方法获取地址交互
            interactions = monitor.get_address_interactions(address)
            
            if interactions:
                # 统计交互对手
                sent_to = interactions.get('sent_to', {})
                received_from = interactions.get('received_from', {})
                
                # 合并所有交互对手
                counterparts = set()
                counterparts.update(sent_to.keys())
                counterparts.update(received_from.keys())
                
                # 更新计数器
                for counterpart in counterparts:
                    all_counterparts[counterpart] += 1
                
                all_interactions[address] = {
                    'counterparts': list(counterparts),
                    'sent_to': sent_to,
                    'received_from': received_from,
                    'total_counterparts': len(counterparts)
                }
                
                print(f"   ✅ 找到 {len(counterparts)} 个交互地址")
            else:
                print(f"   ❌ 未找到交互数据")
                
        except Exception as e:
            print(f"   ⚠️ 分析失败: {e}")
        
        # 简单延时
        import time
        time.sleep(0.3)
    
    return all_interactions, all_counterparts

def find_common_interactions(all_counterparts, min_count=2):
    """找出共同交互地址"""
    common_addresses = {addr: count for addr, count in all_counterparts.items() 
                       if count >= min_count}
    return common_addresses

def display_analysis_results(all_interactions, common_addresses):
    """显示分析结果"""
    print(f"\n" + "=" * 100)
    print("📊 地址交互分析结果")
    print("=" * 100)
    
    total_analyzed = len(all_interactions)
    total_unique_counterparts = len(set().union(*[data['counterparts'] for data in all_interactions.values()]))
    
    print(f"🎯 成功分析地址数: {total_analyzed}")
    print(f"🌐 唯一交互地址数: {total_unique_counterparts}")
    print(f"🤝 共同交互地址数: {len(common_addresses)}")
    
    if not common_addresses:
        print("\n✅ 在样本中没有发现被多个地址共同交互的地址")
        print("💡 这可能表明这些地址的交互模式相对独立")
        return
    
    # 按交互次数排序
    sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n🏆 共同交互地址 TOP 10:")
    print("-" * 100)
    
    for i, (addr, count) in enumerate(sorted_common[:10], 1):
        percentage = (count / total_analyzed) * 100
        print(f"{i:2d}. {addr}")
        print(f"    🔗 被 {count} 个地址交互 ({percentage:.1f}%)")
        print(f"    🌐 Etherscan: https://etherscan.io/address/{addr}")
        print()
    
    # 分析高频地址
    high_freq_threshold = max(3, total_analyzed // 5)
    high_freq_addresses = [addr for addr, count in common_addresses.items() 
                         if count >= high_freq_threshold]
    
    if high_freq_addresses:
        print(f"🚨 高频交互地址 (被至少 {high_freq_threshold} 个地址交互):")
        print("-" * 80)
        for addr in high_freq_addresses:
            count = common_addresses[addr]
            percentage = (count / total_analyzed) * 100
            print(f"   🔥 {addr} - {count} 次 ({percentage:.1f}%)")
    
    # 保存结果
    save_analysis_results(all_interactions, common_addresses)

def save_analysis_results(all_interactions, common_addresses):
    """保存分析结果"""
    try:
        os.makedirs('temp', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"temp/address_list_interaction_analysis_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Concrete_STABLE 相关地址交互分析结果\n")
            f.write(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 分析地址数: {len(all_interactions)}\n")
            f.write(f"# 共同交互地址数: {len(common_addresses)}\n\n")
            
            f.write("=== 各地址交互统计 ===\n")
            for addr, data in all_interactions.items():
                f.write(f"{addr}: {data['total_counterparts']} 个交互地址\n")
            
            f.write(f"\n=== 共同交互地址 ===\n")
            sorted_common = sorted(common_addresses.items(), key=lambda x: x[1], reverse=True)
            
            for i, (addr, count) in enumerate(sorted_common, 1):
                percentage = (count / len(all_interactions)) * 100
                f.write(f"{i:3d}. {addr} - {count} 次交互 ({percentage:.1f}%)\n")
        
        print(f"\n💾 分析结果已保存到: {filename}")
        
    except Exception as e:
        print(f"⚠️ 保存结果时出错: {e}")

def main():
    """主函数"""
    print("🚀 地址列表交互分析器")
    print("=" * 60)
    
    # 参数设置
    file_path = "temp/concrete_stable_addresses_20251024_153119.txt"
    max_analyze = 15  # 限制分析数量避免API限制
    
    # 检查API密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("⚠️ 未检测到 ETHERSCAN_API_KEY 环境变量")
        api_key = input("请输入 Etherscan API 密钥: ").strip()
        if not api_key:
            print("❌ API 密钥不能为空")
            return
    
    # 检查文件
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    try:
        # 提取地址
        addresses = extract_addresses_from_file(file_path)
        if not addresses:
            print("❌ 没有提取到有效地址")
            return
        
        print(f"\n⚠️ 注意: 为避免API限制，只分析前 {max_analyze} 个地址")
        
        # 分析交互
        all_interactions, all_counterparts = analyze_address_list_interactions(
            api_key, addresses, max_analyze
        )
        
        if not all_interactions:
            print("❌ 没有获取到有效的交互数据")
            return
        
        # 查找共同交互
        common_addresses = find_common_interactions(all_counterparts, min_count=2)
        
        # 显示结果
        display_analysis_results(all_interactions, common_addresses)
        
        print(f"\n🎉 分析完成！")
        
    except KeyboardInterrupt:
        print(f"\n👋 分析已停止")
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()