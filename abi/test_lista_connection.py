#!/usr/bin/env python3
"""
Lista Withdraw工具 - 快速测试脚本
仅测试连接和ABI加载，不执行实际交易
"""

from lista_withdraw import ListaWithdraw
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_connection():
    """测试连接和基本功能"""
    try:
        logger.info("🧪 开始测试...")
        logger.info("=" * 60)
        
        # 创建实例（会测试连接、加载ABI、检查余额）
        lista = ListaWithdraw()
        
        # 获取合约信息
        lista.get_contract_info()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试通过!")
        logger.info("=" * 60)
        logger.info("💡 准备好执行withdraw操作")
        logger.info("   运行: python lista_withdraw.py")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"详细错误:\n{traceback.format_exc()}")

if __name__ == "__main__":
    test_connection()
