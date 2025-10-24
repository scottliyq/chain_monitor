#!/usr/bin/env python3
"""
快速地址交互分析工具
基于已有的方法直接分析地址交互
"""

import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime
from collections import Counter

# USDT 合约地址
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

def make_etherscan_request(api_key, params):
    """发送Etherscan API请求"""
    base_url = "https://api.etherscan.io/v2/api"
    params['apikey'] = api_key
    
    try:
        query_string = urllib.parse.urlencode(params)
        url = f"{base_url}?{query_string}"
        
        response = urllib.request.urlopen(url, timeout=30)
        data = response.read().decode('utf-8')
        
        return json.loads(data)
        
    except Exception as e:
        print(f"⚠️ API 请求失败: {e}")
        return None

def get_latest_block(api_key):
    """获取最新区块号"""
    params = {
        'chainid': '1',
        'module': 'proxy',
        'action': 'eth_blockNumber'
    }
    
    data = make_etherscan_request(api_key, params)
    
    if data and 'result' in data:
        return int(data['result'], 16)
    return None

def get_address_recent_transfers(api_key, address, hours=24):
    """获取地址最近的USDT转账记录"""
    # 获取最新区块
    latest_block = get_latest_block(api_key)
    if not latest_block:
        return []
    
    # 计算起始区块 (大约每15秒一个块)
    blocks_per_hour = 240
    start_block = latest_block - (hours * blocks_per_hour)
    
    params = {
        'chainid': '1',
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': USDT_CONTRACT_ADDRESS,
        'address': address,
        'startblock': start_block,
        'endblock': latest_block,
        'page': 1,
        'offset': 10000,
        'sort': 'desc'
    }
    
    data = make_etherscan_request(api_key, params)
    
    if data and data['status'] == '1' and 'result' in data:
        return data['result']
    return []

def analyze_address_interactions(api_key, address):
    """分析单个地址的交互情况"""
    transfers = get_address_recent_transfers(api_key, address, 24)
    
    if not transfers:
        return None
    
    counterparts = set()
    sent_to = {}
    received_from = {}
    
    for tx in transfers:
        try:
            from_addr = tx['from'].lower()
            to_addr = tx['to'].lower()
            amount = float(tx['value']) / 1000000  # USDT has 6 decimals
            
            if from_addr == address.lower():
                # 当前地址发送
                counterparts.add(to_addr)
                sent_to[to_addr] = sent_to.get(to_addr, 0) + amount
            
            if to_addr == address.lower():
                # 当前地址接收
                counterparts.add(from_addr)
                received_from[from_addr] = received_from.get(from_addr, 0) + amount
                
        except (ValueError, KeyError):
            continue
    
    return {
        'counterparts': list(counterparts),
        'sent_to': sent_to,
        'received_from': received_from,
        'total_counterparts': len(counterparts),
        'total_transactions': len(transfers)
    }

def extract_addresses_from_file(file_path):
    """从文件提取地址"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取所有0x开头的40字符地址
        address_pattern = r'0x[a-fA-F0-9]{40}'
        addresses = re.findall(address_pattern, content)
        
        # 去重并转小写
        unique_addresses = list(set([addr.lower() for addr in addresses]))
        
        # 排除Concrete_STABLE地址本身
        concrete_stable = "0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f".lower()
        filtered_addresses = [addr for addr in unique_addresses if addr != concrete_stable]
        
        return filtered_addresses
        
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return []

def main():
    """主函数"""
    print("🚀 快速地址交互分析")
    print("=" * 50)
    
    # 获取API密钥
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("💡 请输入Etherscan API密钥 (在etherscan.io申请免费API密钥)")
        api_key = input("API Key: ").strip()
        if not api_key:
            print("❌ 需要API密钥才能继续")
            return
    
    # 文件路径
    file_path = "temp/concrete_stable_addresses_20251024_153119.txt"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    # 提取地址
    addresses = extract_addresses_from_file(file_path)
    print(f"📋 找到 {len(addresses)} 个地址")
    
    if not addresses:
        print("❌ 没有有效地址")
        return
    
    # 限制分析数量
    max_analyze = 15
    analyze_list = addresses[:max_analyze]
    
    print(f"🔍 分析前 {len(analyze_list)} 个地址的24小时交互情况...")
    print("=" * 60)
    
    # 存储结果
    all_interactions = {}
    all_counterparts = Counter()
    
    for i, address in enumerate(analyze_list, 1):
        print(f"\n{i:2d}. {address[:10]}...{address[-6:]}")
        
        try:
            result = analyze_address_interactions(api_key, address)
            
            if result:
                all_interactions[address] = result
                
                # 统计所有交互对手
                for counterpart in result['counterparts']:
                    all_counterparts[counterpart] += 1
                
                print(f"    ✅ {result['total_transactions']} 笔交易, {result['total_counterparts']} 个交互地址")
            else:
                print(f"    ❌ 无交易记录")
                
        except Exception as e:
            print(f"    ⚠️ 分析失败: {e}")
        
        # 短暂延时
        import time
        time.sleep(0.3)
    
    # 分析结果
    print(f"\n" + "=" * 80)
    print("📊 分析结果")
    print("=" * 80)
    
    print(f"🎯 成功分析地址: {len(all_interactions)}")
    print(f"🌐 总交互地址数: {len(all_counterparts)}")
    
    # 查找共同交互地址
    common_interactions = {addr: count for addr, count in all_counterparts.items() if count >= 2}
    
    print(f"🤝 共同交互地址: {len(common_interactions)}")
    
    if common_interactions:
        print(f"\n🏆 被多个地址交互的地址:")
        print("-" * 70)
        
        sorted_common = sorted(common_interactions.items(), key=lambda x: x[1], reverse=True)
        
        for i, (addr, count) in enumerate(sorted_common[:10], 1):
            percentage = (count / len(all_interactions)) * 100
            print(f"{i:2d}. {addr}")
            print(f"    🔗 被 {count} 个地址交互 ({percentage:.1f}%)")
            print(f"    🌐 https://etherscan.io/address/{addr}")
            print()
    else:
        print("\n✅ 没有发现共同交互地址")
        print("💡 说明这些地址的交互模式相对独立")
    
    # 保存结果
    try:
        os.makedirs('temp', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"temp/quick_interaction_analysis_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# 快速地址交互分析结果\n")
            f.write(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 分析地址数: {len(all_interactions)}\n\n")
            
            f.write("=== 个人交互统计 ===\n")
            for addr, data in all_interactions.items():
                f.write(f"{addr}: {data['total_transactions']} 交易, {data['total_counterparts']} 交互地址\n")
            
            if common_interactions:
                f.write(f"\n=== 共同交互地址 ===\n")
                for addr, count in sorted_common:
                    f.write(f"{addr} - {count} 次交互\n")
        
        print(f"\n💾 结果已保存: {filename}")
        
    except Exception as e:
        print(f"⚠️ 保存失败: {e}")
    
    print(f"\n🎉 分析完成！")

if __name__ == "__main__":
    main()