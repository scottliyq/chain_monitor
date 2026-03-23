#!/usr/bin/env python3
"""
简化的区块号测试脚本
测试不同网络的最新区块号获取
"""
import sys
import os
import time

from _path_setup import ensure_src_path

ensure_src_path()

from block_time_converter import BlockTimeConverter

def test_network_blocks():
    """测试不同网络的区块号"""
    print("🧪 测试不同网络的区块号查询")
    print("=" * 60)
    
    # 网络配置 - 统一使用etherscan的v2接口
    networks = {
        'ethereum': {
            'base_url': 'https://api.etherscan.io/v2/api',
            'api_key': os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken'),
            'chain_id': 1
        },
        'arbitrum': {
            'base_url': 'https://api.etherscan.io/v2/api',  # 统一使用etherscan的v2端点
            'api_key': os.getenv('ARBISCAN_API_KEY') or os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken'),
            'chain_id': 42161
        },
        'bsc': {
            'base_url': 'https://api.etherscan.io/v2/api',  # 统一使用etherscan的v2端点
            'api_key': os.getenv('BSCSCAN_API_KEY') or os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken'),
            'chain_id': 56
        }
    }
    
    results = {}
    
    for network_name, config in networks.items():
        print(f"\n🔍 测试 {network_name.upper()} 网络")
        print("-" * 40)
        
        try:
            # 创建区块转换器
            converter = BlockTimeConverter(config)
            
            # 测试获取最新区块号
            print(f"📦 获取最新区块号...")
            latest_block = converter.get_latest_block_number()
            
            if latest_block:
                print(f"   ✅ 最新区块号: {latest_block:,}")
                
                # 获取区块详情
                print(f"📋 获取区块详情...")
                block_info = converter.get_block_info(latest_block)
                
                if block_info:
                    print(f"   ✅ 区块详情获取成功")
                    print(f"   ⏰ 区块时间: {block_info['datetime'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    print(f"   🏗️ 矿工: {block_info['miner'][:42]}...")
                    print(f"   📊 交易数: {len(block_info['transactions'])}")
                    
                    results[network_name] = {
                        'latest_block': latest_block,
                        'block_time': block_info['datetime'],
                        'status': 'success'
                    }
                else:
                    print(f"   ❌ 无法获取区块详情")
                    results[network_name] = {
                        'latest_block': latest_block,
                        'status': 'partial_success'
                    }
            else:
                print(f"   ❌ 无法获取最新区块号")
                results[network_name] = {'status': 'failed'}
                
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            results[network_name] = {'status': 'error', 'error': str(e)}
        
        time.sleep(1)  # 避免API限制
    
    # 显示比较结果
    print(f"\n📊 网络对比结果")
    print("=" * 60)
    print(f"{'网络':<12} {'最新区块号':<15} {'状态':<12} {'区块时间'}")
    print("-" * 60)
    
    for network, data in results.items():
        status = data['status']
        if status == 'success':
            block_num = f"{data['latest_block']:,}"
            block_time = data['block_time'].strftime('%H:%M:%S UTC')
            print(f"{network:<12} {block_num:<15} ✅ 成功{' ':<6} {block_time}")
        elif status == 'partial_success':
            block_num = f"{data['latest_block']:,}"
            print(f"{network:<12} {block_num:<15} ⚠️ 部分成功{' ':<3} -")
        else:
            print(f"{network:<12} {'N/A':<15} ❌ 失败{' ':<6} -")
    
    # 分析区块号差异
    successful_networks = [n for n, d in results.items() if d['status'] in ['success', 'partial_success']]
    
    if len(successful_networks) > 1:
        print(f"\n📈 区块号特征分析")
        print("-" * 40)
        for network in successful_networks:
            data = results[network]
            latest = data['latest_block']
            
            # 估算网络的大致特征
            if network == 'ethereum':
                # 以太坊大约每12秒一个区块
                estimated_daily_blocks = 24 * 60 * 60 / 12
                print(f"{network}: 区块 {latest:,} (约每12秒一个区块)")
            elif network == 'arbitrum':
                # Arbitrum大约每0.25秒一个区块  
                estimated_daily_blocks = 24 * 60 * 60 / 0.25
                print(f"{network}: 区块 {latest:,} (约每0.25秒一个区块)")
            elif network == 'bsc':
                # BSC大约每3秒一个区块
                estimated_daily_blocks = 24 * 60 * 60 / 3
                print(f"{network}: 区块 {latest:,} (约每3秒一个区块)")

if __name__ == "__main__":
    test_network_blocks()
