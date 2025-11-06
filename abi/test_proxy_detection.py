#!/usr/bin/env python3
"""
测试代理合约ABI获取功能
"""

from abi_fetcher import ABIFetcher

def test_proxy_detection():
    """测试代理合约检测功能"""
    
    fetcher = ABIFetcher()
    
    print("=" * 60)
    print("测试1: BSC上的USDT代理合约")
    print("=" * 60)
    
    # BSC USDT - 已知的代理合约
    bsc_usdt = "0x55d398326f99059fF775485246999027B3197955"
    
    # 检测是否是代理
    impl_address = fetcher.get_implementation_address("bsc", bsc_usdt)
    
    if impl_address:
        print(f"✅ 成功检测到代理合约")
        print(f"   代理地址: {bsc_usdt}")
        print(f"   实现地址: {impl_address}")
    else:
        print(f"❌ 未检测到代理或检测失败")
    
    print("\n" + "=" * 60)
    print("测试2: 获取完整的实现合约ABI")
    print("=" * 60)
    
    # 获取ABI（自动处理代理）
    abi = fetcher.fetch_contract_abi("bsc", bsc_usdt, check_proxy=True)
    
    if abi:
        print(f"✅ 成功获取ABI")
        print(f"   ABI包含 {len(abi)} 个项目")
        
        # 统计函数和事件
        functions = [item for item in abi if item.get('type') == 'function']
        events = [item for item in abi if item.get('type') == 'event']
        
        print(f"   函数数量: {len(functions)}")
        print(f"   事件数量: {len(events)}")
        
        # 显示一些函数名
        if functions:
            print(f"\n   示例函数:")
            for i, func in enumerate(functions[:5], 1):
                print(f"   {i}. {func.get('name', 'unnamed')}")
    else:
        print(f"❌ 获取ABI失败")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_proxy_detection()
