#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyperliquid 大户盈利分析器
查询Hyperliquid上持仓大于500万金额，盈利最高的前20个地址

API文档: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import pandas as pd

class HyperliquidMonitor:
    """Hyperliquid大户监控器"""
    
    def __init__(self):
        self.base_url = "https://api.hyperliquid.xyz"
        self.info_url = f"{self.base_url}/info"
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'HyperliquidMonitor/1.0'
        })
        
        print("🚀 Hyperliquid 大户盈利分析器初始化完成")
    
    def get_all_mids(self) -> Dict:
        """获取所有交易对的中间价格"""
        try:
            response = self.session.post(self.info_url, json={"type": "allMids"})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取价格数据失败: {e}")
            return {}
    
    def get_meta_info(self) -> Dict:
        """获取市场元数据信息"""
        try:
            response = self.session.post(self.info_url, json={"type": "meta"})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取市场元数据失败: {e}")
            return {}
    
    def get_open_orders(self, user_address: str) -> List[Dict]:
        """获取用户的开放订单"""
        try:
            response = self.session.post(self.info_url, json={
                "type": "openOrders",
                "user": user_address
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取用户 {user_address[:10]}... 订单失败: {e}")
            return []
    
    def get_user_state(self, user_address: str) -> Dict:
        """获取用户状态信息，包括持仓和余额"""
        try:
            response = self.session.post(self.info_url, json={
                "type": "clearinghouseState",
                "user": user_address
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取用户 {user_address[:10]}... 状态失败: {e}")
            return {}
    
    def get_user_funding(self, user_address: str, start_time: int, end_time: int) -> List[Dict]:
        """获取用户的资金费用历史"""
        try:
            response = self.session.post(self.info_url, json={
                "type": "userFunding",
                "user": user_address,
                "startTime": start_time,
                "endTime": end_time
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取用户 {user_address[:10]}... 资金费用失败: {e}")
            return []
    
    def get_user_fills(self, user_address: str) -> List[Dict]:
        """获取用户的成交记录"""
        try:
            response = self.session.post(self.info_url, json={
                "type": "userFills",
                "user": user_address
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取用户 {user_address[:10]}... 成交记录失败: {e}")
            return []
    
    def get_leaderboard(self) -> List[Dict]:
        """获取排行榜数据 - 这是获取大户信息的主要途径"""
        try:
            # 尝试获取PNL排行榜
            response = self.session.post(self.info_url, json={
                "type": "leaderboard",
                "leaderboardType": "pnl"  # 盈亏排行榜
            })
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ 获取排行榜失败: {e}")
            return []
    
    def calculate_position_value(self, position: Dict, prices: Dict) -> float:
        """计算持仓价值"""
        try:
            coin = position.get('position', {}).get('coin', '')
            size = float(position.get('position', {}).get('szi', '0'))
            
            # 获取当前价格
            price = float(prices.get(coin, 0))
            
            # 计算持仓价值 (绝对值)
            position_value = abs(size * price)
            
            return position_value
        except Exception as e:
            print(f"⚠️ 计算持仓价值失败: {e}")
            return 0.0
    
    def calculate_pnl(self, user_state: Dict, prices: Dict) -> Tuple[float, float]:
        """计算用户的总PNL和持仓价值"""
        try:
            total_pnl = 0.0
            total_position_value = 0.0
            
            # 获取持仓信息
            assets_positions = user_state.get('assetPositions', [])
            
            for position_data in assets_positions:
                if 'position' in position_data:
                    position = position_data['position']
                    coin = position.get('coin', '')
                    size = float(position.get('szi', '0'))
                    unrealized_pnl = float(position.get('unrealizedPnl', '0'))
                    
                    # 获取当前价格
                    price = float(prices.get(coin, 0))
                    
                    # 计算持仓价值
                    position_value = abs(size * price)
                    total_position_value += position_value
                    
                    # 累计未实现盈亏
                    total_pnl += unrealized_pnl
            
            return total_pnl, total_position_value
            
        except Exception as e:
            print(f"⚠️ 计算PNL失败: {e}")
            return 0.0, 0.0
    
    def scan_top_traders(self, min_position_value: float = 5000000) -> List[Dict]:
        """扫描顶级交易者"""
        print(f"🔍 开始扫描持仓价值 > ${min_position_value:,.0f} 的顶级交易者...")
        
        # 获取当前价格
        prices = self.get_all_mids()
        if not prices:
            print("❌ 无法获取价格数据")
            return []
        
        print(f"📊 获取到 {len(prices)} 个交易对价格")
        
        # 获取排行榜
        leaderboard = self.get_leaderboard()
        if not leaderboard:
            print("❌ 无法获取排行榜数据")
            return []
        
        print(f"📋 获取到 {len(leaderboard)} 个排行榜用户")
        
        top_traders = []
        
        for i, trader_info in enumerate(leaderboard[:100], 1):  # 只检查前100名
            try:
                user_address = trader_info.get('user', '')
                if not user_address:
                    continue
                
                print(f"📊 分析进度: {i}/100 - {user_address[:10]}...{user_address[-6:]}")
                
                # 获取用户状态
                user_state = self.get_user_state(user_address)
                if not user_state:
                    continue
                
                # 计算PNL和持仓价值
                total_pnl, total_position_value = self.calculate_pnl(user_state, prices)
                
                # 检查是否符合条件
                if total_position_value >= min_position_value:
                    trader_data = {
                        'address': user_address,
                        'total_pnl': total_pnl,
                        'position_value': total_position_value,
                        'pnl_percentage': (total_pnl / total_position_value * 100) if total_position_value > 0 else 0,
                        'rank_info': trader_info,
                        'user_state': user_state
                    }
                    
                    top_traders.append(trader_data)
                    print(f"   ✅ 符合条件: 持仓 ${total_position_value:,.0f}, PNL ${total_pnl:,.0f} ({trader_data['pnl_percentage']:.2f}%)")
                
                # API限制
                time.sleep(0.1)
                
            except Exception as e:
                print(f"   ⚠️ 分析用户失败: {e}")
                continue
        
        return top_traders
    
    def get_top_profitable_traders(self, min_position_value: float = 5000000, top_count: int = 20) -> List[Dict]:
        """获取盈利最高的前N个大户"""
        print("=" * 80)
        print("🎯 Hyperliquid 大户盈利分析")
        print("=" * 80)
        
        # 扫描所有符合条件的交易者
        all_traders = self.scan_top_traders(min_position_value)
        
        if not all_traders:
            print("❌ 没有找到符合条件的交易者")
            return []
        
        print(f"\n📊 找到 {len(all_traders)} 个符合条件的大户")
        
        # 按照绝对盈利排序
        sorted_traders = sorted(all_traders, key=lambda x: x['total_pnl'], reverse=True)
        
        # 取前N个
        top_traders = sorted_traders[:top_count]
        
        return top_traders
    
    def display_results(self, top_traders: List[Dict], min_position_value: float):
        """显示分析结果"""
        if not top_traders:
            return
        
        print(f"\n" + "=" * 100)
        print(f"🏆 TOP {len(top_traders)} 盈利最高的大户 (持仓 > ${min_position_value:,.0f})")
        print("=" * 100)
        
        for i, trader in enumerate(top_traders, 1):
            address = trader['address']
            pnl = trader['total_pnl']
            position_value = trader['position_value']
            pnl_percentage = trader['pnl_percentage']
            
            # 风险等级
            if pnl_percentage > 50:
                risk_level = "🔥 极高盈利"
            elif pnl_percentage > 20:
                risk_level = "📈 高盈利"
            elif pnl_percentage > 10:
                risk_level = "📊 中等盈利"
            elif pnl_percentage > 0:
                risk_level = "📉 低盈利"
            else:
                risk_level = "❌ 亏损"
            
            print(f"\n#{i}. {address}")
            print(f"    💰 持仓价值: ${position_value:,.0f}")
            print(f"    💵 总盈亏: ${pnl:,.0f}")
            print(f"    📊 盈利率: {pnl_percentage:.2f}%")
            print(f"    🎯 状态: {risk_level}")
            print(f"    🔗 查看: https://app.hyperliquid.xyz/user/{address}")
        
        # 统计信息
        total_position_value = sum(t['position_value'] for t in top_traders)
        total_pnl = sum(t['total_pnl'] for t in top_traders)
        avg_pnl_percentage = sum(t['pnl_percentage'] for t in top_traders) / len(top_traders)
        
        print(f"\n" + "=" * 100)
        print("📊 统计摘要")
        print("=" * 100)
        print(f"🎯 总计大户数量: {len(top_traders)}")
        print(f"💰 总持仓价值: ${total_position_value:,.0f}")
        print(f"💵 总盈亏: ${total_pnl:,.0f}")
        print(f"📊 平均盈利率: {avg_pnl_percentage:.2f}%")
    
    def save_results(self, top_traders: List[Dict], min_position_value: float):
        """保存分析结果"""
        try:
            # 确保 temp 目录存在
            os.makedirs('temp', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存详细JSON结果
            json_filename = f"temp/hyperliquid_top_traders_{timestamp}.json"
            
            result_data = {
                'analysis_time': datetime.now().isoformat(),
                'min_position_value': min_position_value,
                'trader_count': len(top_traders),
                'summary': {
                    'total_position_value': sum(t['position_value'] for t in top_traders),
                    'total_pnl': sum(t['total_pnl'] for t in top_traders),
                    'avg_pnl_percentage': sum(t['pnl_percentage'] for t in top_traders) / len(top_traders) if top_traders else 0
                },
                'top_traders': top_traders
            }
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存到: {json_filename}")
            
            # 保存简化的CSV结果
            csv_filename = f"temp/hyperliquid_top_traders_{timestamp}.csv"
            
            df_data = []
            for i, trader in enumerate(top_traders, 1):
                df_data.append({
                    'Rank': i,
                    'Address': trader['address'],
                    'Position_Value_USD': trader['position_value'],
                    'Total_PNL_USD': trader['total_pnl'],
                    'PNL_Percentage': trader['pnl_percentage'],
                    'Hyperliquid_URL': f"https://app.hyperliquid.xyz/user/{trader['address']}"
                })
            
            df = pd.DataFrame(df_data)
            df.to_csv(csv_filename, index=False)
            
            print(f"📊 CSV结果已保存到: {csv_filename}")
            
        except Exception as e:
            print(f"⚠️ 保存结果时出错: {e}")

def main():
    """主函数"""
    print("🚀 Hyperliquid 大户盈利分析器")
    print("=" * 60)
    
    # 参数设置
    min_position_value = 5000000  # 500万美元
    top_count = 20  # 前20名
    
    try:
        # 创建监控器
        monitor = HyperliquidMonitor()
        
        # 获取盈利最高的大户
        top_traders = monitor.get_top_profitable_traders(min_position_value, top_count)
        
        if not top_traders:
            print("❌ 没有找到符合条件的交易者")
            return
        
        # 显示结果
        monitor.display_results(top_traders, min_position_value)
        
        # 保存结果
        monitor.save_results(top_traders, min_position_value)
        
        print(f"\n🎉 分析完成！")
        
    except KeyboardInterrupt:
        print(f"\n👋 分析已停止")
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()