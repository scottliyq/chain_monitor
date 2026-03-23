#!/usr/bin/env python3
"""
余额激增监控使用示例
演示如何使用余额激增监控功能发现异常资金流动
"""

import os
import sys
from _path_setup import ensure_src_path

ensure_src_path()

from balance_surge_monitor import USDTBalanceSurgeMonitor

def demo_balance_surge_monitoring():
    """演示余额激增监控"""
    print("=" * 80)
    print("🚀 示例：USDT 余额激增监控")
    print("=" * 80)
    print("这个功能可以帮助您发现：")
    print("• 🏦 新出现的大户地址")
    print("• 💰 异常资金聚集")
    print("• 📈 可能的市场操作信号")
    print("• 🔍 隐藏的资金流动模式")
    print("=" * 80)
    
    # 从环境变量获取 API 密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量 ETHERSCAN_API_KEY")
        print("📝 获取免费 API 密钥: https://etherscan.io/apis")
        return
    
    # 创建监控器
    monitor = USDTBalanceSurgeMonitor(api_key)
    
    print("\n📊 监控参数说明：")
    print("• 最小增长金额: 5,000,000 USDT (500万)")
    print("• 48小时前最大余额: 100,000 USDT (10万)")
    print("• 监控时间窗口: 48小时")
    print("\n这意味着我们要找到那些：")
    print("1. 48小时前余额不超过10万USDT的地址")
    print("2. 但在最近24小时内余额增长了至少500万USDT")
    print("\n🔍 开始监控...")
    
    # 执行监控
    results = monitor.monitor_balance_surge(
        min_increase=5000000,      # 500万USDT增长
        min_48h_balance=100000     # 48小时前最多10万USDT
    )
    
    if results:
        print(f"\n🎯 发现了 {len(results)} 个符合条件的地址！")
        print("\n💡 这些地址可能代表：")
        print("• 新的机构投资者")
        print("• 大户资金重新分配")
        print("• 交易所新的热钱包")
        print("• 可能的市场操作准备")
        
        # 分析结果
        total_increase = sum(r['balance_increase'] for r in results)
        avg_ratio = sum(r['increase_ratio'] for r in results) / len(results)
        
        print(f"\n📈 统计信息：")
        print(f"• 总资金流入: {total_increase:,.2f} USDT")
        print(f"• 平均增长倍数: {avg_ratio:,.1f}%")
        print(f"• 单地址最大增长: {max(r['balance_increase'] for r in results):,.2f} USDT")
        
    else:
        print("\n✅ 未发现符合条件的地址")
        print("💡 这可能意味着：")
        print("• 最近没有异常的大额资金聚集")
        print("• 市场资金流动相对平稳")
        print("• 可以尝试调整监控参数")

def demo_different_thresholds():
    """演示不同阈值的监控效果"""
    print("\n" + "=" * 80)
    print("🎯 示例：不同监控阈值的效果对比")
    print("=" * 80)
    
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量 ETHERSCAN_API_KEY")
        return
    
    monitor = USDTBalanceSurgeMonitor(api_key)
    
    # 测试不同的阈值组合
    test_cases = [
        {
            'name': '超保守监控 (1000万增长, 5万基础)',
            'min_increase': 10000000,
            'min_48h_balance': 50000,
            'description': '只捕获最极端的资金流动'
        },
        {
            'name': '保守监控 (500万增长, 10万基础)',
            'min_increase': 5000000,
            'min_48h_balance': 100000,
            'description': '平衡的监控策略'
        },
        {
            'name': '敏感监控 (100万增长, 5万基础)',
            'min_increase': 1000000,
            'min_48h_balance': 50000,
            'description': '更敏感，可能包含更多噪音'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n🔍 测试 {i}: {case['name']}")
        print(f"📝 {case['description']}")
        
        try:
            results = monitor.monitor_balance_surge(
                min_increase=case['min_increase'],
                min_48h_balance=case['min_48h_balance']
            )
            
            if results:
                print(f"✅ 发现 {len(results)} 个地址")
                total = sum(r['balance_increase'] for r in results)
                print(f"💰 总流入: {total:,.2f} USDT")
            else:
                print("❌ 未发现符合条件的地址")
                
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
            break
        except Exception as e:
            print(f"⚠️ 监控出错: {e}")
        
        if i < len(test_cases):
            input("\n按 Enter 键继续下一个测试...")

def main():
    """主函数"""
    print("🎮 USDT 余额激增监控演示")
    print("=" * 80)
    print("本演示将展示如何使用余额激增监控功能")
    print("请确保已设置 ETHERSCAN_API_KEY 环境变量")
    print("=" * 80)
    
    # 检查 API 密钥
    if not os.getenv('ETHERSCAN_API_KEY'):
        print("❌ 未找到 ETHERSCAN_API_KEY 环境变量")
        print("📝 请先设置环境变量:")
        print("   export ETHERSCAN_API_KEY='your_api_key'")
        print("   或者在 .env 文件中配置")
        return
    
    print("\n请选择演示内容:")
    print("1. 🔍 基础余额激增监控")
    print("2. 🎯 不同阈值效果对比")
    print("3. 📚 监控策略说明")
    
    choice = input("\n请输入选择 (1-3): ").strip()
    
    if choice == "1":
        demo_balance_surge_monitoring()
    elif choice == "2":
        demo_different_thresholds()
    elif choice == "3":
        show_monitoring_strategies()
    else:
        print("❌ 无效选择")

def show_monitoring_strategies():
    """显示监控策略说明"""
    print("\n" + "=" * 80)
    print("📚 余额激增监控策略指南")
    print("=" * 80)
    
    strategies = [
        {
            'name': '🏦 机构监控策略',
            'min_increase': '50,000,000 USDT',
            'min_48h_balance': '1,000,000 USDT',
            'purpose': '发现大型机构的资金调动',
            'suitable_for': '机构投资者、大型交易所'
        },
        {
            'name': '🐋 鲸鱼监控策略',
            'min_increase': '10,000,000 USDT',
            'min_48h_balance': '500,000 USDT',
            'purpose': '追踪鲸鱼用户的资金流动',
            'suitable_for': '大户投资者、资金管理公司'
        },
        {
            'name': '📈 市场信号策略',
            'min_increase': '5,000,000 USDT',
            'min_48h_balance': '100,000 USDT',
            'purpose': '捕获可能的市场操作信号',
            'suitable_for': '交易员、市场分析师'
        },
        {
            'name': '🔍 异常检测策略',
            'min_increase': '1,000,000 USDT',
            'min_48h_balance': '50,000 USDT',
            'purpose': '发现异常的资金聚集模式',
            'suitable_for': '安全分析、合规监控'
        }
    ]
    
    for strategy in strategies:
        print(f"\n{strategy['name']}")
        print(f"   最小增长: {strategy['min_increase']}")
        print(f"   基础余额: {strategy['min_48h_balance']}")
        print(f"   监控目的: {strategy['purpose']}")
        print(f"   适用场景: {strategy['suitable_for']}")
    
    print(f"\n💡 使用建议：")
    print(f"• 🎯 根据您的监控目的选择合适的阈值")
    print(f"• ⏰ 定期运行监控以捕获时效性信息")
    print(f"• 📊 结合大额转账监控获得完整视图")
    print(f"• 🔄 根据市场情况调整监控参数")
    print(f"• 📝 保存历史数据进行趋势分析")

if __name__ == "__main__":
    main()
