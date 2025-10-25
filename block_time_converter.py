#!/usr/bin/env python3
"""
区块时间转换器
根据UTC开始时间和结束时间，查询对应的以太坊区块号区间
"""

import sys
import os
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class BlockTimeConverter:
    def __init__(self):
        """初始化区块时间转换器"""
        # API配置
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.etherscan_api_url = "https://api.etherscan.io/v2/api"  # 使用V2 API
        
        print(f"🔧 配置信息:")
        print(f"   Etherscan API: {'***' + self.etherscan_api_key[-4:] if len(self.etherscan_api_key) > 4 else 'YourApiKeyToken'}")
        print()
    
    def datetime_to_timestamp(self, dt_str):
        """将UTC时间字符串转换为时间戳
        
        Args:
            dt_str (str): UTC时间字符串，格式如 "2024-10-24 00:00:00" 或 "2024-10-24T00:00:00"
            
        Returns:
            int: Unix时间戳
        """
        try:
            # 支持多种时间格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d"
            ]
            
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                raise ValueError(f"无法解析时间格式: {dt_str}")
            
            # 设置时区为UTC
            dt = dt.replace(tzinfo=timezone.utc)
            
            # 转换为时间戳 - 使用UTC时间计算
            timestamp = int((dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
            
            print(f"   📅 {dt_str} UTC -> 时间戳: {timestamp}")
            return timestamp
            
        except Exception as e:
            raise ValueError(f"时间转换失败 {dt_str}: {e}")
    
    def get_block_by_timestamp(self, timestamp, closest='before'):
        """根据时间戳获取最接近的区块号
        
        Args:
            timestamp (int): Unix时间戳
            closest (str): 'before' 或 'after'，获取时间戳之前或之后最接近的区块
            
        Returns:
            int: 区块号
        """
        try:
            # 正确显示UTC时间
            utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            print(f"🔍 查询时间戳 {timestamp} ({utc_time.strftime('%Y-%m-%d %H:%M:%S')} UTC) 对应的区块号...")
            
            params = {
                'chainid': 1,  # 以太坊主网
                'module': 'block',
                'action': 'getblocknobytime',
                'timestamp': timestamp,
                'closest': closest,
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=30)
            data = response.json()
            
            if data['status'] == '1':
                block_number = int(data['result'])
                print(f"   📦 找到区块号: {block_number:,}")
                return block_number
            else:
                print(f"   ❌ API错误: {data.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"   ❌ 查询区块号失败: {e}")
            return None
    
    def get_block_details(self, block_number):
        """获取区块详细信息
        
        Args:
            block_number (int): 区块号
            
        Returns:
            dict: 区块信息
        """
        try:
            params = {
                'chainid': 1,  # 以太坊主网
                'module': 'proxy',
                'action': 'eth_getBlockByNumber',
                'tag': hex(block_number),
                'boolean': 'false',
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=30)
            data = response.json()
            
            if 'result' in data and data['result']:
                block_info = data['result']
                timestamp = int(block_info['timestamp'], 16)
                
                return {
                    'number': block_number,
                    'hash': block_info['hash'],
                    'timestamp': timestamp,
                    'datetime': datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    'transaction_count': len(block_info.get('transactions', [])),
                    'gas_used': int(block_info.get('gasUsed', '0x0'), 16),
                    'gas_limit': int(block_info.get('gasLimit', '0x0'), 16)
                }
            else:
                return None
                
        except Exception as e:
            print(f"   ⚠️ 获取区块详情失败: {e}")
            return None
    
    def validate_time_range(self, start_time, end_time):
        """验证时间范围的合理性
        
        Args:
            start_time (str): 开始时间
            end_time (str): 结束时间
        """
        start_ts = self.datetime_to_timestamp(start_time)
        end_ts = self.datetime_to_timestamp(end_time)
        
        if start_ts >= end_ts:
            raise ValueError("开始时间必须早于结束时间")
        
        # 检查时间是否过于久远或未来
        now = int(time.time())
        if start_ts > now:
            print("⚠️ 警告: 开始时间是未来时间")
        if end_ts > now:
            print("⚠️ 警告: 结束时间是未来时间")
        
        # 检查时间范围是否过大（超过30天提醒）
        time_diff = end_ts - start_ts
        days = time_diff / (24 * 60 * 60)
        if days > 30:
            print(f"⚠️ 警告: 时间范围较大 ({days:.1f} 天)，查询可能较慢")
        
        return start_ts, end_ts
    
    def get_block_range(self, start_time, end_time):
        """根据UTC时间范围获取区块号区间
        
        Args:
            start_time (str): 开始时间 (UTC)
            end_time (str): 结束时间 (UTC)
            
        Returns:
            tuple: (start_block, end_block, block_info)
        """
        try:
            print(f"🚀 开始查询区块号区间...")
            print(f"⏰ 开始时间: {start_time} UTC")
            print(f"⏰ 结束时间: {end_time} UTC")
            print("=" * 60)
            
            # 验证时间范围
            start_ts, end_ts = self.validate_time_range(start_time, end_time)
            
            # 获取开始区块（之前最接近的区块）
            start_block = self.get_block_by_timestamp(start_ts, 'before')
            if start_block is None:
                raise Exception("无法获取开始区块号")
            
            time.sleep(0.2)  # API限制
            
            # 获取结束区块（之后最接近的区块）
            end_block = self.get_block_by_timestamp(end_ts, 'after')
            if end_block is None:
                raise Exception("无法获取结束区块号")
            
            # 获取区块详细信息
            print(f"\n📋 获取区块详细信息...")
            start_info = self.get_block_details(start_block)
            time.sleep(0.2)
            end_info = self.get_block_details(end_block)
            
            # 格式化结果
            result = {
                'query': {
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_timestamp': start_ts,
                    'end_timestamp': end_ts
                },
                'blocks': {
                    'start_block': start_block,
                    'end_block': end_block,
                    'block_count': end_block - start_block + 1
                },
                'details': {
                    'start_block_info': start_info,
                    'end_block_info': end_info
                }
            }
            
            # 显示结果
            self.display_results(result)
            
            return start_block, end_block, result
            
        except Exception as e:
            raise Exception(f"查询失败: {e}")
    
    def display_results(self, result):
        """显示查询结果"""
        print(f"\n📊 查询结果")
        print("=" * 80)
        
        # 查询参数
        query = result['query']
        print(f"🕐 查询时间范围:")
        print(f"   开始: {query['start_time']} UTC (时间戳: {query['start_timestamp']})")
        print(f"   结束: {query['end_time']} UTC (时间戳: {query['end_timestamp']})")
        
        # 区块范围
        blocks = result['blocks']
        print(f"\n📦 区块号范围:")
        print(f"   开始区块: {blocks['start_block']:,}")
        print(f"   结束区块: {blocks['end_block']:,}")
        print(f"   区块数量: {blocks['block_count']:,}")
        
        # 区块详情
        details = result['details']
        if details['start_block_info']:
            start_info = details['start_block_info']
            print(f"\n🎯 开始区块详情:")
            print(f"   区块号: {start_info['number']:,}")
            print(f"   区块哈希: {start_info['hash']}")
            print(f"   时间: {start_info['datetime']} UTC")
            print(f"   交易数: {start_info['transaction_count']:,}")
            print(f"   Gas使用: {start_info['gas_used']:,} / {start_info['gas_limit']:,}")
        
        if details['end_block_info']:
            end_info = details['end_block_info']
            print(f"\n🏁 结束区块详情:")
            print(f"   区块号: {end_info['number']:,}")
            print(f"   区块哈希: {end_info['hash']}")
            print(f"   时间: {end_info['datetime']} UTC")
            print(f"   交易数: {end_info['transaction_count']:,}")
            print(f"   Gas使用: {end_info['gas_used']:,} / {end_info['gas_limit']:,}")
        
        # 计算一些统计信息
        if details['start_block_info'] and details['end_block_info']:
            start_info = details['start_block_info']
            end_info = details['end_block_info']
            
            time_diff = end_info['timestamp'] - start_info['timestamp']
            block_diff = end_info['number'] - start_info['number']
            
            if block_diff > 0:
                avg_block_time = time_diff / block_diff
                print(f"\n📈 统计信息:")
                print(f"   实际时间跨度: {time_diff:,} 秒 ({time_diff/3600:.1f} 小时)")
                print(f"   平均出块时间: {avg_block_time:.2f} 秒")
    
    def save_results(self, result, output_dir="temp"):
        """保存结果到文件"""
        try:
            import json
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 处理datetime对象序列化
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            
            # 保存JSON文件
            json_filename = f"block_range_{timestamp}.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=json_serializer)
            
            # 保存文本报告
            txt_filename = f"block_range_{timestamp}.txt"
            txt_filepath = os.path.join(output_dir, txt_filename)
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write("以太坊区块号查询结果\n")
                f.write("=" * 50 + "\n")
                f.write(f"查询时间: {datetime.now()}\n\n")
                
                query = result['query']
                f.write(f"查询时间范围:\n")
                f.write(f"  开始: {query['start_time']} UTC\n")
                f.write(f"  结束: {query['end_time']} UTC\n\n")
                
                blocks = result['blocks']
                f.write(f"区块号范围:\n")
                f.write(f"  开始区块: {blocks['start_block']:,}\n")
                f.write(f"  结束区块: {blocks['end_block']:,}\n")
                f.write(f"  区块数量: {blocks['block_count']:,}\n\n")
                
                details = result['details']
                if details['start_block_info']:
                    start_info = details['start_block_info']
                    f.write(f"开始区块详情:\n")
                    f.write(f"  区块号: {start_info['number']:,}\n")
                    f.write(f"  时间: {start_info['datetime']} UTC\n")
                    f.write(f"  交易数: {start_info['transaction_count']:,}\n\n")
                
                if details['end_block_info']:
                    end_info = details['end_block_info']
                    f.write(f"结束区块详情:\n")
                    f.write(f"  区块号: {end_info['number']:,}\n")
                    f.write(f"  时间: {end_info['datetime']} UTC\n")
                    f.write(f"  交易数: {end_info['transaction_count']:,}\n")
            
            print(f"\n💾 结果已保存:")
            print(f"   📄 详细数据: {json_filepath}")
            print(f"   📝 文本报告: {txt_filepath}")
            
            return json_filepath, txt_filepath
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")
            return None, None

def main():
    """主函数"""
    print("🕐 以太坊区块时间转换器")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("📖 功能说明:")
        print("  根据UTC开始时间和结束时间，查询对应的以太坊区块号区间")
        print()
        print("📝 使用方法:")
        print(f"  python {sys.argv[0]} [start_time] [end_time]")
        print()
        print("🕐 时间格式支持:")
        print("  - YYYY-MM-DD HH:MM:SS  (如: 2024-10-24 00:00:00)")
        print("  - YYYY-MM-DDTHH:MM:SS  (如: 2024-10-24T00:00:00)")
        print("  - YYYY-MM-DD           (如: 2024-10-24，默认00:00:00)")
        print("  - YYYY/MM/DD HH:MM:SS  (如: 2024/10/24 00:00:00)")
        print()
        print("🔧 环境变量配置 (.env文件):")
        print("  ETHERSCAN_API_KEY=YourEtherscanApiKey")
        print()
        print("📋 示例:")
        print(f"  python {sys.argv[0]} '2024-10-24 00:00:00' '2024-10-24 23:59:59'")
        print(f"  python {sys.argv[0]} '2024-10-24' '2024-10-25'")
        return
    
    try:
        # 创建转换器实例
        converter = BlockTimeConverter()
        
        # 获取时间参数
        if len(sys.argv) >= 3:
            start_time = sys.argv[1]
            end_time = sys.argv[2]
        else:
            # 交互式输入
            print("📝 请输入查询参数:")
            start_time = input("开始时间 (UTC): ").strip()
            end_time = input("结束时间 (UTC): ").strip()
            
            if not start_time or not end_time:
                print("❌ 时间不能为空")
                return
        
        # 执行查询
        start_block, end_block, result = converter.get_block_range(start_time, end_time)
        
        # 保存结果
        converter.save_results(result)
        
        print(f"\n✅ 查询完成!")
        print(f"📦 区块范围: {start_block:,} 到 {end_block:,}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()