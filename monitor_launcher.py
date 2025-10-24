#!/usr/bin/env python3
"""
USDT 监控工具启动器
统一入口，支持所有监控功能
"""

import os
import sys
from datetime import datetime

def print_banner():
    """打印欢迎横幅"""
    print("=" * 80)
    print("🚀 USDT 区块链监控工具套件")
    print("=" * 80)
    print("📊 监控以太坊网络上的 USDT 资金流动")
    print("🔍 发现大额转账和异常余额变化")
    print("⚡ 基于 Etherscan API 的实时监控")
    print("=" * 80)

def check_requirements():
    """检查必要的环境配置"""
    issues = []
    
    # 检查 API 密钥
    if not os.getenv('ETHERSCAN_API_KEY'):
        issues.append("❌ ETHERSCAN_API_KEY 环境变量未设置")
    
    # 检查必要的文件
    required_files = [
        'usdt_quick_check.py',
        'balance_surge_monitor.py',
        'mainnet_monitor.py'
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            issues.append(f"❌ 缺少文件: {file}")
    
    if issues:
        print("⚠️ 配置检查发现问题：")
        for issue in issues:
            print(f"   {issue}")
        print("\n📝 解决方案：")
        print("   1. 获取 Etherscan API 密钥: https://etherscan.io/apis")
        print("   2. 设置环境变量: export ETHERSCAN_API_KEY='your_key'")
        print("   3. 或创建 .env 文件并添加: ETHERSCAN_API_KEY=your_key")
        return False
    
    print("✅ 环境配置检查通过")
    return True

def show_main_menu():
    """显示主菜单"""
    print(f"\n📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n🎯 请选择监控功能：")
    print()
    print("1. 🔍 大额转账监控")
    print("   查询指定时间范围内的 USDT 大额转账")
    print()
    print("2. 📈 余额激增监控")
    print("   发现余额快速增长的地址（可能的大户/异常活动）")
    print()
    print("3. 🎮 演示模式")
    print("   运行功能演示，了解工具能力")
    print()
    print("4. 📚 查看使用说明")
    print("   详细的功能介绍和使用指南")
    print()
    print("5. ⚙️  高级监控")
    print("   访问完整的监控系统（需数据库配置）")
    print()
    print("0. 🚪 退出")

def run_large_transfer_monitor():
    """运行大额转账监控"""
    print("\n🔍 大额转账监控")
    print("=" * 50)
    
    # 获取参数
    try:
        min_amount = input("最小金额阈值 (USDT, 默认 1000000): ").strip()
        min_amount = float(min_amount) if min_amount else 1000000
        
        hours_back = input("查询最近多少小时 (默认 24): ").strip()
        hours_back = int(hours_back) if hours_back else 24
        
        print(f"\n🚀 开始查询最近 {hours_back} 小时内超过 {min_amount:,.0f} USDT 的转账...")
        
        # 运行监控
        cmd = f"python usdt_quick_check.py {min_amount} {hours_back}"
        os.system(cmd)
        
    except ValueError:
        print("❌ 输入格式错误，请输入数字")
    except KeyboardInterrupt:
        print("\n👋 监控已取消")

def run_balance_surge_monitor():
    """运行余额激增监控"""
    print("\n📈 余额激增监控")
    print("=" * 50)
    print("监控条件：")
    print("• 最近24小时余额新增 ≥ 设定阈值")
    print("• 48小时前余额 < 设定阈值")
    print("用途：发现新的大户地址、异常资金聚集")
    
    try:
        min_increase = input("\n最小增长金额 (USDT, 默认 5000000): ").strip()
        min_increase = float(min_increase) if min_increase else 5000000
        
        min_48h_balance = input("48小时前最大余额 (USDT, 默认 100000): ").strip()
        min_48h_balance = float(min_48h_balance) if min_48h_balance else 100000
        
        print(f"\n🚀 开始监控余额激增地址...")
        print(f"   条件1: 24小时增长 ≥ {min_increase:,.0f} USDT")
        print(f"   条件2: 48小时前余额 < {min_48h_balance:,.0f} USDT")
        
        # 运行监控
        cmd = f"python balance_surge_monitor.py {min_increase} {min_48h_balance}"
        os.system(cmd)
        
    except ValueError:
        print("❌ 输入格式错误，请输入数字")
    except KeyboardInterrupt:
        print("\n👋 监控已取消")

def run_demo_mode():
    """运行演示模式"""
    print("\n🎮 演示模式")
    print("=" * 50)
    print("选择演示内容：")
    print("1. 🔍 大额转账监控演示")
    print("2. 📈 余额激增监控演示")
    print("3. 📚 监控策略指南")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == "1":
        os.system("python demo.py")
    elif choice == "2":
        os.system("python balance_surge_demo.py")
    elif choice == "3":
        os.system("python balance_surge_demo.py")
    else:
        print("❌ 无效选择")

def show_help():
    """显示使用说明"""
    print("\n📚 USDT 监控工具使用指南")
    print("=" * 80)
    
    print("\n🎯 工具功能：")
    print("1. 大额转账监控")
    print("   • 监控指定时间范围内的大额 USDT 转账")
    print("   • 分析发送方和接收方地址")
    print("   • 统计转账金额和频率")
    print("   • 用途：市场分析、资金流向追踪")
    
    print("\n2. 余额激增监控")
    print("   • 发现余额快速增长的地址")
    print("   • 识别新出现的大户")
    print("   • 监控异常资金聚集")
    print("   • 用途：大户分析、异常检测")
    
    print("\n📊 监控策略建议：")
    strategies = [
        ("机构级监控", "≥5000万USDT", "捕获超大型资金流动"),
        ("鲸鱼级监控", "≥1000万USDT", "追踪大户资金活动"),
        ("市场级监控", "≥500万USDT", "分析市场资金流向"),
        ("异常检测", "≥100万USDT", "发现异常交易模式")
    ]
    
    for name, threshold, purpose in strategies:
        print(f"   • {name}: {threshold} - {purpose}")
    
    print("\n⚡ 快速命令：")
    print("   python usdt_quick_check.py 5000000 1    # 查询1小时内≥500万的转账")
    print("   python balance_surge_monitor.py          # 交互式余额监控")
    
    print("\n💡 使用技巧：")
    print("   • 建议从较高阈值开始，逐步调整")
    print("   • 定期运行监控以捕获时效性信息")
    print("   • 结合多种监控方式获得完整视图")
    print("   • 保存监控结果进行历史分析")
    
    print("\n🔗 相关链接：")
    print("   • Etherscan API: https://etherscan.io/apis")
    print("   • USDT 合约: https://etherscan.io/token/0xdAC17F958D2ee523a2206206994597C13D831ec7")

def run_advanced_monitor():
    """运行高级监控系统"""
    print("\n⚙️ 高级监控系统")
    print("=" * 50)
    print("这是完整的监控系统，支持：")
    print("• 定时自动监控")
    print("• 数据库存储")
    print("• 自动通知")
    print("• 详细分析报告")
    
    print("\n请确保已配置：")
    print("• 数据库连接 (db_url)")
    print("• 通知服务 (IFTTT_KEY)")
    
    choice = input("\n是否继续？(y/N): ").strip().lower()
    if choice == 'y':
        try:
            os.system("python mainnet_monitor.py")
        except KeyboardInterrupt:
            print("\n👋 高级监控已停止")
    else:
        print("👋 已取消")

def main():
    """主函数"""
    print_banner()
    
    # 检查环境
    if not check_requirements():
        print("\n👋 请解决配置问题后重新运行")
        return
    
    while True:
        try:
            show_main_menu()
            choice = input("\n请选择功能 (0-5): ").strip()
            
            if choice == "0":
                print("\n👋 感谢使用 USDT 监控工具！")
                break
            elif choice == "1":
                run_large_transfer_monitor()
            elif choice == "2":
                run_balance_surge_monitor()
            elif choice == "3":
                run_demo_mode()
            elif choice == "4":
                show_help()
            elif choice == "5":
                run_advanced_monitor()
            else:
                print("❌ 无效选择，请输入 0-5")
            
            if choice != "0":
                input("\n按 Enter 键返回主菜单...")
                
        except KeyboardInterrupt:
            print("\n\n👋 程序已退出")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            input("按 Enter 键继续...")

if __name__ == "__main__":
    main()