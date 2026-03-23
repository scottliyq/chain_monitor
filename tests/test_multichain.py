#!/usr/bin/env python3
"""
多链USDT分析器测试脚本
"""
import sys
import os

from _path_setup import ensure_src_path

ensure_src_path()

from address_constant import TOKEN_CONTRACTS, get_token_address
from usdt_deposit_analyzer import USDTDepositAnalyzer

def test_address_constants():
    """测试地址常量"""
    print("🔍 测试多链代币地址常量")
    print("=" * 50)
    
    # 测试所有网络的USDT地址
    for network in ["ethereum", "arbitrum", "base", "bsc"]:
        usdt_address = get_token_address(network, "USDT")
        usdc_address = get_token_address(network, "USDC")
        
        print(f"\n🌐 {network.upper()}:")
        print(f"   USDT: {usdt_address}")
        print(f"   USDC: {usdc_address}")
        
        if usdt_address == "0x0000000000000000000000000000000000000000":
            print(f"   ⚠️  {network} 不支持USDT")
        elif not usdt_address:
            print(f"   ❌ {network} USDT地址未配置")
        else:
            print(f"   ✅ {network} USDT地址配置正确")

def test_analyzer_initialization():
    """测试分析器初始化"""
    print("\n\n🧪 测试多链分析器初始化")
    print("=" * 50)
    
    test_networks = ["ethereum", "arbitrum", "bsc"]  # 跳过base因为没有USDT
    
    for network in test_networks:
        print(f"\n🔧 测试 {network.upper()} 网络:")
        try:
            analyzer = USDTDepositAnalyzer(
                start_time='2025-01-01 00:00:00',
                end_time='2025-01-01 01:00:00', 
                min_amount=1000,
                network=network
            )
            
            print(f"   ✅ 初始化成功")
            print(f"   📍 USDT地址: {analyzer.USDT_CONTRACT_ADDRESS}")
            print(f"   🆔 链ID: {analyzer.network_config['chain_id']}")
            print(f"   📊 小数位: {analyzer.usdt_decimals}")
            print(f"   🌐 API端点: {analyzer.api_config['base_url']}")
            
        except Exception as e:
            print(f"   ❌ 初始化失败: {e}")

def test_unsupported_network():
    """测试不支持的网络"""
    print("\n\n🚫 测试不支持的网络")
    print("=" * 50)
    
    # 测试Base网络（没有USDT）
    try:
        analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',
            end_time='2025-01-01 01:00:00', 
            min_amount=1000,
            network='base'
        )
        print("❌ Base网络不应该成功，因为没有USDT")
    except Exception as e:
        print(f"✅ 正确拒绝Base网络: {e}")
    
    # 测试无效网络
    try:
        analyzer = USDTDepositAnalyzer(
            start_time='2025-01-01 00:00:00',
            end_time='2025-01-01 01:00:00', 
            min_amount=1000,
            network='polygon'  # 不支持的网络
        )
        print("❌ 无效网络不应该成功")
    except Exception as e:
        print(f"✅ 正确拒绝无效网络: {e}")

def main():
    """主函数"""
    print("🚀 多链USDT分析器综合测试")
    print("=" * 60)
    
    test_address_constants()
    test_analyzer_initialization()
    test_unsupported_network()
    
    print("\n\n🎉 测试完成!")
    print("=" * 60)
    print("\n📖 使用说明:")
    print("  python src/token_deposit_analyzer.py '开始时间' '结束时间' [最小金额] [网络]")
    print("\n🌐 支持的网络:")
    print("  - ethereum (默认)")
    print("  - arbitrum") 
    print("  - bsc")
    print("\n📋 示例:")
    print("  python src/token_deposit_analyzer.py '2025-01-01 00:00:00' '2025-01-01 01:00:00' 1000 arbitrum")

if __name__ == "__main__":
    main()
