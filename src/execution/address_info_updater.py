#!/usr/bin/env python3
"""
地址信息更新工具
通过Moralis API客户端查询地址信息，更新SQLite数据库中的现有数据
保持现有数据结构不变，只更新相关字段
只处理合约地址，检测到EOA地址时删除数据库记录
"""

import sqlite3
import logging
import time
import os
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime
from web3 import Web3
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

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
        
        # 初始化Web3连接用于地址类型检测
        self.web3 = self._init_web3()
        
        # 初始化Moralis API客户端
        try:
            from core.moralis_api_client import MoralisAPIClient
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
            'deleted_eoa_addresses': 0,
            'failed_queries': 0,
            'skipped_addresses': 0
        }
    
    def _init_web3(self) -> Optional[Web3]:
        """初始化Web3连接"""
        try:
            # 尝试从环境变量获取RPC URL
            rpc_url = (os.getenv('WEB3_RPC_URL') or 
                      os.getenv('ETHEREUM_RPC_URL') or 
                      "https://eth.llamarpc.com")  # 默认RPC
            
            provider = Web3.HTTPProvider(
                rpc_url,
                request_kwargs={'timeout': 30}
            )
            web3 = Web3(provider)
            
            # 验证连接
            chain_id = web3.eth.chain_id
            logger.info(f"✅ Web3连接成功 (Chain ID: {chain_id})")
            return web3
            
        except Exception as e:
            logger.warning(f"⚠️ Web3连接失败: {e}")
            logger.warning("⚠️ 无法检测地址类型，将跳过EOA检测功能")
            return None
    
    def is_contract_address(self, address: str) -> tuple[bool, str]:
        """检查地址是否为合约地址
        
        Args:
            address: 要检查的地址
            
        Returns:
            tuple: (is_contract: bool, address_type: str)
        """
        if not self.web3:
            return False, "Unknown"
        
        try:
            # 转换为checksum地址
            checksum_address = self.web3.to_checksum_address(address)
            code = self.web3.eth.get_code(checksum_address)
            is_contract = len(code) > 2  # 不只是'0x'
            address_type = "Contract" if is_contract else "EOA"
            return is_contract, address_type
        except Exception as e:
            logger.error(f"⚠️ 检查合约地址失败 {address}: {e}")
            return False, "Unknown"
    
    def delete_eoa_address(self, address_id: int, address: str) -> bool:
        """删除EOA地址记录（只删除已标记为EOA的地址）
        
        Args:
            address_id: 地址记录ID
            address: 地址字符串（用于日志）
            
        Returns:
            是否删除成功
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 只删除已标记为EOA的地址记录
                cursor.execute("DELETE FROM address_labels WHERE id = ? AND is_eoa = 1", (address_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"🗑️ 已删除EOA地址: {address[:10]}...{address[-8:]}")
                    return True
                else:
                    # 检查记录是否存在但不是EOA
                    cursor.execute("SELECT is_eoa FROM address_labels WHERE id = ?", (address_id,))
                    result = cursor.fetchone()
                    if result:
                        is_eoa = result[0]
                        if not is_eoa:
                            logger.warning(f"⚠️ 地址未标记为EOA，跳过删除: {address[:10]}...{address[-8:]} (is_eoa: {is_eoa})")
                        else:
                            logger.warning(f"⚠️ 删除失败，记录状态异常 ID:{address_id}")
                    else:
                        logger.warning(f"⚠️ 删除失败，未找到记录 ID:{address_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 删除地址记录失败 {address}: {e}")
            return False
    
    def get_all_addresses(self) -> List[Dict]:
        """获取数据库中需要更新的地址（只查询Unknown Address记录）
        
        Returns:
            地址信息列表
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 只查询label为'Unknown Address'的记录
                cursor.execute("""
                    SELECT id, address, network, label, type, source, 
                           contract_name, is_verified, query_count
                    FROM address_labels
                    WHERE label = 'Unknown Address'
                    ORDER BY query_count ASC, updated_at ASC
                """)
                
                addresses = [dict(row) for row in cursor.fetchall()]
                logger.info(f"📊 从数据库获取到 {len(addresses)} 个Unknown Address需要更新")
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
    
    def update_address_info(self, address_id: int, address: str, network: str = 'ethereum') -> bool:
        """更新地址信息到数据库 - 新逻辑：保存有外部数据的EOA，删除无外部数据的EOA
        
        Args:
            address_id: 地址记录ID
            address: 地址字符串
            network: 网络名称
            
        Returns:
            是否更新成功
        """
        try:
            # 1. 检查地址类型
            is_contract, address_type = self.is_contract_address(address)
            
            # 2. 查询外部API获取地址信息
            moralis_info = self.query_moralis_info(address, network)
            
            # 3. 根据不同情况进行处理
            if moralis_info and moralis_info.get('label'):
                # 情况1: 外部API返回了有效信息
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    
                    # 准备更新数据
                    label = moralis_info.get('label', 'Unknown Address')
                    contract_type = moralis_info.get('type', 'eoa' if not is_contract else 'contract')
                    source = moralis_info.get('source', 'moralis')
                    contract_name = moralis_info.get('contract_name', '')
                    is_eoa = not is_contract
                    updated_at = datetime.now().isoformat()
                    
                    # 更新记录，包括is_eoa字段
                    cursor.execute("""
                        UPDATE address_labels 
                        SET label = ?, type = ?, source = ?, contract_name = ?, 
                            is_eoa = ?, query_count = query_count + 1, updated_at = ?
                        WHERE id = ?
                    """, (label, contract_type, source, contract_name, is_eoa, updated_at, address_id))
                    
                    if cursor.rowcount > 0:
                        address_type_str = "EOA" if is_eoa else "合约"
                        logger.info(f"✅ 更新成功({address_type_str}): {address[:10]}...{address[-8:]} -> {label}")
                        return True
                    else:
                        logger.warning(f"⚠️ 更新失败，未找到记录 ID:{address_id}")
                        return False
            else:
                # 情况2: 外部API没有返回有效信息
                if not is_contract and address_type == "EOA":
                    # EOA地址且无外部信息 -> 先标记为EOA，然后删除记录
                    logger.info(f"🗑️ 删除无信息的EOA地址: {address[:10]}...{address[-8:]}")
                    
                    # 先标记为EOA
                    try:
                        with sqlite3.connect(self.db_file) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE address_labels SET is_eoa = 1, updated_at = ? WHERE id = ?",
                                (datetime.now().isoformat(), address_id)
                            )
                            conn.commit()
                    except Exception as e:
                        logger.error(f"   ❌ 标记EOA失败: {e}")
                    
                    # 然后删除
                    return self.delete_eoa_address(address_id, address)
                else:
                    # 合约地址但无外部信息 -> 保持原样
                    logger.info(f"📭 合约地址无新信息: {address[:10]}...{address[-8:]}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ 更新地址信息失败 {address}: {e}")
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
            
            # 更新地址信息（在方法内部查询Moralis API）
            if self.update_address_info(addr_info['id'], address, network):
                self.stats['updated_addresses'] += 1
                update_count += 1
            
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
            
            # 更新地址信息（在方法内部查询Moralis API）
            if self.update_address_info(addr_info['id'], address, network):
                self.stats['updated_addresses'] += 1
                update_count += 1
            
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
                    
                    # 更新地址信息（在方法内部查询Moralis API）
                    if self.update_address_info(record['id'], address, network):
                        self.stats['updated_addresses'] += 1
                    else:
                        self.stats['failed_queries'] += 1
                    
            except Exception as e:
                logger.error(f"❌ 处理地址失败 {address}: {e}")
                self.stats['failed_queries'] += 1
            
            # 添加延迟
            if delay_seconds > 0 and i < len(addresses):
                time.sleep(delay_seconds)
        
        self.print_summary()
    
    def cleanup_eoa_addresses(self, max_checks: int = 500, delay_seconds: float = 0.1):
        """专门清理数据库中的EOA地址记录（只处理Unknown Address）
        
        Args:
            max_checks: 最大检查数量
            delay_seconds: 检查间隔秒数
        """
        logger.info("🧹 开始清理数据库中的EOA地址...")
        
        if not self.web3:
            logger.error("❌ Web3连接不可用，无法进行EOA检测")
            return
        
        # 只获取label为'Unknown Address'的记录进行检查
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, address, network, label, type
                    FROM address_labels
                    WHERE label = 'Unknown Address'
                    ORDER BY updated_at ASC
                    LIMIT ?
                """, (max_checks,))
                
                all_addresses = [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"❌ 获取地址记录失败: {e}")
            return
        
        self.stats['total_addresses'] = len(all_addresses)
        
        if not all_addresses:
            logger.info("✅ 没有Unknown Address需要检查")
            return
        
        logger.info(f"📍 找到 {len(all_addresses)} 个Unknown Address需要检查")
        
        check_count = 0
        
        for addr_info in all_addresses:
            if check_count >= max_checks:
                logger.info(f"🛑 达到最大检查数量限制: {max_checks}")
                break
            
            address = addr_info['address']
            
            logger.info(f"🔍 检查地址 ({check_count + 1}/{min(max_checks, len(all_addresses))}): {address[:10]}...{address[-8:]}")
            
            # 检查地址类型
            is_contract, address_type = self.is_contract_address(address)
            
            if not is_contract and address_type == "EOA":
                # 先标记为EOA，然后删除
                logger.info(f"🗑️ 发现EOA地址，先标记再删除: {address[:10]}...{address[-8:]}")
                
                # 标记为EOA
                try:
                    with sqlite3.connect(self.db_file) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE address_labels SET is_eoa = 1, updated_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), addr_info['id'])
                        )
                        conn.commit()
                        
                        if cursor.rowcount > 0:
                            logger.debug(f"   ✅ 已标记为EOA: {address[:10]}...{address[-8:]}")
                        else:
                            logger.warning(f"   ⚠️ 标记EOA失败: {address[:10]}...{address[-8:]}")
                            
                except Exception as e:
                    logger.error(f"   ❌ 标记EOA失败: {e}")
                
                # 删除EOA记录(只删除已标记的EOA)
                if self.delete_eoa_address(addr_info['id'], address):
                    self.stats['deleted_eoa_addresses'] += 1
                else:
                    self.stats['failed_queries'] += 1
            elif is_contract and address_type == "Contract":
                logger.debug(f"✅ 确认为合约地址: {address[:10]}...{address[-8:]}")
            else:
                logger.debug(f"❓ 地址类型未知: {address[:10]}...{address[-8:]} ({address_type})")
            
            check_count += 1
            
            # 添加延迟避免RPC限制
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        
        self.print_summary()
    
    def print_summary(self):
        """打印更新统计摘要"""
        logger.info("📊 更新完成统计:")
        logger.info(f"   总地址数: {self.stats['total_addresses']}")
        logger.info(f"   已更新合约: {self.stats['updated_addresses']}")
        logger.info(f"   已删除EOA: {self.stats['deleted_eoa_addresses']}")
        logger.info(f"   查询失败: {self.stats['failed_queries']}")
        logger.info(f"   跳过数量: {self.stats['skipped_addresses']}")
        
        if self.stats['total_addresses'] > 0:
            successful_operations = self.stats['updated_addresses'] + self.stats['deleted_eoa_addresses']
            total_operations = successful_operations + self.stats['failed_queries']
            success_rate = (successful_operations / max(1, total_operations)) * 100
            logger.info(f"   成功率: {success_rate:.1f}%")
            
            if self.stats['deleted_eoa_addresses'] > 0:
                eoa_ratio = (self.stats['deleted_eoa_addresses'] / max(1, self.stats['total_addresses'])) * 100
                logger.info(f"   EOA地址占比: {eoa_ratio:.1f}%")


def main():
    """主函数 - 演示用法"""
    updater = AddressInfoUpdater()
    
    logger.info("🔧 地址信息更新工具 (v2.0 - 只处理合约地址)")
    logger.info("=" * 60)
    
    # 示例1: 专门清理EOA地址记录
    logger.info("🧹 步骤1: 清理数据库中的EOA地址")
    updater.cleanup_eoa_addresses(max_checks=100, delay_seconds=0.1)
    
    # 重置统计
    updater.stats = {
        'total_addresses': 0,
        'updated_addresses': 0,
        'deleted_eoa_addresses': 0,
        'failed_queries': 0,
        'skipped_addresses': 0
    }
    
    # 示例2: 专门更新所有Unknown Address记录（只更新合约地址）
    logger.info("\n📝 步骤2: 更新Unknown Address记录")
    updater.update_unknown_addresses(max_updates=10, delay_seconds=1.0)
    
    # 示例3: 更新指定地址 (如果需要)
    # test_addresses = [
    #     "0xc7bbec68d12a0d1830360f8ec58fa599ba1b0e9b",  # 已知的Uniswap池子
    #     "0x48da0965ab2d2cbf1c17c09cfb5cbe67ad5b1406"   # 数据库中的地址
    # ]
    # logger.info("\n🎯 步骤3: 更新指定地址")
    # updater.update_specific_addresses(test_addresses, network='ethereum', delay_seconds=1.0)
    
    logger.info("\n✅ 地址信息更新完成！")
    logger.info("💡 提示: 只有合约地址会被更新，EOA地址会被自动删除")


if __name__ == "__main__":
    main()
