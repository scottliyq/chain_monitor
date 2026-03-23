#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyperliquid SDK 测试脚本
快速测试 SDK 是否可用以及 API 调用
"""

import json
from typing import Dict, Any

# 尝试导入 SDK
try:
    import hyperliquid
    print(f"✅ 成功导入 hyperliquid SDK")
    
    # 检查可用的类和方法
    print(f"📋 SDK 模块属性: {[attr for attr in dir(hyperliquid) if not attr.startswith('_')]}")
    
    # 尝试创建客户端
    if hasattr(hyperliquid, 'Info'):
        info_client = hyperliquid.Info()
        print(f"✅ 成功创建 Info 客户端")
        print(f"📋 Info 客户端方法: {[method for method in dir(info_client) if not method.startswith('_')]}")
        
        # 测试基本调用
        try:
            mids = info_client.all_mids()
            print(f"✅ all_mids() 调用成功，返回 {len(mids)} 项")
            
            # 显示前几个价格
            if isinstance(mids, dict):
                items = list(mids.items())[:5]
                print(f"📊 价格样本: {items}")
        except Exception as e:
            print(f"⚠️ all_mids() 调用失败: {e}")
        
        try:
            leaderboard = info_client.leaderboard("pnl")
            print(f"✅ leaderboard() 调用成功，返回 {len(leaderboard)} 项")
            
            # 显示前几个用户
            if isinstance(leaderboard, list) and len(leaderboard) > 0:
                first_user = leaderboard[0]
                print(f"📊 排行榜样本: {first_user}")
        except Exception as e:
            print(f"⚠️ leaderboard() 调用失败: {e}")
            
        # 如果有用户地址，测试获取用户状态
        try:
            if isinstance(leaderboard, list) and len(leaderboard) > 0:
                test_user = leaderboard[0].get('user') or leaderboard[0].get('address')
                if test_user:
                    print(f"🔍 测试用户状态查询: {test_user}")
                    user_state = info_client.clearinghouse_state(test_user)
                    if user_state:
                        print(f"✅ clearinghouse_state() 调用成功")
                        print(f"📊 用户状态字段: {list(user_state.keys())}")
                    else:
                        print(f"⚠️ clearinghouse_state() 返回空结果")
        except Exception as e:
            print(f"⚠️ clearinghouse_state() 调用失败: {e}")
    
    else:
        print(f"⚠️ SDK 中没有找到 Info 类")
        
except ImportError as e:
    print(f"❌ 无法导入 hyperliquid SDK: {e}")
except Exception as e:
    print(f"❌ SDK 测试出错: {e}")