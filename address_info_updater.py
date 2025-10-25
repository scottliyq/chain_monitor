#!/usr/bin/env python3
"""
地址信息更新工具
通过Moralis API客户端查询地址信息，更新SQLite数据库中的现有数据
保持现有数据结构不变，只更新相关字段
"""

import sqlite3
import logging
import time
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('address_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AddressInfoUpdater:
    """地址信息更新器"""
    
    def __init__(self, db_file: str = "address_labels.db"):
        """初始化更新器
        
        Args:
            db_file: SQLite数据库文件路径
        """
        self.db_file = db_file
        
        # 初始化Moralis API客户端
        try:
            from moralis_api_client import MoralisAPIClient
            self.moralis_client = MoralisAPIClient()
            if self.moralis_client.is_api_available():
                logger.info("✅ Moralis API客户端初始化成功")
            else:
                logger.warning("⚠️ Moralis API不可用")
                self.moralis_client = None
        except ImportError:
            logger.error("❌ 无法导入MoralisAPIClient模块")
            self.moralis_client = None
        except Exception as e:
            logger.error(f"❌ Moralis客户端初始化失败: {e}")
            self.moralis_client = None
        
        # 统计信息
        self.stats = {
            'total_addresses': 0,
            'updated_addresses': 0,
            'failed_queries': 0,
            'skipped_addresses': 0
        }
    
    def get_all_addresses(self) -> List[Dict]:
        """获取数据库中的所有地址，优先返回Unknown Address记录
        
        Returns:
            地址信息列表
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, address, network, label, type, source, 
                           contract_name, is_verified, query_count
                    FROM address_labels
                    ORDER BY 
                        CASE WHEN label = 'Unknown Address' THEN 0 ELSE 1 END,
                        query_count ASC, 
                        updated_at ASC
                """)
                
                addresses = [dict(row) for row in cursor.fetchall()]
                unknown_count = len([addr for addr in addresses if addr['label'] == 'Unknown Address'])
                logger.info(f"📊 从数据库获取到 {len(addresses)} 个地址，其中 {unknown_count} 个Unknown Address")
                return addresses
                
        except Exception as e:
            logger.error(f"❌ 获取地址列表失败: {e}")
            return []
    
    def query_moralis_info(self, address: str, network: str) -> Optional[Dict]:
        """通过Moralis API查询地址信息
        
        Args:
            address: 地址
            network: 网络名称
            
        Returns:
            查询结果字典或None
        """
        if not self.moralis_client:
            return None
        
        try:
            result = self.moralis_client.query_address_info(address, network)
            if result:
                logger.debug(f"🔍 Moralis查询成功: {address[:10]}...{address[-8:]} -> {result.get('label', 'N/A')}")
                return result
            else:
                logger.debug(f"📭 Moralis无结果: {address[:10]}...{address[-8:]}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ Moralis查询异常 {address[:10]}...{address[-8:]}: {e}")
            return None
    
    def update_address_info(self, address_id: int, moralis_info: Dict) -> bool:
        """更新地址信息到数据库 - 更新label、type、source和contract_name字段
        
        Args:
            address_id: 地址记录ID
            moralis_info: Moralis查询结果
            
        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 准备更新数据
                label = moralis_info.get('label', 'Unknown Address')
                address_type = moralis_info.get('type', 'unknown')
                source = moralis_info.get('source', 'moralis')
                contract_name = moralis_info.get('contract_name', '')
                updated_at = datetime.now().isoformat()
                
                # 更新label、type、source和contract_name字段
                cursor.execute("""
                    UPDATE address_labels 
                    SET label = ?, type = ?, source = ?, contract_name = ?, 
                        query_count = query_count + 1, updated_at = ?
                    WHERE id = ?
                """, (label, address_type, source, contract_name, updated_at, address_id))
                
                if cursor.rowcount > 0:
                    logger.debug(f"✅ 更新成功 ID:{address_id} -> {label}")
                    return True
                else:
                    logger.warning(f"⚠️ 更新失败，未找到记录 ID:{address_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 数据库更新失败 ID:{address_id}: {e}")
            return False
    
    def should_update_address(self, address_info: Dict) -> bool:
        """判断是否需要更新地址信息 - 只更新Unknown Address
        
        Args:
            address_info: 地址信息字典
            
        Returns:
            是否需要更新
        """
        # 只更新标签为"Unknown Address"的记录
        return address_info.get('label') == 'Unknown Address'
    
    def update_all_addresses(self, max_updates: int = 50, delay_seconds: float = 1.0):
        """更新所有需要更新的地址信息
        
        Args:
            max_updates: 最大更新数量
            delay_seconds: 请求间隔秒数
        """
        logger.info("🚀 开始批量更新地址信息...")
        
        # 获取所有地址
        addresses = self.get_all_addresses()
        self.stats['total_addresses'] = len(addresses)
        
        if not addresses:
            logger.warning("⚠️ 数据库中没有地址数据")
            return
        
        if not self.moralis_client:
            logger.error("❌ Moralis客户端不可用，无法进行更新")
            return
        
        update_count = 0
        
        for addr_info in addresses:
            if update_count >= max_updates:
                logger.info(f"🛑 达到最大更新数量限制: {max_updates}")
                break
            
            # 判断是否需要更新
            if not self.should_update_address(addr_info):
                self.stats['skipped_addresses'] += 1
                logger.debug(f"⏭️ 跳过地址: {addr_info['address'][:10]}...{addr_info['address'][-8:]} (标签: {addr_info['label']})")
                continue
            
            address = addr_info['address']
            network = addr_info['network']
            
            logger.info(f"🔍 更新地址 ({update_count + 1}/{max_updates}): {address[:10]}...{address[-8:]} ({network})")
            
            # 查询Moralis API
            moralis_info = self.query_moralis_info(address, network)
            
            if moralis_info:
                # 更新数据库
                if self.update_address_info(addr_info['id'], moralis_info):
                    self.stats['updated_addresses'] += 1
                    update_count += 1
                    logger.info(f"✅ 更新成功: {address[:10]}...{address[-8:]} -> {moralis_info.get('label', 'N/A')}")
                else:
                    self.stats['failed_queries'] += 1
                    logger.error(f"❌ 数据库更新失败: {address[:10]}...{address[-8:]}")
            else:
                self.stats['failed_queries'] += 1
                logger.info(f"📭 无新信息: {address[:10]}...{address[-8:]}")
            
            # 添加延迟避免API限制
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        
        self.print_summary()
    
    def update_unknown_addresses(self, max_updates: int = 100, delay_seconds: float = 1.0):
        """专门更新所有Unknown Address记录
        
        Args:
            max_updates: 最大更新数量
            delay_seconds: 请求间隔秒数
        """
        logger.info("🎯 开始更新所有Unknown Address记录...")
        
        if not self.moralis_client:
            logger.error("❌ Moralis客户端不可用，无法进行更新")
            return
        
        # 获取所有Unknown Address记录
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, address, network, label, type, source, 
                           contract_name, is_verified, query_count
                    FROM address_labels
                    WHERE label = 'Unknown Address'
                    ORDER BY query_count ASC, updated_at ASC
                """)
                
                unknown_addresses = [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"❌ 获取Unknown Address记录失败: {e}")
            return
        
        self.stats['total_addresses'] = len(unknown_addresses)
        
        if not unknown_addresses:
            logger.info("✅ 没有需要更新的Unknown Address记录")
            return
        
        logger.info(f"📍 找到 {len(unknown_addresses)} 个Unknown Address记录")
        
        update_count = 0
        
        for addr_info in unknown_addresses:
            if update_count >= max_updates:
                logger.info(f"🛑 达到最大更新数量限制: {max_updates}")
                break
            
            address = addr_info['address']
            network = addr_info['network']
            
            logger.info(f"🔍 更新Unknown Address ({update_count + 1}/{min(max_updates, len(unknown_addresses))}): {address[:10]}...{address[-8:]} ({network})")
            
            # 查询Moralis API
            moralis_info = self.query_moralis_info(address, network)
            
            if moralis_info:
                # 更新数据库 (更新label、type、source和contract_name字段)
                if self.update_address_info(addr_info['id'], moralis_info):
                    self.stats['updated_addresses'] += 1
                    update_count += 1
                    logger.info(f"✅ 更新成功: {address[:10]}...{address[-8:]} -> {moralis_info.get('label', 'N/A')}")
                else:
                    self.stats['failed_queries'] += 1
                    logger.error(f"❌ 数据库更新失败: {address[:10]}...{address[-8:]}")
            else:
                self.stats['failed_queries'] += 1
                logger.info(f"📭 仍为Unknown: {address[:10]}...{address[-8:]}")
            
            # 添加延迟避免API限制
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        
        self.print_summary()
    
    def update_specific_addresses(self, addresses: List[str], network: str = 'ethereum', delay_seconds: float = 1.0):
        """更新指定的地址列表
        
        Args:
            addresses: 地址列表
            network: 网络名称
            delay_seconds: 请求间隔秒数
        """
        logger.info(f"🎯 开始更新指定地址列表 ({len(addresses)} 个地址)")
        
        if not self.moralis_client:
            logger.error("❌ Moralis客户端不可用，无法进行更新")
            return
        
        for i, address in enumerate(addresses, 1):
            logger.info(f"🔍 更新地址 ({i}/{len(addresses)}): {address[:10]}...{address[-8:]} ({network})")
            
            # 查找数据库中的记录
            try:
                with sqlite3.connect(self.db_file) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, label FROM address_labels WHERE address = ? AND network = ?",
                        (address, network)
                    )
                    record = cursor.fetchone()
                    
                    if not record:
                        logger.warning(f"⚠️ 数据库中未找到地址: {address}")
                        continue
                    
                    # 查询Moralis API
                    moralis_info = self.query_moralis_info(address, network)
                    
                    if moralis_info:
                        # 更新数据库
                        if self.update_address_info(record['id'], moralis_info):
                            self.stats['updated_addresses'] += 1
                            logger.info(f"✅ 更新成功: {address[:10]}...{address[-8:]} -> {moralis_info.get('label', 'N/A')}")
                        else:
                            self.stats['failed_queries'] += 1
                    else:
                        self.stats['failed_queries'] += 1
                        logger.info(f"📭 无新信息: {address[:10]}...{address[-8:]}")
                    
            except Exception as e:
                logger.error(f"❌ 处理地址失败 {address}: {e}")
                self.stats['failed_queries'] += 1
            
            # 添加延迟
            if delay_seconds > 0 and i < len(addresses):
                time.sleep(delay_seconds)
        
        self.print_summary()
    
    def print_summary(self):
        """打印更新统计摘要"""
        logger.info("📊 更新完成统计:")
        logger.info(f"   总地址数: {self.stats['total_addresses']}")
        logger.info(f"   已更新: {self.stats['updated_addresses']}")
        logger.info(f"   查询失败: {self.stats['failed_queries']}")
        logger.info(f"   跳过数量: {self.stats['skipped_addresses']}")
        
        if self.stats['total_addresses'] > 0:
            success_rate = (self.stats['updated_addresses'] / 
                          max(1, self.stats['updated_addresses'] + self.stats['failed_queries'])) * 100
            logger.info(f"   成功率: {success_rate:.1f}%")


def main():
    """主函数 - 演示用法"""
    updater = AddressInfoUpdater()
    
    logger.info("🔧 地址信息更新工具")
    logger.info("=" * 50)
    
    # 示例1: 专门更新所有Unknown Address记录
    updater.update_unknown_addresses(max_updates=10, delay_seconds=1.0)
    
    # 示例2: 更新指定地址 (如果需要)
    # test_addresses = [
    #     "0xc7bbec68d12a0d1830360f8ec58fa599ba1b0e9b",  # 已知的Uniswap池子
    #     "0x48da0965ab2d2cbf1c17c09cfb5cbe67ad5b1406"   # 数据库中的地址
    # ]
    # updater.update_specific_addresses(test_addresses, network='ethereum', delay_seconds=1.0)


if __name__ == "__main__":
    main()