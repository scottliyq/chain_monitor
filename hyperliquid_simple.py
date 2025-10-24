#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyperliquid 大户盈利分析器 - 轻量版
查询Hyperliquid上持仓大于500万金额，盈利最高的前20个地址

API文档: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
只使用Python标准库，无需额外依赖
"""

import json
import time
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

class HyperliquidMonitor:
    """Hyperliquid大户监控器 - 轻量版"""
    
    def __init__(self):
        self.base_url = "https://api.hyperliquid.xyz"
        self.info_url = f"{self.base_url}/info"
        
        print("🚀 Hyperliquid 大户盈利分析器初始化完成")
    
    def make_request(self, data: Dict) -> Dict:
        """发送POST请求"""
        try:
            json_data = json.dumps(data).encode('utf-8')
            
            req = urllib.request.Request(
                self.info_url,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'HyperliquidMonitor/1.0'
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except Exception as e:
            print(f"⚠️ 请求失败: {e}")
            return {}
    
    def get_all_mids(self) -> Dict:
        """获取所有交易对的中间价格"""
        return self.make_request({"type": "allMids"})
    
    def get_meta_info(self) -> Dict:
        """获取市场元数据信息"""
        return self.make_request({"type": "meta"})
    
    def get_user_state(self, user_address: str) -> Dict:
        """获取用户状态信息，包括持仓和余额"""
        return self.make_request({
            "type": "clearinghouseState",
            "user": user_address
        })
    
    def get_leaderboard(self) -> List[Dict]:
        """获取排行榜数据"""
        try:
            result = self.make_request({
                "type": "leaderboard",
                "leaderboardType": "pnl"
            })
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"⚠️ 获取排行榜失败: {e}")
            return []
    
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
        
        # 限制检查数量以避免过多API调用
        check_count = min(len(leaderboard), 50)
        
        for i, trader_info in enumerate(leaderboard[:check_count], 1):
            try:
                user_address = trader_info.get('user', '')
                if not user_address:
                    continue
                
                print(f"📊 分析进度: {i}/{check_count} - {user_address[:10]}...{user_address[-6:]}")
                
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
                        'rank_info': trader_info
                    }
                    
                    top_traders.append(trader_data)
                    print(f"   ✅ 符合条件: 持仓 ${total_position_value:,.0f}, PNL ${total_pnl:,.0f} ({trader_data['pnl_percentage']:.2f}%)")
                
                # API限制
                time.sleep(0.2)
                
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
            
            # 盈利等级
            if pnl_percentage > 50:
                profit_level = "🔥 极高盈利"
            elif pnl_percentage > 20:
                profit_level = "📈 高盈利"
            elif pnl_percentage > 10:
                profit_level = "📊 中等盈利"
            elif pnl_percentage > 0:
                profit_level = "📉 低盈利"
            else:
                profit_level = "❌ 亏损"
            
            print(f"\n#{i}. {address}")
            print(f"    💰 持仓价值: ${position_value:,.0f}")
            print(f"    💵 总盈亏: ${pnl:,.0f}")
            print(f"    📊 盈利率: {pnl_percentage:.2f}%")
            print(f"    🎯 状态: {profit_level}")
            print(f"    🔗 查看: https://app.hyperliquid.xyz/user/{address}")
        
        # 统计信息
        total_position_value = sum(t['position_value'] for t in top_traders)
        total_pnl = sum(t['total_pnl'] for t in top_traders)
        avg_pnl_percentage = sum(t['pnl_percentage'] for t in top_traders) / len(top_traders)
        profitable_count = len([t for t in top_traders if t['total_pnl'] > 0])
        
        print(f"\n" + "=" * 100)
        print("📊 统计摘要")
        print("=" * 100)
        print(f"🎯 总计大户数量: {len(top_traders)}")
        print(f"💰 总持仓价值: ${total_position_value:,.0f}")
        print(f"💵 总盈亏: ${total_pnl:,.0f}")
        print(f"📊 平均盈利率: {avg_pnl_percentage:.2f}%")
        print(f"📈 盈利用户数: {profitable_count}/{len(top_traders)} ({profitable_count/len(top_traders)*100:.1f}%)")
    
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
                    'avg_pnl_percentage': sum(t['pnl_percentage'] for t in top_traders) / len(top_traders) if top_traders else 0,
                    'profitable_count': len([t for t in top_traders if t['total_pnl'] > 0])
                },
                'top_traders': top_traders
            }
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存到: {json_filename}")
            
            # 保存简化的TXT结果
            txt_filename = f"temp/hyperliquid_top_traders_{timestamp}.txt"
            
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Hyperliquid 大户盈利分析结果\n")
                f.write(f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 最小持仓要求: ${min_position_value:,.0f}\n")
                f.write(f"# 大户数量: {len(top_traders)}\n\n")
                
                f.write("=" * 80 + "\n")
                f.write(f"TOP {len(top_traders)} 盈利最高的大户\n")
                f.write("=" * 80 + "\n\n")
                
                for i, trader in enumerate(top_traders, 1):
                    address = trader['address']
                    pnl = trader['total_pnl']
                    position_value = trader['position_value']
                    pnl_percentage = trader['pnl_percentage']
                    
                    f.write(f"#{i}. {address}\n")
                    f.write(f"    持仓价值: ${position_value:,.0f}\n")
                    f.write(f"    总盈亏: ${pnl:,.0f}\n")
                    f.write(f"    盈利率: {pnl_percentage:.2f}%\n")
                    f.write(f"    查看: https://app.hyperliquid.xyz/user/{address}\n\n")
                
                # 统计信息
                total_position_value = sum(t['position_value'] for t in top_traders)
                total_pnl = sum(t['total_pnl'] for t in top_traders)
                avg_pnl_percentage = sum(t['pnl_percentage'] for t in top_traders) / len(top_traders)
                profitable_count = len([t for t in top_traders if t['total_pnl'] > 0])
                
                f.write("=" * 80 + "\n")
                f.write("统计摘要\n")
                f.write("=" * 80 + "\n")
                f.write(f"总计大户数量: {len(top_traders)}\n")
                f.write(f"总持仓价值: ${total_position_value:,.0f}\n")
                f.write(f"总盈亏: ${total_pnl:,.0f}\n")
                f.write(f"平均盈利率: {avg_pnl_percentage:.2f}%\n")
                f.write(f"盈利用户数: {profitable_count}/{len(top_traders)} ({profitable_count/len(top_traders)*100:.1f}%)\n")
            
            print(f"📊 TXT结果已保存到: {txt_filename}")
            
        except Exception as e:
            print(f"⚠️ 保存结果时出错: {e}")

def main():
    """主函数"""
    print("🚀 Hyperliquid 大户盈利分析器 - 轻量版")
    print("=" * 60)
    
    # 参数设置
    min_position_value = 5000000  # 500万美元
    top_count = 20  # 前20名
    
    print(f"⚙️ 分析参数:")
    print(f"   💰 最小持仓要求: ${min_position_value:,.0f}")
    print(f"   🏆 显示前: {top_count} 名")
    print(f"   📊 数据源: Hyperliquid API")
    
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