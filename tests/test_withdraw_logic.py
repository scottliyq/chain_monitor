#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试取款逻辑的各种场景
"""
import math

def test_withdraw_logic(max_withdraw: float, config_amount: float):
    """
    测试取款逻辑
    
    Args:
        max_withdraw: 最大可取出金额
        config_amount: 配置的取出金额
    """
    print(f"\n{'='*70}")
    print(f"测试场景: 最大可取={max_withdraw}, 配置金额={config_amount}")
    print(f"{'='*70}")
    
    twenty_percent_of_config = config_amount * 0.2
    print(f"配置金额的20% = {twenty_percent_of_config}")
    
    # 情况1: 剩余可取金额 < 配置金额的20% -> 跳过
    if max_withdraw < twenty_percent_of_config:
        print(f"❌ 情况1: 剩余可取 ({max_withdraw}) < 配置20% ({twenty_percent_of_config})")
        print(f"   结果: 跳过取款")
        return None
    
    # 情况2: 配置金额的20% <= 剩余可取金额 < 配置金额 -> 取出int(剩余金额)，但最小为1
    if twenty_percent_of_config <= max_withdraw < config_amount:
        int_amount = int(max_withdraw)
        
        if int_amount < 1:
            print(f"⚠️ 情况2: 配置20% ({twenty_percent_of_config}) <= 剩余可取 ({max_withdraw}) < 配置金额 ({config_amount})")
            print(f"   但 int({max_withdraw}) = {int_amount} < 1，不满足最小取出金额")
            print(f"   结果: 跳过取款")
            return None
        
        actual_amount = int_amount
        print(f"📌 情况2: 配置20% ({twenty_percent_of_config}) <= 剩余可取 ({max_withdraw}) < 配置金额 ({config_amount})")
        print(f"   结果: 取出 int({max_withdraw}) = {actual_amount}")
        return actual_amount
    
    # 情况3: 剩余可取金额 >= 配置金额 -> 正常计算
    print(f"🎉 情况3: 剩余可取 ({max_withdraw}) >= 配置金额 ({config_amount})")
    
    twenty_percent_of_max = max_withdraw * 0.2
    print(f"   最大可取的20% = {twenty_percent_of_max}")
    
    desired_amount = max(twenty_percent_of_max, config_amount)
    print(f"   期望取出 = max({twenty_percent_of_max}, {config_amount}) = {desired_amount}")
    
    if desired_amount > max_withdraw:
        actual_amount = max_withdraw
        print(f"   ⚠️ 期望金额超过最大可取，使用最大可取")
    else:
        actual_amount = desired_amount
    
    print(f"   结果: 取出 {actual_amount}")
    return actual_amount


if __name__ == "__main__":
    print("取款逻辑测试")
    print("="*70)
    
    # 测试场景
    test_cases = [
        # (最大可取, 配置金额)
        (0.5, 10),      # < 20% -> 跳过
        (1.5, 10),      # = 15% -> 跳过
        (2.0, 10),      # = 20% -> 取int(2)=2
        (3.5, 10),      # = 35% -> 取int(3)=3
        (8.7, 10),      # = 87% -> 取int(8)=8
        (9.9, 10),      # = 99% -> 取int(9)=9
        (10, 10),       # = 100% -> 正常逻辑，取max(2, 10)=10
        (15, 10),       # = 150% -> 正常逻辑，取max(3, 10)=10
        (50, 10),       # = 500% -> 正常逻辑，取max(10, 10)=10
        (100, 10),      # = 1000% -> 正常逻辑，取max(20, 10)=20
        
        # 配置金额=1的场景
        (0.1, 1),       # < 20% -> 跳过
        (0.2, 1),       # = 20% -> 取int(0)=0
        (0.5, 1),       # = 50% -> 取int(0)=0
        (0.99, 1),      # = 99% -> 取int(0)=0
        (1.0, 1),       # = 100% -> 正常逻辑，取max(0.2, 1)=1
        (5.0, 1),       # = 500% -> 正常逻辑，取max(1, 1)=1
        (10.0, 1),      # = 1000% -> 正常逻辑，取max(2, 1)=2
    ]
    
    for max_withdraw, config_amount in test_cases:
        result = test_withdraw_logic(max_withdraw, config_amount)
        if result is not None:
            percentage = (result / config_amount) * 100
            print(f"   💰 实际取出占配置金额的 {percentage:.1f}%")
