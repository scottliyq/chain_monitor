#!/usr/bin/env python3
"""
地址交互分析演示
模拟分析Concrete_STABLE相关地址的交互情况
"""

import os
import re
from datetime import datetime
from collections import Counter

def demo_address_interaction_analysis():
    """演示地址交互分析"""
    
    print("🚀 Concrete_STABLE 相关地址交互分析演示")
    print("=" * 80)
    
    # 读取地址文件
    file_path = "temp/concrete_stable_addresses_20251024_153119.txt"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    # 提取地址
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式提取地址
        address_pattern = r'0x[a-fA-F0-9]{40}'
        found_addresses = re.findall(address_pattern, content)
        
        # 去重
        unique_addresses = list(set([addr.lower() for addr in found_addresses]))
        
        # 过滤掉Concrete_STABLE本身
        concrete_stable = "0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f"
        addresses = [addr for addr in unique_addresses if addr.lower() != concrete_stable.lower()]
        
        print(f"📋 成功提取 {len(addresses)} 个唯一地址")
        
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 分析说明
    print(f"\n🔍 分析目标:")
    print(f"   • 分析这些地址在过去24小时的USDT交易")
    print(f"   • 找出它们共同交互过的地址")
    print(f"   • 识别可能的关联模式")
    
    print(f"\n📊 分析方法:")
    print(f"   • 获取每个地址最近24小时的USDT转账记录")
    print(f"   • 提取所有交易对手地址")
    print(f"   • 统计被多个地址交互的共同地址")
    print(f"   • 分析交互频率和模式")
    
    # 模拟分析结果（基于实际区块链分析的合理预期）
    print(f"\n🎯 预期分析结果:")
    print(f"   • 大额地址通常与交易所、做市商交互")
    print(f"   • 可能发现共同的中介地址或服务提供商")
    print(f"   • 识别可能的资金流动模式")
    
    # 实际运行指令
    print(f"\n🚀 实际运行指令:")
    print(f"```bash")
    print(f"# 方法1: 使用内置库版本 (无需额外依赖)")
    print(f"python quick_analyzer.py")
    print(f"")
    print(f"# 方法2: 使用功能完整版本 (需要requests库)")
    print(f"python batch_address_analyzer.py")
    print(f"")
    print(f"# 方法3: 使用高级分析版本")
    print(f"python analyze_address_interactions.py temp/concrete_stable_addresses_20251024_153119.txt 20")
    print(f"```")
    
    # 预期输出示例
    print(f"\n📋 预期输出示例:")
    print("-" * 60)
    print("📊 地址交互分析结果")
    print("🎯 成功分析地址: 15")
    print("🌐 总交互地址数: 45")
    print("🤝 共同交互地址: 8")
    print("")
    print("🏆 被多个地址交互的地址:")
    print("1. 0x123...abc - 被 5 个地址交互 (33.3%)")
    print("   🌐 https://etherscan.io/address/0x123...abc")
    print("2. 0x456...def - 被 3 个地址交互 (20.0%)")
    print("   🌐 https://etherscan.io/address/0x456...def")
    print("")
    print("🚨 高频交互地址:")
    print("   🔥 0x123...abc - 可能是交易所或大型服务商")
    print("   🔥 0x456...def - 可能是做市商或中介")
    
    # 分析价值
    print(f"\n💡 分析价值:")
    print(f"   • 识别关键的中介节点和服务提供商")
    print(f"   • 了解大额USDT的流动模式")
    print(f"   • 发现潜在的关联账户网络")
    print(f"   • 为风险评估提供数据支持")
    
    # 保存演示结果
    try:
        os.makedirs('temp', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        demo_file = f"temp/interaction_analysis_demo_{timestamp}.txt"
        
        with open(demo_file, 'w', encoding='utf-8') as f:
            f.write("# Concrete_STABLE 相关地址交互分析演示\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 地址文件: {file_path}\n")
            f.write(f"# 提取地址数: {len(addresses)}\n\n")
            
            f.write("=== 地址列表预览 (前10个) ===\n")
            for i, addr in enumerate(addresses[:10], 1):
                f.write(f"{i:2d}. {addr}\n")
            
            if len(addresses) > 10:
                f.write(f"... 还有 {len(addresses) - 10} 个地址\n")
            
            f.write(f"\n=== 分析计划 ===\n")
            f.write("1. 获取每个地址最近24小时USDT交易记录\n")
            f.write("2. 提取所有交易对手地址\n") 
            f.write("3. 统计共同交互地址\n")
            f.write("4. 分析交互模式和频率\n")
            f.write("5. 生成可视化报告\n")
        
        print(f"\n💾 演示信息已保存到: {demo_file}")
        
    except Exception as e:
        print(f"⚠️ 保存演示文件失败: {e}")
    
    print(f"\n🎯 下一步操作:")
    print(f"   1. 准备Etherscan API密钥")
    print(f"   2. 选择合适的分析脚本")
    print(f"   3. 运行分析并查看结果")
    print(f"   4. 基于结果进行深入研究")

if __name__ == "__main__":
    demo_address_interaction_analysis()