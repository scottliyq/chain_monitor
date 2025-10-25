#!/usr/bin/env python3
"""
地址标签查询工具 - SQLite版本
查询顺序：本地常量 -> SQLite缓存 -> 外部API -> 更新SQLite
支持多网络地址查询，Unknown结果不保存
"""

import json
import re
import time
import os
import sqlite3
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# 导入本地地址常量
try:
    from address_constants import get_address_info, is_known_address, ALL_KNOWN_ADDRESSES
    HAS_CONSTANTS = True
except ImportError:
    print("⚠️ 未找到 address_constants.py，将使用内置标签")
    HAS_CONSTANTS = False

# 导入requests (如果可用)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    print("⚠️ 未安装 requests 库，外部查询功能将被禁用")
    HAS_REQUESTS = False

class SQLiteAddressLabelQuerier:
    """SQLite地址标签查询器 - 支持多网络查询"""
    
    def __init__(self, db_file='address_labels.db'):
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.db_file = db_file
        
        # 初始化SQLite数据库
        self.init_database()
        
        # 初始化请求会话
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
        else:
            self.session = None
            print("⚠️ requests库未安装，外部查询功能禁用")
        
        # 统计计数器
        self.query_stats = {
            'constants_hits': 0,
            'sqlite_hits': 0,
            'api_queries': 0,
            'sqlite_updates': 0,
            'total_queries': 0
        }
        
        # 网络配置
        self.network_configs = {
            'ethereum': {
                'name': 'Ethereum Mainnet',
                'chain_id': 1,
                'api_base': 'https://api.etherscan.io/api',
                'native_token': 'ETH'
            },
            'polygon': {
                'name': 'Polygon',
                'chain_id': 137,
                'api_base': 'https://api.polygonscan.com/api',
                'native_token': 'MATIC'
            },
            'bsc': {
                'name': 'Binance Smart Chain',
                'chain_id': 56,
                'api_base': 'https://api.bscscan.com/api',
                'native_token': 'BNB'
            }
        }
    
    def init_database(self):
        """初始化SQLite数据库"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row  # 允许通过列名访问
            
            # 创建地址标签表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS address_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    label TEXT NOT NULL,
                    type TEXT DEFAULT 'unknown',
                    source TEXT DEFAULT 'unknown',
                    contract_name TEXT,
                    is_verified BOOLEAN DEFAULT 0,
                    query_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(address, network)
                )
            ''')
            
            # 创建索引以提高查询性能
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_address_network 
                ON address_labels(address, network)
            ''')
            
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_label 
                ON address_labels(label)
            ''')
            
            self.conn.commit()
            
            # 统计现有记录数
            cursor = self.conn.execute('SELECT COUNT(*) FROM address_labels')
            count = cursor.fetchone()[0]
            print(f"📊 SQLite数据库: {self.db_file}")
            print(f"📁 已缓存地址数: {count} 个")
            
        except Exception as e:
            print(f"❌ 初始化数据库失败: {e}")
            raise
    
    def get_from_constants(self, address: str, network: str = 'ethereum') -> Optional[Dict]:
        """从地址常量文件获取标签"""
        if not HAS_CONSTANTS:
            return None
        
        try:
            info = get_address_info(address)
            if info:
                self.query_stats['constants_hits'] += 1
                # 添加网络信息
                info['network'] = network
                return info
        except Exception as e:
            print(f"⚠️ 查询常量失败: {e}")
        
        return None
    
    def get_from_sqlite(self, address: str, network: str = 'ethereum') -> Optional[Dict]:
        """从SQLite缓存获取标签"""
        try:
            cursor = self.conn.execute('''
                SELECT * FROM address_labels 
                WHERE address = ? AND network = ?
            ''', (address.lower(), network))
            
            row = cursor.fetchone()
            if row:
                # 检查缓存是否过期（可选，这里设置7天过期）
                cached_time = datetime.fromisoformat(row['created_at'])
                age_days = (datetime.now() - cached_time).days
                
                if age_days > 7:
                    print(f"   ⏰ 缓存已过期 ({age_days}天)，将重新查询")
                    return None
                
                # 如果SQLite中的结果是Unknown，不返回，继续查询外部API
                label = row['label']
                if 'unknown' in label.lower():
                    print(f"   💾 SQLite有Unknown记录，继续查询API")
                    return None
                
                # 非Unknown结果才作为缓存命中
                self.query_stats['sqlite_hits'] += 1
                
                result = {
                    'label': row['label'],
                    'type': row['type'],
                    'source': row['source'],
                    'network': row['network'],
                    'contract_name': row['contract_name'],
                    'is_verified': bool(row['is_verified']),
                    'query_count': row['query_count'],
                    'cached_at': row['created_at']
                }
                
                print(f"   💾 SQLite命中: {result['label']}")
                return result
                
        except Exception as e:
            print(f"⚠️ SQLite查询失败: {e}")
        
        return None
    
    def save_to_sqlite(self, address: str, network: str, label_info: Dict):
        """保存或更新SQLite中的地址标签"""
        try:
            address = address.lower()
            current_time = datetime.now().isoformat()
            
            # 检查是否已存在
            cursor = self.conn.execute('''
                SELECT id, query_count FROM address_labels 
                WHERE address = ? AND network = ?
            ''', (address, network))
            
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                self.conn.execute('''
                    UPDATE address_labels SET
                        label = ?,
                        type = ?,
                        source = ?,
                        contract_name = ?,
                        is_verified = ?,
                        query_count = query_count + 1,
                        updated_at = ?
                    WHERE address = ? AND network = ?
                ''', (
                    label_info.get('label'),
                    label_info.get('type', 'unknown'),
                    label_info.get('source', 'unknown'),
                    label_info.get('contract_name'),
                    label_info.get('is_verified', False),
                    current_time,
                    address,
                    network
                ))
                print(f"   🔄 SQLite已更新: {label_info.get('label')}")
            else:
                # 插入新记录
                self.conn.execute('''
                    INSERT INTO address_labels 
                    (address, network, label, type, source, contract_name, is_verified, query_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    address,
                    network,
                    label_info.get('label'),
                    label_info.get('type', 'unknown'),
                    label_info.get('source', 'unknown'),
                    label_info.get('contract_name'),
                    label_info.get('is_verified', False),
                    1,
                    current_time,
                    current_time
                ))
                print(f"   ➕ SQLite已保存: {label_info.get('label')}")
            
            self.conn.commit()
            self.query_stats['sqlite_updates'] += 1
            
        except Exception as e:
            print(f"❌ SQLite保存失败: {e}")
    
    def query_etherscan_api(self, address: str, network: str = 'ethereum') -> Optional[Dict]:
        """从Etherscan API查询地址信息"""
        if not HAS_REQUESTS or not self.session:
            return None
        
        network_config = self.network_configs.get(network.lower())
        if not network_config:
            print(f"⚠️ 不支持的网络: {network}")
            return None
        
        try:
            # 查询合约信息
            params = {
                'module': 'contract',
                'action': 'getsourcecode',
                'address': address,
                'apikey': self.etherscan_api_key
            }
            
            response = self.session.get(
                network_config['api_base'], 
                params=params, 
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if data.get('status') == '1' and data.get('result'):
                result = data['result'][0]
                contract_name = result.get('ContractName', '').strip()
                
                if contract_name and contract_name != '':
                    self.query_stats['api_queries'] += 1
                    
                    return {
                        'label': f"Contract: {contract_name}",
                        'type': 'contract',
                        'source': f'{network}_api',
                        'contract_name': contract_name,
                        'is_verified': True,
                        'network': network
                    }
            
            # 可以在这里添加其他API查询逻辑
            return None
            
        except Exception as e:
            print(f"⚠️ {network} API查询失败 {address[:10]}...{address[-8:]}: {e}")
            return None
    
    def get_address_label(self, address: str, network: str = 'ethereum') -> Dict[str, str]:
        """获取地址标签 - 多级查询策略"""
        address = address.lower()
        network = network.lower()
        self.query_stats['total_queries'] += 1
        
        print(f"🔍 查询地址: {address[:10]}...{address[-8:]} ({network})")
        
        # 1. 首先检查地址常量
        constants_result = self.get_from_constants(address, network)
        if constants_result:
            print(f"   ✅ 常量库命中: {constants_result['label']}")
            # 常量库结果保存到SQLite
            self.save_to_sqlite(address, network, constants_result)
            return constants_result
        
        # 2. 检查SQLite缓存（如果是Unknown则跳过）
        cache_result = self.get_from_sqlite(address, network)
        if cache_result:
            return cache_result
        
        # 3. 查询外部API
        print(f"   🌐 查询{network} API...")
        api_result = self.query_etherscan_api(address, network)
        if api_result:
            print(f"   🎯 API查询成功: {api_result['label']}")
            # 保存API结果到SQLite
            self.save_to_sqlite(address, network, api_result)
            return api_result
        
        # 4. 默认返回Unknown - 也保存到SQLite
        default_result = {
            'label': 'Unknown Address',
            'type': 'unknown',
            'source': 'default',
            'network': network
        }
        
        # Unknown地址也保存到SQLite，但下次会重新查询API
        self.save_to_sqlite(address, network, default_result)
        print(f"   ❓ 未知地址 (已缓存)")
        return default_result
    
    def extract_addresses_from_txt(self, txt_file: str) -> List[Dict]:
        """从TXT文件提取地址信息"""
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            addresses = []
            
            # 检测网络信息
            network = 'ethereum'  # 默认
            if 'ethereum' in content.lower():
                network = 'ethereum'
            elif 'polygon' in content.lower():
                network = 'polygon'
            elif 'bsc' in content.lower() or 'binance smart chain' in content.lower():
                network = 'bsc'
            
            # 使用正则表达式提取以太坊地址
            address_pattern = r'0x[a-fA-F0-9]{40}'
            
            # 按行处理
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '地址:' in line:
                    # 提取地址
                    match = re.search(address_pattern, line)
                    if match:
                        address = match.group()
                        
                        # 查找相关信息
                        name = "Unknown"
                        transaction_count = 0
                        total_amount = 0.0
                        
                        # 向前查找名称
                        for j in range(max(0, i-3), i):
                            if lines[j].strip() and not lines[j].startswith('   '):
                                name = lines[j].strip().split('.', 1)[-1].strip()
                                break
                        
                        # 向后查找统计信息
                        for j in range(i+1, min(len(lines), i+5)):
                            if '交互次数:' in lines[j]:
                                count_match = re.search(r'(\d+)\s*次', lines[j])
                                if count_match:
                                    transaction_count = int(count_match.group(1))
                            elif '总金额:' in lines[j]:
                                amount_match = re.search(r'([\d,]+\.?\d*)', lines[j])
                                if amount_match:
                                    total_amount = float(amount_match.group(1).replace(',', ''))
                        
                        addresses.append({
                            'address': address,
                            'network': network,
                            'name': name,
                            'transaction_count': transaction_count,
                            'total_amount': total_amount,
                            'source_type': 'analysis_result'
                        })
            
            return addresses
            
        except Exception as e:
            print(f"❌ 读取TXT文件失败: {e}")
            return []
    
    def extract_addresses_from_json(self, json_file: str) -> List[Dict]:
        """从JSON文件提取地址信息"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            addresses = []
            
            # 检测网络
            network = data.get('metadata', {}).get('network', 'ethereum').lower()
            if not network or network == 'unknown':
                network = 'ethereum'
            
            # 从 filtered_contracts 提取
            if 'filtered_contracts' in data:
                for contract in data['filtered_contracts']:
                    addresses.append({
                        'address': contract['address'],
                        'network': network,
                        'name': contract.get('name', 'Unknown'),
                        'transaction_count': contract.get('transaction_count', 0),
                        'total_amount': contract.get('total_amount', 0),
                        'source_type': 'contract'
                    })
            
            # 从addresses数组提取
            if 'addresses' in data:
                for addr_info in data['addresses']:
                    addresses.append({
                        'address': addr_info['address'],
                        'network': addr_info.get('network', network),
                        'name': addr_info.get('name', 'Unknown'),
                        'transaction_count': addr_info.get('transaction_count', 0),
                        'total_amount': addr_info.get('total_amount', 0),
                        'source_type': addr_info.get('type', 'unknown')
                    })
            
            return addresses
            
        except Exception as e:
            print(f"❌ 读取JSON文件失败: {e}")
            return []
    
    def analyze_file(self, file_path: str, network: str = None):
        """分析文件并查询地址标签"""
        print(f"🔍 分析文件: {file_path}")
        print("=" * 60)
        
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.json':
            addresses = self.extract_addresses_from_json(file_path)
        elif file_ext == '.txt':
            addresses = self.extract_addresses_from_txt(file_path)
        else:
            print(f"❌ 不支持的文件格式: {file_ext}")
            return
        
        if not addresses:
            print("❌ 没有找到地址信息")
            return
        
        # 如果指定了网络，覆盖检测到的网络
        if network:
            for addr in addresses:
                addr['network'] = network.lower()
        
        # 统计SQLite中的记录数
        cursor = self.conn.execute('SELECT COUNT(*) FROM address_labels')
        sqlite_count = cursor.fetchone()[0]
        
        print(f"📋 找到 {len(addresses)} 个地址")
        print(f"📊 SQLite缓存: {sqlite_count} 个地址")
        if HAS_CONSTANTS:
            print(f"📖 常量库: {len(ALL_KNOWN_ADDRESSES)} 个地址")
        print()
        
        # 查询标签
        results = []
        for i, addr_info in enumerate(addresses, 1):
            address = addr_info['address']
            addr_network = addr_info.get('network', 'ethereum')
            
            print(f"[{i:2d}/{len(addresses)}]", end=" ")
            
            # 获取标签
            label_info = self.get_address_label(address, addr_network)
            
            result = {
                **addr_info,
                **label_info
            }
            results.append(result)
            
            print(f"   📛 标签: {label_info['label']}")
            print(f"   🏷️ 类型: {label_info['type']}")
            print(f"   🔍 数据源: {label_info['source']}")
            print()
            
            # API查询间隔，避免限制
            if label_info.get('source', '').endswith('_api'):
                time.sleep(0.5)
        
        # 保存结果
        self.save_results(results, file_path)
        
        # 显示汇总
        self.show_summary(results)
        
        # 显示查询统计
        self.show_query_stats()
    
    def save_results(self, results: List[Dict], original_file: str):
        """保存查询结果"""
        try:
            # 生成输出文件名
            file_path = Path(original_file)
            output_file = file_path.parent / f"{file_path.stem}_with_labels.json"
            
            # 准备保存数据，包含元数据
            save_data = {
                'metadata': {
                    'original_file': str(original_file),
                    'analysis_time': datetime.now().isoformat(),
                    'total_addresses': len(results),
                    'query_stats': self.query_stats,
                    'tool_version': '4.0',
                    'database_file': self.db_file
                },
                'addresses': results
            }
            
            # 保存JSON格式
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 结果已保存到: {output_file}")
            
            # 保存人类可读格式
            txt_output_file = file_path.parent / f"{file_path.stem}_with_labels.txt"
            
            with open(txt_output_file, 'w', encoding='utf-8') as f:
                f.write("地址标签查询结果 (SQLite版本)\n")
                f.write("=" * 50 + "\n")
                f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"源文件: {original_file}\n")
                f.write(f"数据库: {self.db_file}\n")
                f.write(f"总地址数: {len(results)}\n")
                f.write(f"查询统计: 常量({self.query_stats['constants_hits']}) | "
                       f"SQLite({self.query_stats['sqlite_hits']}) | "
                       f"API({self.query_stats['api_queries']}) | "
                       f"更新({self.query_stats['sqlite_updates']})\n\n")
                
                for i, result in enumerate(results, 1):
                    f.write(f"{i}. {result['label']}\n")
                    f.write(f"   地址: {result['address']}\n")
                    f.write(f"   网络: {result.get('network', 'unknown')}\n")
                    f.write(f"   类型: {result['type']}\n")
                    f.write(f"   数据源: {result['source']}\n")
                    f.write(f"   原始名称: {result.get('name', 'Unknown')}\n")
                    f.write(f"   交互次数: {result.get('transaction_count', 'N/A')}\n")
                    f.write(f"   总金额: {result.get('total_amount', 'N/A')}\n")
                    if 'cached_at' in result:
                        f.write(f"   缓存时间: {result['cached_at']}\n")
                    f.write("\n")
            
            print(f"📝 可读格式已保存到: {txt_output_file}")
            
        except Exception as e:
            print(f"❌ 保存结果失败: {e}")
    
    def show_query_stats(self):
        """显示查询统计"""
        print("📈 查询统计")
        print("=" * 30)
        print(f"📖 常量库命中: {self.query_stats['constants_hits']} 次")
        print(f"📊 SQLite命中: {self.query_stats['sqlite_hits']} 次") 
        print(f"🌐 API查询: {self.query_stats['api_queries']} 次")
        print(f"💿 SQLite更新: {self.query_stats['sqlite_updates']} 次")
        print(f"🔍 总查询: {self.query_stats['total_queries']} 次")
        
        total_successful = (self.query_stats['constants_hits'] + 
                           self.query_stats['sqlite_hits'] + 
                           self.query_stats['api_queries'])
        
        if total_successful > 0:
            cache_hit_rate = ((self.query_stats['constants_hits'] + self.query_stats['sqlite_hits']) 
                             / total_successful * 100)
            print(f"🎯 缓存命中率: {cache_hit_rate:.1f}%")
        
        # SQLite统计信息
        cursor = self.conn.execute('SELECT COUNT(*) FROM address_labels')
        sqlite_count = cursor.fetchone()[0]
        print(f"📊 SQLite状态: {sqlite_count} 个地址")
        print()
    
    def show_summary(self, results: List[Dict]):
        """显示查询汇总"""
        print("📊 查询汇总")
        print("=" * 40)
        
        # 按网络分类统计
        network_stats = {}
        source_stats = {}
        type_stats = {}
        
        for result in results:
            network = result.get('network', 'unknown')
            source = result['source']
            addr_type = result['type']
            amount = result.get('total_amount', 0)
            txn_count = result.get('transaction_count', 0)
            
            # 网络统计
            if network not in network_stats:
                network_stats[network] = {'count': 0, 'amount': 0, 'txn': 0}
            network_stats[network]['count'] += 1
            network_stats[network]['amount'] += amount
            network_stats[network]['txn'] += txn_count
            
            # 数据源统计
            if source not in source_stats:
                source_stats[source] = {'count': 0, 'amount': 0}
            source_stats[source]['count'] += 1
            source_stats[source]['amount'] += amount
            
            # 类型统计
            if addr_type not in type_stats:
                type_stats[addr_type] = {'count': 0, 'amount': 0}
            type_stats[addr_type]['count'] += 1
            type_stats[addr_type]['amount'] += amount
        
        # 显示网络分布
        print("🌐 按网络分类:")
        for network, stats in sorted(network_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            network_name = self.network_configs.get(network, {}).get('name', network.title())
            print(f"   {network_name}: {stats['count']} 个地址")
            print(f"      交易: {stats['txn']:,} 笔, 金额: {stats['amount']:,.2f}")
        print()
        
        # 显示数据源分布
        print("🔍 按数据源分类:")
        for source, stats in sorted(source_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            print(f"   {source}: {stats['count']} 个地址 (总金额: {stats['amount']:,.2f})")
        print()
        
        # 显示类型分布
        print("🏷️ 按类型分类:")
        for addr_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            print(f"   {addr_type}: {stats['count']} 个地址 (总金额: {stats['amount']:,.2f})")
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()
            print("📊 SQLite数据库已关闭")

def main():
    """主函数"""
    import sys
    
    print("🏷️ 地址标签查询工具 (SQLite版本)")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # 命令行参数
        file_path = sys.argv[1]
        network = sys.argv[2] if len(sys.argv) > 2 else None
        db_file = sys.argv[3] if len(sys.argv) > 3 else 'address_labels.db'
    else:
        # 交互式输入
        file_path = input("请输入分析结果文件路径: ").strip()
        network = input("请输入网络名称 (ethereum/polygon/bsc，留空自动检测): ").strip()
        db_file = input("请输入数据库文件路径 (默认: address_labels.db): ").strip()
        
        if not network:
            network = None
        if not db_file:
            db_file = 'address_labels.db'
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    # 创建查询器
    querier = SQLiteAddressLabelQuerier(db_file)
    
    try:
        # 分析文件
        querier.analyze_file(file_path, network)
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断查询")
    except Exception as e:
        print(f"❌ 查询过程中出错: {e}")
    finally:
        # 关闭数据库
        querier.close()

if __name__ == "__main__":
    main()