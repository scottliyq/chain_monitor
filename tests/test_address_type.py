#!/usr/bin/env python3
"""
测试地址类型判断功能
"""

from _path_setup import ensure_src_path

ensure_src_path()

from usdt_deposit_analyzer import TokenDepositAnalyzer

def test_address_type_detection():
    """测试地址类型检测功能"""
    print("🧪 测试地址类型检测功能...")
    
    # 创建分析器实例
    analyzer = TokenDepositAnalyzer(
        start_time="2024-10-24 00:00:00",
        end_time="2024-10-24 00:01:00",
        min_amount=1000,
        network="ethereum",
        token="USDT"
    )
    
    # 测试几个已知地址
    test_addresses = [
        ('0xdAC17F958D2ee523a2206206994597C13D831ec7', 'USDT合约'),  # USDT合约
        ('0x28C6c06298d514Db089934071355E5743bf21d60', 'Binance热钱包'),  # Binance
        ('0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2', 'Aave V3池'),  # Aave V3
        ('0x00000000219ab540356cBB839Cbe05303d7705Fa', 'ETH2存款合约'),  # ETH2 Deposit Contract
    ]
    
    print("\n📋 地址类型检测结果:")
    print("-" * 80)
    
    for address, description in test_addresses:
        try:
            is_contract, addr_type = analyzer.is_contract_address(address)
            contract_icon = "📄" if is_contract else "👤"
            type_name = "合约地址" if is_contract else "外部账户"
            
            print(f"{contract_icon} {description}")
            print(f"   地址: {address}")
            print(f"   类型: {type_name} ({addr_type})")
            print()
            
        except Exception as e:
            print(f"❌ {description}: 检查失败 - {e}")
            print()
    
    print("✅ 地址类型检测测试完成")

if __name__ == "__main__":
    test_address_type_detection()
