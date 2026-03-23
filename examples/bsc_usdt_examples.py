#!/usr/bin/env python3
"""
BSC网络USDT查询示例脚本
演示如何使用USDTDepositAnalyzer查询BSC网络上的USDT交易
"""

import sys
import os
from datetime import datetime, timezone

from _path_setup import ensure_src_path

ensure_src_path()

from usdt_deposit_analyzer import USDTDepositAnalyzer

def example_1_basic_bsc_query():
    """示例1: 基本BSC USDT查询"""
    print("🔥 示例1: BSC网络基本USDT查询")
    print("=" * 50)
    
    try:
        # 创建BSC网络分析器实例
        analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',     # 开始时间（UTC）
            end_time='2025-01-01 01:00:00',       # 结束时间（UTC）
            min_amount=1000,                       # 最小金额 1000 USDT
            network='bsc'                          # BSC网络
        )
        
        print("✅ BSC网络分析器初始化成功!")
        print(f"📍 USDT合约地址: {analyzer.USDT_CONTRACT_ADDRESS}")
        print(f"🔗 链ID: {analyzer.network_config['chain_id']}")
        print(f"📊 USDT小数位: {analyzer.usdt_decimals}")
        print(f"🌐 API端点: {analyzer.api_config['base_url']}")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")

def example_2_large_amount_query():
    """示例2: BSC大额USDT交易查询"""
    print("\n🚀 示例2: BSC网络大额USDT交易查询")
    print("=" * 50)
    
    try:
        # 查询大额USDT交易（大于50万USDT）
        analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',
            end_time='2025-01-01 23:59:59',
            min_amount=500000,  # 50万USDT
            network='bsc'
        )
        
        print("✅ 大额交易分析器配置完成")
        print(f"💰 查询条件: >= {analyzer.min_amount:,} USDT")
        print(f"⏰ 时间范围: {analyzer.start_time_str} - {analyzer.end_time_str} UTC")
        
    except Exception as e:
        print(f"❌ 配置失败: {e}")

def example_3_bsc_vs_ethereum():
    """示例3: BSC与以太坊网络对比"""
    print("\n⚡ 示例3: BSC vs 以太坊网络配置对比")
    print("=" * 50)
    
    try:
        # BSC网络配置
        bsc_analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',
            end_time='2025-01-01 01:00:00',
            min_amount=1000,
            network='bsc'
        )
        
        print("🟡 BSC网络配置:")
        print(f"   USDT地址: {bsc_analyzer.USDT_CONTRACT_ADDRESS}")
        print(f"   小数位数: {bsc_analyzer.usdt_decimals}")
        print(f"   链ID: {bsc_analyzer.network_config['chain_id']}")
        print(f"   API端点: {bsc_analyzer.api_config['base_url']}")
        
        # 以太坊网络配置（对比）
        eth_analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',
            end_time='2025-01-01 01:00:00',
            min_amount=1000,
            network='ethereum'
        )
        
        print("\n🔵 以太坊网络配置:")
        print(f"   USDT地址: {eth_analyzer.USDT_CONTRACT_ADDRESS}")
        print(f"   小数位数: {eth_analyzer.usdt_decimals}")
        print(f"   链ID: {eth_analyzer.network_config['chain_id']}")
        print(f"   API端点: {eth_analyzer.api_config['base_url']}")
        
        print("\n📊 主要差异:")
        print(f"   BSC USDT小数位: {bsc_analyzer.usdt_decimals} | 以太坊: {eth_analyzer.usdt_decimals}")
        print(f"   BSC链ID: {bsc_analyzer.network_config['chain_id']} | 以太坊: {eth_analyzer.network_config['chain_id']}")
        
    except Exception as e:
        print(f"❌ 对比失败: {e}")

def example_4_real_time_query():
    """示例4: 实时BSC USDT查询"""
    print("\n🕐 示例4: 实时BSC USDT查询示例")
    print("=" * 50)
    
    # 使用当前时间前1小时作为查询范围
    end_time = datetime.now(timezone.utc)
    start_time = end_time.replace(hour=end_time.hour-1) if end_time.hour > 0 else end_time.replace(hour=23, day=end_time.day-1)
    
    start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"🕐 查询时间范围: {start_str} - {end_str} UTC")
    print(f"💡 这是基于当前时间的实时查询范围示例")
    
    try:
        analyzer = USDTDepositAnalyzer(
            start_time=start_str,
            end_time=end_str,
            min_amount=5000,  # 5000 USDT以上
            network='bsc'
        )
        
        print("✅ 实时查询配置完成")
        print(f"📊 查询条件: >= {analyzer.min_amount:,} USDT")
        print(f"🌐 网络: {analyzer.network_config['name']}")
        
    except Exception as e:
        print(f"❌ 实时查询配置失败: {e}")

def example_5_api_configuration():
    """示例5: BSC API配置说明"""
    print("\n🔧 示例5: BSC API配置说明")
    print("=" * 50)
    
    print("📋 BSC网络API配置信息:")
    print("   API端点: https://api.bscscan.com/v2/api")
    print("   支持的API密钥环境变量:")
    print("     1. BSCSCAN_API_KEY (BSC专用，优先级最高)")
    print("     2. ETHERSCAN_API_KEY (通用密钥，作为备用)")
    print()
    print("🔑 获取BSC API密钥:")
    print("   1. 访问: https://bscscan.com/apis")
    print("   2. 注册账户并申请API密钥")
    print("   3. 在.env文件中配置:")
    print("      BSCSCAN_API_KEY=YourBscscanApiKeyHere")
    print()
    print("💡 BSC网络特点:")
    print("   - USDT合约地址: 0x55d398326f99059fF775485246999027B3197955")
    print("   - USDT小数位数: 18位 (与以太坊的6位不同)")
    print("   - 链ID: 56")
    print("   - 平均出块时间: ~3秒")

def main():
    """主函数 - 运行所有示例"""
    print("🌟 BSC网络USDT查询完整示例")
    print("=" * 60)
    
    # 运行所有示例
    example_1_basic_bsc_query()
    example_2_large_amount_query()
    example_3_bsc_vs_ethereum()
    example_4_real_time_query()
    example_5_api_configuration()
    
    print("\n🎯 实际使用建议:")
    print("=" * 60)
    print("1. 配置API密钥: 在.env文件中设置BSCSCAN_API_KEY")
    print("2. 注意小数位差异: BSC USDT是18位小数，以太坊是6位")
    print("3. 合理设置查询范围: BSC出块快，建议缩短时间范围")
    print("4. 监控API限制: 注意请求频率和每日限额")
    print("5. 测试连接: 先用小范围查询测试网络连接")

if __name__ == "__main__":
    main()
