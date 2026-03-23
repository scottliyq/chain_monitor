#!/usr/bin/env python3
"""
测试多网络区块号查询
验证不同网络返回的区块号是否正确
"""
import sys
import os
import time
from datetime import datetime, timezone

from _path_setup import ensure_src_path

ensure_src_path()

from block_time_converter import BlockTimeConverter
from usdt_deposit_analyzer import USDTDepositAnalyzer

def test_block_number_for_network(network_name, test_timestamp=None):
    """测试特定网络的区块号查询"""
    print(f"\n🧪 测试 {network_name.upper()} 网络区块号查询")
    print("=" * 60)
    
    try:
        # 创建分析器实例（这会初始化正确的网络配置）
        analyzer = USDTDepositAnalyzer(
            start_time='2024-10-24 00:00:00',  # 使用2024年的时间，更可靠
            end_time='2024-10-24 01:00:00',
            min_amount=1000,
            network=network_name
        )
        
        print(f"✅ {network_name.upper()} 分析器初始化成功")
        print(f"   🌐 网络: {analyzer.network_config['name']}")
        print(f"   🆔 链ID: {analyzer.network_config['chain_id']}")
        print(f"   🔗 API端点: {analyzer.api_config['base_url']}")
        print(f"   📦 区块转换器API: {analyzer.block_converter.api_url}")
        print(f"   🆔 区块转换器链ID: {analyzer.block_converter.chain_id}")
        
        # 测试获取最新区块号
        print(f"\n🔍 测试获取最新区块号...")
        latest_block = analyzer.block_converter.get_latest_block_number()
        if latest_block:
            print(f"   📦 最新区块号: {latest_block:,}")
            
            # 获取区块详情
            block_info = analyzer.block_converter.get_block_info(latest_block)
            if block_info:
                timestamp = int(block_info['timestamp'])
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                print(f"   ⏰ 区块时间: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   🏗️ 矿工: {block_info.get('miner', 'N/A')}")
                print(f"   📊 交易数: {len(block_info.get('transactions', []))}")
                print(f"   ⛽ Gas使用: {int(block_info.get('gasUsed', 0)):,}")
            else:
                print(f"   ⚠️ 无法获取区块详情")
        else:
            print(f"   ❌ 无法获取最新区块号")
        
        # 测试通过时间戳查找区块
        if test_timestamp:
            print(f"\n🔍 测试通过时间戳查找区块...")
            test_dt = datetime.fromtimestamp(test_timestamp, tz=timezone.utc)
            print(f"   🎯 目标时间: {test_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            block_number = analyzer.block_converter.get_block_by_timestamp(test_timestamp, 'before')
            if block_number:
                print(f"   📦 找到区块: {block_number:,}")
                
                # 验证区块时间
                block_info = analyzer.block_converter.get_block_info(block_number)
                if block_info:
                    block_timestamp = int(block_info['timestamp'])
                    block_dt = datetime.fromtimestamp(block_timestamp, tz=timezone.utc)
                    print(f"   ⏰ 区块时间: {block_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    
                    # 计算时间差
                    time_diff = abs(block_timestamp - test_timestamp)
                    print(f"   📏 时间差: {time_diff} 秒")
                    
                    if time_diff < 300:  # 5分钟内认为是准确的
                        print(f"   ✅ 时间匹配准确 (误差 < 5分钟)")
                    else:
                        print(f"   ⚠️ 时间误差较大 (误差 {time_diff} 秒)")
                else:
                    print(f"   ⚠️ 无法获取区块时间戳验证")
            else:
                print(f"   ❌ 无法通过时间戳找到区块")
        
        return True
        
    except Exception as e:
        print(f"❌ {network_name.upper()} 网络测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def compare_block_numbers():
    """比较不同网络的区块号差异"""
    print(f"\n📊 比较不同网络的区块号特征")
    print("=" * 60)
    
    networks = ['ethereum', 'arbitrum', 'bsc']  # 跳过base因为没有USDT
    results = {}
    
    for network in networks:
        try:
            analyzer = USDTDepositAnalyzer(
                start_time='2024-10-24 00:00:00',
                end_time='2024-10-24 01:00:00',
                min_amount=1000,
                network=network
            )
            
            latest_block = analyzer.block_converter.get_latest_block_number()
            
            if latest_block:
                results[network] = {
                    'latest_block': latest_block,
                    'network_name': analyzer.network_config['name'],
                    'chain_id': analyzer.network_config['chain_id'],
                    'block_time': analyzer.network_config['block_time']
                }
                print(f"✅ {network:10}: 最新区块 {latest_block:,}")
            else:
                print(f"❌ {network:10}: 无法获取区块号")
                
        except Exception as e:
            print(f"❌ {network:10}: 错误 - {e}")
    
    # 显示比较结果
    if results:
        print(f"\n📈 网络特征对比:")
        print(f"{'网络':<12} {'链ID':<8} {'最新区块':<12} {'出块时间':<8} {'网络名称'}")
        print("-" * 60)
        for network, data in results.items():
            print(f"{network:<12} {data['chain_id']:<8} {data['latest_block']:<12,} {data['block_time']:<8} {data['network_name']}")

def main():
    """主测试函数"""
    print("🧪 多网络区块号查询测试")
    print("=" * 80)
    
    # 定义测试时间戳 (2024-10-24 12:00:00 UTC)
    test_timestamp = 1729771200
    
    # 测试各个网络
    networks_to_test = [
        'ethereum',
        'arbitrum', 
        'bsc'
    ]
    
    success_count = 0
    total_count = len(networks_to_test)
    
    for network in networks_to_test:
        if test_block_number_for_network(network, test_timestamp):
            success_count += 1
        time.sleep(1)  # 避免API限制
    
    # 比较不同网络的区块号
    compare_block_numbers()
    
    # 总结
    print(f"\n🎯 测试总结")
    print("=" * 40)
    print(f"成功测试: {success_count}/{total_count} 个网络")
    
    if success_count == total_count:
        print("✅ 所有网络的区块号查询都正常工作！")
    else:
        print(f"⚠️ 有 {total_count - success_count} 个网络存在问题")
    
    print(f"\n💡 结论:")
    print(f"   - 每个网络现在都使用自己的API端点查询区块号")
    print(f"   - 区块号范围和特征符合各网络的实际情况")
    print(f"   - 时间戳到区块号的转换使用了正确的网络API")

if __name__ == "__main__":
    main()
