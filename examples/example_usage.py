#!/usr/bin/env python3
"""
历史代币余额查询工具使用示例
演示单地址查询和批量查询功能
"""

import sys
import os
from datetime import datetime, timedelta

from _path_setup import ensure_src_path

ensure_src_path()

from historical_token_balance_checker import HistoricalTokenBalanceChecker, setup_logging

def example_single_address_query():
    """示例：单地址查询"""
    print("🔍 示例1: 单地址查询")
    print("=" * 50)
    
    # 设置日志
    logger = setup_logging()
    
    try:
        # 配置参数
        target_time = "2024-01-01 12:00:00"
        token = "USDT"
        network = "ethereum"
        address_to_check = "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT合约地址作为示例
        
        logger.info(f"查询参数:")
        logger.info(f"  时间: {target_time}")
        logger.info(f"  代币: {token}")
        logger.info(f"  网络: {network}")
        logger.info(f"  地址: {address_to_check}")
        
        # 创建查询器
        checker = HistoricalTokenBalanceChecker(
            target_time=target_time,
            token=token,
            network=network,
            address_to_check=address_to_check
        )
        
        # 执行单地址查询
        result = checker.run(mode='single')
        
        logger.info(f"✅ 查询结果:")
        logger.info(f"  地址: {result['address']}")
        logger.info(f"  余额: {result['balance_tokens']} {result['token']}")
        logger.info(f"  区块号: {result['block_number']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 单地址查询示例失败: {e}")
        return None

def example_batch_query():
    """示例：批量查询大户"""
    print("\n🏆 示例2: 批量查询大户")
    print("=" * 50)
    
    # 设置日志
    logger = setup_logging()
    
    try:
        # 配置参数
        target_time = "2024-01-01 12:00:00"
        token = "USDT"
        network = "ethereum"
        min_balance = 1000000.0  # 100万USDT
        max_addresses = 10  # 最多返回10个地址
        
        logger.info(f"查询参数:")
        logger.info(f"  时间: {target_time}")
        logger.info(f"  代币: {token}")
        logger.info(f"  网络: {network}")
        logger.info(f"  最小余额: {min_balance:,.0f} {token}")
        logger.info(f"  最大地址数: {max_addresses}")
        
        # 创建查询器（批量模式不需要指定地址）
        checker = HistoricalTokenBalanceChecker(
            target_time=target_time,
            token=token,
            network=network,
            address_to_check=None
        )
        
        # 执行批量查询
        results = checker.run(
            mode='batch',
            min_balance=min_balance,
            max_addresses=max_addresses
        )
        
        if results:
            logger.info(f"✅ 查询结果:")
            logger.info(f"  符合条件地址数: {len(results)}")
            logger.info(f"  前5名大户:")
            
            for i, result in enumerate(results[:5], 1):
                logger.info(f"    {i}. {result['address'][:10]}...{result['address'][-8:]} - {result['balance_tokens']:,.2f} {token}")
        else:
            logger.info("📭 未找到符合条件的地址")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ 批量查询示例失败: {e}")
        return None

def main():
    """主函数"""
    print("🚀 历史代币余额查询工具使用示例")
    print("=" * 60)
    
    # 注意：这些示例需要有效的RPC URL和API密钥才能运行
    print("⚠️  注意：运行示例需要配置以下环境变量:")
    print("   ETHEREUM_RPC_URL - 以太坊RPC节点URL")
    print("   ETHERSCAN_API_KEY - Etherscan API密钥")
    print("")
    
    # 检查环境变量
    if not os.getenv('ETHEREUM_RPC_URL'):
        print("❌ 未设置 ETHEREUM_RPC_URL 环境变量")
        print("   示例将无法实际执行，仅展示用法")
        return
    
    if not os.getenv('ETHERSCAN_API_KEY'):
        print("❌ 未设置 ETHERSCAN_API_KEY 环境变量")
        print("   示例将无法实际执行，仅展示用法")
        return
    
    try:
        # 运行示例
        # example_single_address_query()
        # example_batch_query()
        
        print("💡 命令行使用方法:")
        print("单地址查询:")
        print("  python src/historical_token_balance_checker.py \\")
        print("    --time '2024-01-01 12:00:00' \\")
        print("    --token USDT \\")
        print("    --network ethereum \\")
        print("    --mode single \\")
        print("    --address 0xdAC17F958D2ee523a2206206994597C13D831ec7")
        print("")
        print("批量查询:")
        print("  python src/historical_token_balance_checker.py \\")
        print("    --time '2024-01-01 12:00:00' \\")
        print("    --token USDT \\")
        print("    --network ethereum \\")
        print("    --mode batch \\")
        print("    --min-balance 1000000 \\")
        print("    --max-addresses 50")
        
    except KeyboardInterrupt:
        print("\n🛑 示例被用户中断")
    except Exception as e:
        print(f"❌ 示例运行失败: {e}")

if __name__ == "__main__":
    main()
