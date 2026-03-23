#!/usr/bin/env python3
"""
可配置协议监控器测试脚本
"""

from _path_setup import ensure_src_path

ensure_src_path()

from configurable_protocol_monitor import ConfigurableProtocolMonitor

def test_configurable_monitor():
    """测试可配置协议监控器"""
    print("🧪 测试可配置协议监控器功能...")
    
    test_configs = [
        {
            "name": "以太坊USDT 10分钟窗口",
            "network": "ethereum",
            "token": "USDT",
            "min_amount": 500,
            "time_window_minutes": 10,
            "monitor_interval_minutes": 5
        },
        {
            "name": "BSC USDC 15分钟窗口",
            "network": "bsc",
            "token": "USDC",
            "min_amount": 1000,
            "time_window_minutes": 15,
            "monitor_interval_minutes": 10
        }
    ]
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"🚀 测试配置: {config['name']}")
        print(f"{'='*60}")
        
        try:
            # 创建监控器实例
            monitor = ConfigurableProtocolMonitor(
                network=config["network"],
                token=config["token"],
                min_amount=config["min_amount"],
                time_window_minutes=config["time_window_minutes"],
                monitor_interval_minutes=config["monitor_interval_minutes"]
            )
            
            # 测试一次监控周期
            print("🚀 开始测试监控周期...")
            report = monitor.analyze_recent_activity()
            
            if report:
                print("✅ 测试成功! 获得监控报告")
                monitor.display_summary(report)
            else:
                print("⚠️ 未获得足够数据，可能最近时间窗口没有足够的代币活动")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n⏸️ 等待下一个测试...")
        input("按回车键继续下一个测试...")

def test_parameter_validation():
    """测试参数验证功能"""
    print("\n🧪 测试参数验证功能...")
    
    invalid_configs = [
        {
            "name": "无效网络",
            "network": "invalid_network",
            "token": "USDT"
        },
        {
            "name": "无效代币",
            "network": "ethereum",
            "token": "INVALID_TOKEN"
        },
        {
            "name": "负数金额",
            "network": "ethereum",
            "token": "USDT",
            "min_amount": -100
        }
    ]
    
    for config in invalid_configs:
        print(f"\n🔍 测试无效配置: {config['name']}")
        
        try:
            monitor = ConfigurableProtocolMonitor(**config)
            print(f"❌ 应该失败但成功了: {config['name']}")
        except Exception as e:
            print(f"✅ 正确拒绝了无效配置: {e}")

if __name__ == "__main__":
    print("🔍 可配置协议监控器测试套件")
    print("=" * 50)
    
    # 测试参数验证
    test_parameter_validation()
    
    # 测试实际监控
    print(f"\n{'='*60}")
    print("是否要测试实际监控功能？(这将进行真实的API调用)")
    choice = input("输入 'y' 继续测试，或按回车跳过: ").strip().lower()
    
    if choice == 'y':
        test_configurable_monitor()
    else:
        print("跳过实际监控测试")
    
    print("\n✅ 测试完成")
