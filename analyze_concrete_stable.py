#!/usr/bin/env python3
"""
Concrete_STABLE 地址交互分析器
快速分析与 Concrete_STABLE 地址的所有 USDT 交互
"""

import os
import sys
from balance_surge_monitor import USDTBalanceSurgeMonitor
from address_constant import Concrete_STABLE
from datetime import datetime

def analyze_concrete_stable(api_key, days_back=30):
    """分析 Concrete_STABLE 地址的交互"""
    
    print("🎯 Concrete_STABLE 地址交互分析")
    print("=" * 80)
    print(f"📍 分析地址: {Concrete_STABLE}")
    print(f"⏰ 分析范围: 最近 {days_back} 天")
    print("=" * 80)
    
    # 创建监控器
    monitor = USDTBalanceSurgeMonitor(api_key)
    
    # 计算区块范围
    latest_block = monitor.get_latest_block()
    if not latest_block:
        print("❌ 无法获取最新区块信息")
        return
    
    blocks_per_day = 240 * 24  # 每天约5760个区块
    start_block = max(1, latest_block - (days_back * blocks_per_day))
    
    print(f"📊 区块范围: {start_block:,} - {latest_block:,}")
    
    # 获取交互数据
    interactions = monitor.get_address_interactions(
        Concrete_STABLE, 
        start_block, 
        latest_block
    )
    
    if not interactions:
        print("❌ 无法获取交互数据")
        return
    
    # 显示结果
    monitor.display_interactions(interactions)
    
    # 额外分析
    print_additional_analysis(interactions)
    
    # 保存结果
    save_analysis_results(interactions)

def print_additional_analysis(interactions_data):
    """打印额外的分析信息"""
    interactions = interactions_data['interactions']
    summary = interactions_data['analysis_summary']
    
    if not interactions:
        return
    
    print(f"\n" + "=" * 100)
    print("🔍 深度分析")
    print("=" * 100)
    
    # 分析交易模式
    total_addresses = len(interactions)
    senders_only = len([x for x in interactions.values() if x['sent_to_target'] > 0 and x['received_from_target'] == 0])
    receivers_only = len([x for x in interactions.values() if x['sent_to_target'] == 0 and x['received_from_target'] > 0])
    bidirectional = len([x for x in interactions.values() if x['sent_to_target'] > 0 and x['received_from_target'] > 0])
    
    print(f"📊 交互模式分析:")
    print(f"   🔄 双向交互地址: {bidirectional} ({bidirectional/total_addresses*100:.1f}%)")
    print(f"   📤 仅发送地址: {senders_only} ({senders_only/total_addresses*100:.1f}%)")
    print(f"   📥 仅接收地址: {receivers_only} ({receivers_only/total_addresses*100:.1f}%)")
    
    # 分析金额分布
    amounts = [abs(x['sent_to_target']) + abs(x['received_from_target']) for x in interactions.values()]
    amounts.sort(reverse=True)
    
    if amounts:
        print(f"\n💰 交互金额分析:")
        print(f"   💎 最大单地址交互: {amounts[0]:,.2f} USDT")
        print(f"   📊 平均交互金额: {sum(amounts)/len(amounts):,.2f} USDT")
        print(f"   📈 中位数交互金额: {amounts[len(amounts)//2]:,.2f} USDT")
        
        # 大额交互地址
        large_interactions = [x for x in interactions.values() 
                            if (x['sent_to_target'] + x['received_from_target']) >= 100000]  # 超过10万USDT
        
        if large_interactions:
            print(f"\n🐋 大额交互地址 (≥10万USDT):")
            large_interactions.sort(
                key=lambda x: x['sent_to_target'] + x['received_from_target'], 
                reverse=True
            )
            
            for i, addr_info in enumerate(large_interactions[:10], 1):
                total_amount = addr_info['sent_to_target'] + addr_info['received_from_target']
                print(f"   {i:2d}. {addr_info['address'][:10]}...{addr_info['address'][-6:]}: {total_amount:,.2f} USDT")
    
    # 分析时间模式
    all_transactions = []
    for addr_info in interactions.values():
        all_transactions.extend(addr_info['sent_transactions'])
        all_transactions.extend(addr_info['received_transactions'])
    
    if all_transactions:
        all_transactions.sort(key=lambda x: x['timestamp'])
        
        print(f"\n⏰ 时间模式分析:")
        print(f"   📅 最早交易: {all_transactions[0]['formatted_time']}")
        print(f"   📅 最近交易: {all_transactions[-1]['formatted_time']}")
        print(f"   📊 总交易数: {len(all_transactions):,}")
        
        # 分析最近活跃度
        recent_transactions = [tx for tx in all_transactions 
                             if tx['timestamp'] > (datetime.now().timestamp() - 7*24*3600)]  # 最近7天
        
        if recent_transactions:
            recent_amount = sum(tx['amount'] for tx in recent_transactions)
            print(f"   🔥 最近7天交易: {len(recent_transactions)} 笔, {recent_amount:,.2f} USDT")

def save_analysis_results(interactions_data):
    """保存分析结果"""
    try:
        # 确保 temp 目录存在
        import os
        os.makedirs('temp', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"temp/concrete_stable_analysis_{timestamp}.json"
        
        # 添加分析时间戳
        interactions_data['analysis_timestamp'] = datetime.now().isoformat()
        interactions_data['analyzed_address_name'] = 'Concrete_STABLE'
        
        import json
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(interactions_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 完整分析结果已保存到: {filename}")
        
        # 生成简化的地址列表
        if interactions_data['interactions']:
            addresses_filename = f"temp/concrete_stable_addresses_{timestamp}.txt"
            with open(addresses_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Concrete_STABLE ({Concrete_STABLE}) 交互地址列表\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 总计: {len(interactions_data['interactions'])} 个地址\n\n")
                
                # 按交互总金额排序
                sorted_addresses = sorted(
                    interactions_data['interactions'].values(),
                    key=lambda x: x['sent_to_target'] + x['received_from_target'],
                    reverse=True
                )
                
                for i, addr_info in enumerate(sorted_addresses, 1):
                    total_amount = addr_info['sent_to_target'] + addr_info['received_from_target']
                    f.write(f"{i:3d}. {addr_info['address']} - {total_amount:,.2f} USDT\n")
            
            print(f"📝 地址列表已保存到: {addresses_filename}")
        
    except Exception as e:
        print(f"⚠️ 保存文件时出错: {e}")

def main():
    """主函数"""
    print("🚀 Concrete_STABLE 交互分析器")
    print("=" * 50)
    
    # 检查 API 密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    
    if len(sys.argv) >= 2:
        # 命令行模式
        if not api_key:
            print("❌ 环境变量 ETHERSCAN_API_KEY 未设置")
            print("📝 获取免费 API 密钥: https://etherscan.io/apis")
            sys.exit(1)
        
        days_back = int(sys.argv[1]) if len(sys.argv) >= 2 else 30
    else:
        # 交互模式
        if not api_key:
            api_key = input("请输入 Etherscan API 密钥: ").strip()
            if not api_key:
                print("❌ API 密钥不能为空")
                return
        
        try:
            days_back = int(input("分析最近多少天的数据 (默认 30): ") or "30")
        except ValueError:
            print("❌ 输入格式错误，使用默认值 30 天")
            days_back = 30
    
    # 执行分析
    try:
        analyze_concrete_stable(api_key, days_back)
        print(f"\n🎉 分析完成！")
        
    except KeyboardInterrupt:
        print(f"\n👋 分析已停止")
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")

if __name__ == "__main__":
    main()