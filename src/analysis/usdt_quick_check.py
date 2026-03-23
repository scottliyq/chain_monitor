#!/usr/bin/env python3
"""
USDT 大额转账快速查询工具
使用 Etherscan API 查询最近的 USDT 大额转账记录
"""

import requests
import json
from datetime import datetime
from decimal import Decimal
import sys
import os
from dotenv import load_dotenv

load_dotenv()
# USDT 合约地址 (ERC-20)
USDT_CONTRACT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

def get_usdt_large_transfers(api_key, min_amount=1000000, hours_back=24):
    """
    查询 USDT 大额转账
    
    Args:
        api_key: Etherscan API 密钥
        min_amount: 最小金额阈值 (USDT)
        hours_back: 查询最近多少小时的数据
    """
    # 使用 Etherscan API V2
    base_url = "https://api.etherscan.io/v2/api"
    
    print(f"🔍 正在查询最近 {hours_back} 小时内超过 {min_amount:,.0f} USDT 的大额转账...")
    
    # 1. 获取最新区块号
    print("📊 获取最新区块信息...")
    block_params = {
        'chainid': '1',  # 以太坊主网
        'module': 'proxy',
        'action': 'eth_blockNumber',
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=block_params, timeout=10)
        response.raise_for_status()
        block_data = response.json()
        
        if 'result' not in block_data:
            print(f"❌ 获取区块信息失败: {block_data}")
            return
            
        latest_block = int(block_data['result'], 16)
        blocks_per_hour = 240  # 约 15 秒一个块
        start_block = latest_block - (hours_back * blocks_per_hour)
        
        print(f"📈 最新区块: {latest_block:,}")
        print(f"📉 开始区块: {start_block:,}")
        
    except Exception as e:
        print(f"❌ 获取区块信息出错: {e}")
        return
    
    # 2. 获取 USDT 转账记录
    print("🔄 获取 USDT 转账记录...")
    transfer_params = {
        'chainid': '1',  # 以太坊主网
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': USDT_CONTRACT_ADDRESS,
        'startblock': start_block,
        'endblock': latest_block,
        'page': 1,
        'offset': 10000,
        'sort': 'desc',
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=transfer_params, timeout=30)
        response.raise_for_status()
        transfer_data = response.json()
        
        if transfer_data['status'] != '1' or 'result' not in transfer_data:
            print(f"❌ 获取转账记录失败: {transfer_data.get('message', '未知错误')}")
            return
            
        transfers = transfer_data['result']
        print(f"📋 获取到 {len(transfers):,} 条转账记录")
        
    except Exception as e:
        print(f"❌ 获取转账记录出错: {e}")
        return
    
    # 3. 筛选大额转账
    print(f"🔍 筛选超过 {min_amount:,.0f} USDT 的大额转账...")
    large_transfers = []
    
    for tx in transfers:
        try:
            # USDT 使用 6 位小数
            amount = Decimal(tx['value']) / Decimal(10**6)
            
            if amount >= min_amount:
                tx['formatted_amount'] = float(amount)
                tx['amount_str'] = f"{amount:,.2f} USDT"
                tx['formatted_time'] = datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')
                large_transfers.append(tx)
                
        except (ValueError, KeyError) as e:
            continue
    
    # 4. 显示结果
    if not large_transfers:
        print(f"✅ 最近 {hours_back} 小时内没有发现超过 {min_amount:,.0f} USDT 的大额转账")
        return
    
    # 按金额降序排序
    large_transfers.sort(key=lambda x: x['formatted_amount'], reverse=True)
    
    # 统计信息
    total_amount = sum(tx['formatted_amount'] for tx in large_transfers)
    unique_from = len(set(tx['from'] for tx in large_transfers))
    unique_to = len(set(tx['to'] for tx in large_transfers))
    
    print("\n" + "=" * 100)
    print("🎯 USDT 大额转账发现报告")
    print("=" * 100)
    print(f"⏰ 查询时间范围: 最近 {hours_back} 小时")
    print(f"💰 金额阈值: {min_amount:,.0f} USDT")
    print(f"📊 大额转账数量: {len(large_transfers):,} 笔")
    print(f"💵 大额转账总金额: {total_amount:,.2f} USDT")
    print(f"📤 涉及发送地址: {unique_from} 个")
    print(f"📥 涉及接收地址: {unique_to} 个")
    
    print(f"\n🏆 前 {min(10, len(large_transfers))} 笔最大转账:")
    print("-" * 100)
    
    for i, tx in enumerate(large_transfers[:10], 1):
        print(f"\n{i:2d}. 💰 {tx['amount_str']}")
        print(f"    📤 发送方: {tx['from']}")
        print(f"    📥 接收方: {tx['to']}")
        print(f"    🕐 时间: {tx['formatted_time']}")
        print(f"    🔗 交易: https://etherscan.io/tx/{tx['hash']}")
        
        # 计算 Gas 费用
        try:
            gas_fee = int(tx['gasUsed']) * int(tx['gasPrice']) / 10**18
            print(f"    ⛽ Gas 费: {gas_fee:.6f} ETH")
        except:
            pass
    
    # 地址统计
    print(f"\n📊 地址统计:")
    print("-" * 100)
    
    # 发送方统计
    from_amounts = {}
    for tx in large_transfers:
        addr = tx['from']
        amount = tx['formatted_amount']
        from_amounts[addr] = from_amounts.get(addr, 0) + amount
    
    top_senders = sorted(from_amounts.items(), key=lambda x: x[1], reverse=True)[:5]
    print("📤 发送金额最多的地址 (TOP 5):")
    for i, (addr, amount) in enumerate(top_senders, 1):
        print(f"   {i}. {addr} - {amount:,.2f} USDT")
    
    # 接收方统计
    to_amounts = {}
    for tx in large_transfers:
        addr = tx['to']
        amount = tx['formatted_amount']
        to_amounts[addr] = to_amounts.get(addr, 0) + amount
    
    top_receivers = sorted(to_amounts.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n📥 接收金额最多的地址 (TOP 5):")
    for i, (addr, amount) in enumerate(top_receivers, 1):
        print(f"   {i}. {addr} - {amount:,.2f} USDT")
    
    print("\n" + "=" * 100)
    
    # 保存结果到文件
    try:
        # 确保 temp 目录存在
        import os
        os.makedirs('temp', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"temp/usdt_large_transfers_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'query_time': datetime.now().isoformat(),
                'parameters': {
                    'min_amount': min_amount,
                    'hours_back': hours_back,
                    'block_range': f"{start_block}-{latest_block}"
                },
                'summary': {
                    'total_transfers': len(large_transfers),
                    'total_amount': total_amount,
                    'unique_from_addresses': unique_from,
                    'unique_to_addresses': unique_to
                },
                'transfers': large_transfers
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 详细结果已保存到: {filename}")
        
    except Exception as e:
        print(f"⚠️ 保存文件时出错: {e}")

def get_usdt_balance(api_key, address, block_number=None):
    """
    获取指定地址在指定区块的 USDT 余额
    
    Args:
        api_key: Etherscan API 密钥
        address: 地址
        block_number: 区块号，None 表示最新区块
    
    Returns:
        USDT 余额（float）或 None（如果出错）
    """
    base_url = "https://api.etherscan.io/v2/api"
    
    params = {
        'chainid': '1',
        'module': 'account',
        'action': 'tokenbalance',
        'contractaddress': USDT_CONTRACT_ADDRESS,
        'address': address,
        'tag': 'latest' if block_number is None else hex(block_number),
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == '1' and 'result' in data:
            # USDT 使用 6 位小数
            balance = Decimal(data['result']) / Decimal(10**6)
            return float(balance)
        else:
            print(f"⚠️ 获取地址 {address} 余额失败: {data.get('message', '未知错误')}")
            return None
            
    except Exception as e:
        print(f"❌ 获取地址 {address} 余额出错: {e}")
        return None

def monitor_balance_surge_addresses(api_key, min_increase=5000000, min_48h_balance=100000):
    """
    监控最近24小时USDT余额新增超过5M，且48小时前余额<100k的地址
    
    Args:
        api_key: Etherscan API 密钥
        min_increase: 最小增长金额阈值 (USDT)，默认500万
        min_48h_balance: 48小时前的最大余额阈值 (USDT)，默认10万
    
    Returns:
        符合条件的地址列表
    """
    base_url = "https://api.etherscan.io/v2/api"
    
    print("🔍 开始监控余额激增的地址...")
    print(f"📊 筛选条件:")
    print(f"   - 最近24小时新增: ≥ {min_increase:,.0f} USDT")
    print(f"   - 48小时前余额: < {min_48h_balance:,.0f} USDT")
    
    # 1. 获取最新区块号
    print("\n📊 获取区块信息...")
    block_params = {
        'chainid': '1',
        'module': 'proxy',
        'action': 'eth_blockNumber',
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=block_params, timeout=10)
        response.raise_for_status()
        block_data = response.json()
        
        if 'result' not in block_data:
            print(f"❌ 获取区块信息失败: {block_data}")
            return []
            
        latest_block = int(block_data['result'], 16)
        blocks_per_hour = 240  # 约 15 秒一个块
        block_24h_ago = latest_block - (24 * blocks_per_hour)
        block_48h_ago = latest_block - (48 * blocks_per_hour)
        
        print(f"📈 最新区块: {latest_block:,}")
        print(f"📉 24小时前区块: {block_24h_ago:,}")
        print(f"📉 48小时前区块: {block_48h_ago:,}")
        
    except Exception as e:
        print(f"❌ 获取区块信息出错: {e}")
        return []
    
    # 2. 获取最近24小时的所有USDT转账（接收方）
    print("\n🔄 获取最近24小时的 USDT 转账记录...")
    transfer_params = {
        'chainid': '1',
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': USDT_CONTRACT_ADDRESS,
        'startblock': block_24h_ago,
        'endblock': latest_block,
        'page': 1,
        'offset': 10000,
        'sort': 'desc',
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=transfer_params, timeout=30)
        response.raise_for_status()
        transfer_data = response.json()
        
        if transfer_data['status'] != '1' or 'result' not in transfer_data:
            print(f"❌ 获取转账记录失败: {transfer_data.get('message', '未知错误')}")
            return []
            
        transfers = transfer_data['result']
        print(f"📋 获取到 {len(transfers):,} 条转账记录")
        
    except Exception as e:
        print(f"❌ 获取转账记录出错: {e}")
        return []
    
    # 3. 统计各地址的接收总额
    print("\n📊 统计地址接收金额...")
    address_received = {}
    
    for tx in transfers:
        try:
            to_address = tx['to'].lower()
            amount = Decimal(tx['value']) / Decimal(10**6)
            
            if to_address in address_received:
                address_received[to_address] += float(amount)
            else:
                address_received[to_address] = float(amount)
                
        except (ValueError, KeyError) as e:
            continue
    
    # 4. 筛选接收金额超过阈值的地址
    candidate_addresses = []
    for address, received_amount in address_received.items():
        if received_amount >= min_increase:
            candidate_addresses.append((address, received_amount))
    
    print(f"🎯 找到 {len(candidate_addresses)} 个候选地址（24小时接收 ≥ {min_increase:,.0f} USDT）")
    
    if not candidate_addresses:
        print("✅ 没有找到符合接收金额条件的地址")
        return []
    
    # 5. 检查这些地址48小时前的余额
    print(f"\n🔍 检查候选地址48小时前的余额...")
    qualified_addresses = []
    
    for i, (address, received_amount) in enumerate(candidate_addresses, 1):
        print(f"检查 {i}/{len(candidate_addresses)}: {address[:10]}...{address[-6:]}")
        
        # 获取48小时前的余额
        balance_48h_ago = get_usdt_balance(api_key, address, block_48h_ago)
        
        if balance_48h_ago is None:
            print(f"   ⚠️ 无法获取48小时前余额，跳过")
            continue
        
        # 获取当前余额
        current_balance = get_usdt_balance(api_key, address)
        
        if current_balance is None:
            print(f"   ⚠️ 无法获取当前余额，跳过")
            continue
        
        # 计算余额增长
        balance_increase = current_balance - balance_48h_ago
        
        print(f"   📊 48小时前余额: {balance_48h_ago:,.2f} USDT")
        print(f"   📊 当前余额: {current_balance:,.2f} USDT")
        print(f"   📈 余额增长: {balance_increase:,.2f} USDT")
        print(f"   📥 24小时接收: {received_amount:,.2f} USDT")
        
        # 检查是否符合条件
        if (balance_48h_ago < min_48h_balance and 
            balance_increase >= min_increase):
            
            qualified_addresses.append({
                'address': address,
                'balance_48h_ago': balance_48h_ago,
                'current_balance': current_balance,
                'balance_increase': balance_increase,
                'received_24h': received_amount,
                'increase_ratio': (balance_increase / max(balance_48h_ago, 1)) * 100
            })
            
            print(f"   ✅ 符合条件！")
        else:
            reasons = []
            if balance_48h_ago >= min_48h_balance:
                reasons.append(f"48小时前余额过高 ({balance_48h_ago:,.2f} ≥ {min_48h_balance:,.0f})")
            if balance_increase < min_increase:
                reasons.append(f"增长金额不足 ({balance_increase:,.2f} < {min_increase:,.0f})")
            print(f"   ❌ 不符合条件: {', '.join(reasons)}")
        
        # API限制，每次请求间隔
        import time
        time.sleep(0.2)
    
    # 6. 显示结果
    if qualified_addresses:
        print(f"\n" + "=" * 100)
        print(f"🎉 发现 {len(qualified_addresses)} 个符合条件的地址!")
        print("=" * 100)
        
        # 按增长比例排序
        qualified_addresses.sort(key=lambda x: x['increase_ratio'], reverse=True)
        
        for i, addr_info in enumerate(qualified_addresses, 1):
            print(f"\n{i}. 🏆 地址: {addr_info['address']}")
            print(f"   📊 48小时前余额: {addr_info['balance_48h_ago']:,.2f} USDT")
            print(f"   📊 当前余额: {addr_info['current_balance']:,.2f} USDT")
            print(f"   📈 余额增长: {addr_info['balance_increase']:,.2f} USDT")
            print(f"   📥 24小时接收: {addr_info['received_24h']:,.2f} USDT")
            print(f"   📊 增长倍数: {addr_info['increase_ratio']:,.1f}%")
            print(f"   🔗 地址链接: https://etherscan.io/address/{addr_info['address']}")
        
        # 保存结果到文件
        try:
            # 确保 temp 目录存在
            import os
            os.makedirs('temp', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"temp/usdt_balance_surge_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'query_time': datetime.now().isoformat(),
                    'parameters': {
                        'min_increase': min_increase,
                        'min_48h_balance': min_48h_balance,
                        'block_range': f"{block_48h_ago}-{latest_block}"
                    },
                    'summary': {
                        'qualified_addresses_count': len(qualified_addresses),
                        'candidate_addresses_count': len(candidate_addresses),
                        'total_transfers_checked': len(transfers)
                    },
                    'qualified_addresses': qualified_addresses
                }, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存到: {filename}")
            
        except Exception as e:
            print(f"⚠️ 保存文件时出错: {e}")
    else:
        print(f"\n✅ 没有找到符合所有条件的地址")
        print(f"   - 48小时前余额 < {min_48h_balance:,.0f} USDT")
        print(f"   - 余额增长 ≥ {min_increase:,.0f} USDT")
    
    return qualified_addresses

def main():
    """主函数"""
    print("🚀 USDT 监控工具")
    print("=" * 50)
    
    # API 密钥
    api_key = input("请输入您的 Etherscan API 密钥: ").strip()
    if not api_key:
        print("❌ API 密钥不能为空")
        print("📝 获取免费 API 密钥: https://etherscan.io/apis")
        return
    
    # 选择功能
    print("\n请选择功能:")
    print("1. 🔍 查询大额转账")
    print("2. 📈 监控余额激增地址")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        # 大额转账查询
        try:
            min_amount = float(input("最小金额阈值 (USDT, 默认 1000000): ") or "1000000")
            hours_back = int(input("查询最近多少小时 (默认 24): ") or "24")
        except ValueError:
            print("❌ 输入参数格式错误")
            return
        
        # 执行查询
        get_usdt_large_transfers(api_key, min_amount, hours_back)
        
    elif choice == "2":
        # 余额激增监控
        try:
            min_increase = float(input("最小增长金额 (USDT, 默认 5000000): ") or "5000000")
            min_48h_balance = float(input("48小时前最大余额 (USDT, 默认 100000): ") or "100000")
        except ValueError:
            print("❌ 输入参数格式错误")
            return
        
        # 执行监控
        qualified_addresses = monitor_balance_surge_addresses(api_key, min_increase, min_48h_balance)
        
        if qualified_addresses:
            print(f"\n🎯 监控完成，发现 {len(qualified_addresses)} 个符合条件的地址")
        else:
            print(f"\n✅ 监控完成，未发现符合条件的地址")
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    # 如果提供了命令行参数，直接使用
    api_key = os.getenv('ETHERSCAN_API_KEY')
    
    if len(sys.argv) >= 2:
        # 命令行模式
        if not api_key:
            print("❌ 环境变量 ETHERSCAN_API_KEY 未设置")
            print("📝 获取免费 API 密钥: https://etherscan.io/apis")
            print("💡 请设置环境变量或使用交互模式")
            sys.exit(1)
        
        # 检查是否是余额监控模式
        if len(sys.argv) >= 2 and sys.argv[1] == "balance":
            # 余额激增监控模式
            min_increase = float(sys.argv[2]) if len(sys.argv) >= 3 else 5000000
            min_48h_balance = float(sys.argv[3]) if len(sys.argv) >= 4 else 100000
            
            print(f"🚀 余额激增监控模式")
            qualified_addresses = monitor_balance_surge_addresses(api_key, min_increase, min_48h_balance)
            
            if qualified_addresses:
                print(f"\n🎯 发现 {len(qualified_addresses)} 个符合条件的地址")
            else:
                print(f"\n✅ 未发现符合条件的地址")
        else:
            # 大额转账查询模式
            min_amount = float(sys.argv[1]) if len(sys.argv) >= 2 else 1000000
            hours_back = int(sys.argv[2]) if len(sys.argv) >= 3 else 24
            
            get_usdt_large_transfers(api_key, min_amount, hours_back)
    else:
        # 交互模式
        main()