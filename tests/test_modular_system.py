#!/usr/bin/env python3
"""
测试模块化地址查询系统
"""

from _path_setup import ensure_src_path

ensure_src_path()

from sqlite_address_querier import SQLiteAddressLabelQuerier

def test_modular_system():
    """测试模块化后的系统"""
    print("🧪 测试模块化地址查询系统...")
    
    # 初始化查询器
    querier = SQLiteAddressLabelQuerier()
    
    # 测试地址
    test_address = "0xc7bbec68d12a0d1830360f8ec58fa599ba1b0e9b"
    
    print(f"\n📍 测试地址: {test_address}")
    
    # 查询地址标签
    result = querier.get_address_label(test_address, network="ethereum")
    
    if result:
        print(f"✅ 查询成功:")
        print(f"   标签: {result}")
    else:
        print("❌ 查询失败")
    
    # 显示统计信息
    stats = querier.query_stats
    print(f"\n📊 查询统计:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # 检查Moralis客户端状态
    if querier.moralis_client:
        print(f"\n🔧 Moralis客户端状态: ✅ 已加载")
        print(f"   API可用性: {'✅ 可用' if querier.moralis_client.is_api_available() else '❌ 不可用'}")
    else:
        print(f"\n🔧 Moralis客户端状态: ❌ 未加载")

if __name__ == "__main__":
    test_modular_system()
