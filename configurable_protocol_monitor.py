#!/usr/bin/env python3
"""
可配置协议监控器
支持完全自定义的监控参数：代币名称、网络、最小交易数量、时间窗口等
复用usdt_deposit_analyzer.py的方法
"""

import os
import sys
import time
import json
import logging
import schedule
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from collections import Counter
from usdt_deposit_analyzer import TokenDepositAnalyzer
from address_constant import get_contract_name, get_all_known_contracts, TOKEN_CONTRACTS, get_token_address, get_defi_protocol_name, get_all_defi_protocols, is_defi_protocol

# 配置日志
def setup_logging():
    """设置日志配置，支持控制台输出和每日轮转的文件输出"""
    # 创建logs目录
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 清除可能已存在的处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 文件处理器 - 每日轮转，保留7天
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'protocol_monitor.log'),
        when='midnight',      # 每天午夜轮转
        interval=1,           # 每1天轮转一次
        backupCount=7,        # 保留7天的日志文件
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# 初始化日志
logger = setup_logging()

class ConfigurableProtocolMonitor:
    def __init__(self, network="ethereum", token="USDT", min_amount=1000, 
                 time_window_minutes=5, monitor_interval_minutes=5, output_dir="monitor_output"):
        """初始化可配置协议监控器
        
        Args:
            network (str): 区块链网络，默认"ethereum"
            token (str): 代币名称，默认"USDT"
            min_amount (float): 最小转账金额，默认1000
            time_window_minutes (int): 分析时间窗口长度（分钟），默认5
            monitor_interval_minutes (int): 监控间隔（分钟），默认5
            output_dir (str): 输出目录，默认"monitor_output"
        """
        self.network = network
        self.token = token
        self.min_amount = min_amount
        self.time_window_minutes = time_window_minutes
        self.monitor_interval_minutes = monitor_interval_minutes
        self.output_dir = output_dir
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 验证配置
        self._validate_config()
        
        logger.info(f"🔍 可配置协议监控器已启动")
        logger.info(f"   网络: {network.upper()}")
        logger.info(f"   代币: {token}")
        logger.info(f"   最小金额: {min_amount} {token}")
        logger.info(f"   时间窗口: {time_window_minutes} 分钟")
        logger.info(f"   监控间隔: {monitor_interval_minutes} 分钟")
        logger.info(f"   输出目录: {output_dir}")
        logger.info("")
    
    def _validate_config(self):
        """验证配置参数的有效性"""
        # 验证网络
        if self.network not in TOKEN_CONTRACTS:
            raise ValueError(f"不支持的网络 '{self.network}'，支持的网络: {', '.join(TOKEN_CONTRACTS.keys())}")
        
        # 验证代币
        token_address = get_token_address(self.network, self.token)
        if not token_address or token_address == "0x0000000000000000000000000000000000000000":
            available_tokens = [t for t, addr in TOKEN_CONTRACTS[self.network].items() 
                              if addr != "0x0000000000000000000000000000000000000000"]
            raise ValueError(f"在{self.network}网络上不支持代币 '{self.token}'，"
                           f"该网络支持的代币: {', '.join(available_tokens)}")
        
        # 验证数值参数
        if self.min_amount <= 0:
            raise ValueError("最小金额必须大于0")
        
        if self.time_window_minutes <= 0:
            raise ValueError("时间窗口必须大于0分钟")
        
        if self.monitor_interval_minutes <= 0:
            raise ValueError("监控间隔必须大于0分钟")
        
        logger.info(f"✅ 配置验证通过")
        logger.info(f"   代币地址: {token_address}")
        
        # 初始化地址类型缓存
        self.address_type_cache = {}
        self.analyzer_instance = None  # 用于地址类型检查
    
    def get_time_window(self, minutes=None):
        """获取监控时间窗口
        
        Args:
            minutes (int): 时间窗口长度（分钟），如果为None则使用配置的默认值
            
        Returns:
            tuple: (start_time_str, end_time_str)
        """
        if minutes is None:
            minutes = self.time_window_minutes
            
        now = datetime.now(timezone.utc)
        end_time = now.replace(second=0, microsecond=0)  # 整分钟
        start_time = end_time - timedelta(minutes=minutes)
        
        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        return start_time_str, end_time_str
    
    def is_contract_address(self, address, analyzer=None):
        """判断地址是否为合约地址（使用analyzer的方法）
        
        Args:
            address (str): 要检查的地址
            analyzer: TokenDepositAnalyzer实例
            
        Returns:
            tuple: (is_contract: bool, address_type: str)
        """
        address = address.lower()
        
        # 检查缓存
        if address in self.address_type_cache:
            return self.address_type_cache[address]
        
        try:
            if analyzer and hasattr(analyzer, 'is_contract_address'):
                # 使用analyzer的方法
                is_contract, address_type = analyzer.is_contract_address(address)
                
                # 缓存结果
                cache_result = (is_contract, address_type)
                self.address_type_cache[address] = cache_result
                return cache_result
            else:
                # 回退到Unknown
                result = (False, "Unknown")
                self.address_type_cache[address] = result
                return result
                
        except Exception as e:
            # 如果出现异常，默认标记为Unknown
            result = (False, "Unknown") 
            self.address_type_cache[address] = result
            return result
    
    def analyze_recent_activity(self):
        """分析指定时间窗口的代币活动"""
        try:
            logger.info(f"🚀 开始分析最近{self.time_window_minutes}分钟的{self.token}活动...")
            logger.info(f"⏰ 时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            # 获取时间窗口
            start_time, end_time = self.get_time_window()
            logger.info(f"📅 分析时间窗口: {start_time} 到 {end_time} UTC")
            
            # 创建分析器实例
            analyzer = TokenDepositAnalyzer(
                start_time=start_time,
                end_time=end_time,
                min_amount=self.min_amount,
                network=self.network,
                token=self.token
            )
            
            # 保存analyzer实例用于地址类型检查
            self.analyzer_instance = analyzer
            
            # 获取转账记录，使用动态分段时间
            segment_minutes = max(10, self.time_window_minutes)  # 至少10分钟分段
            logger.info(f"🔄 获取{self.token}转账记录（分段时间: {segment_minutes}分钟）...")
            all_transfers = analyzer.get_usdt_transfers_by_time_segments(segment_minutes=segment_minutes)
            
            if not all_transfers:
                logger.error("❌ 未找到任何转账记录")
                return None
            
            logger.info(f"📦 获取到 {len(all_transfers)} 笔转账")
            
            # 筛选大额转账
            large_transfers = analyzer.filter_large_amounts(all_transfers)
            
            if not large_transfers:
                logger.error(f"❌ 未发现大于{self.min_amount} {self.token}的转账")
                return None
            
            logger.info(f"💰 大于{self.min_amount} {self.token}的转账: {len(large_transfers)} 笔")
            
            # 分析协议交互
            protocol_stats = self.analyze_protocol_interactions(large_transfers)
            
            if not protocol_stats:
                logger.error("❌ 未发现协议交互")
                return None
            
            # 生成报告
            report = self.generate_report(protocol_stats, start_time, end_time, large_transfers)
            
            # 保存结果
            self.save_results(report)
            
            logger.info(f"✅ 分析完成，发现 {len(protocol_stats)} 个活跃协议")
            return report
            
        except Exception as e:
            logger.error(f"❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze_protocol_interactions(self, transfers):
        """分析协议交互统计
        
        Args:
            transfers (list): 转账记录列表
            
        Returns:
            list: 按交互次数排序的协议统计
        """
        logger.info(f"🔍 分析协议交互...")
        
        # 统计每个地址的交互
        address_stats = {}
        
        for transfer in transfers:
            to_address = transfer['to'].lower()
            
            if to_address not in address_stats:
                # 获取协议名称
                protocol_name = get_contract_name(self.network, transfer['to'])
                
                # 判断地址类型
                is_contract, address_type = self.is_contract_address(transfer['to'], self.analyzer_instance)
                
                address_stats[to_address] = {
                    'address': transfer['to'],  # 保持原始大小写
                    'protocol_name': protocol_name,
                    'address_type': address_type,
                    'is_contract': is_contract,
                    'interaction_count': 0,
                    'total_amount': 0,
                    'transactions': []
                }
            
            # 累加统计
            address_stats[to_address]['interaction_count'] += 1
            address_stats[to_address]['total_amount'] += transfer['amount_usdt']
            address_stats[to_address]['transactions'].append({
                'hash': transfer['hash'],
                'from': transfer['from'],
                'amount': transfer['amount_usdt'],
                'timestamp': transfer['timeStamp']
            })
        
        # 只保留已知协议（非Unknown）或交互次数大于1的地址，并优先显示合约地址
        filtered_stats = []
        for stats in address_stats.values():
            # 优先保留合约地址，或者已知协议，或者交互次数大于1的地址
            if (stats['is_contract'] or 
                stats['protocol_name'] != 'Unknown' or 
                stats['interaction_count'] > 1):
                stats['avg_amount'] = stats['total_amount'] / stats['interaction_count']
                filtered_stats.append(stats)
        
        # 按交互次数降序排序，同时优先显示合约地址
        filtered_stats.sort(key=lambda x: (x['is_contract'], x['interaction_count']), reverse=True)
        
        logger.info(f"📊 发现 {len(filtered_stats)} 个活跃协议/合约")
        
        return filtered_stats
    
    def generate_report(self, protocol_stats, start_time, end_time, all_transfers):
        """生成监控报告
        
        Args:
            protocol_stats (list): 协议统计数据
            start_time (str): 开始时间
            end_time (str): 结束时间
            all_transfers (list): 所有转账记录
            
        Returns:
            dict: 报告数据
        """
        total_amount = sum(transfer['amount_usdt'] for transfer in all_transfers)
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis_period': {
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': self.time_window_minutes
            },
            'configuration': {
                'network': self.network,
                'token': self.token,
                'min_amount': self.min_amount,
                'time_window_minutes': self.time_window_minutes,
                'monitor_interval_minutes': self.monitor_interval_minutes
            },
            'summary': {
                'total_transfers': len(all_transfers),
                'total_amount': total_amount,
                'active_protocols': len(protocol_stats),
                'avg_amount_per_transfer': total_amount / len(all_transfers) if all_transfers else 0
            },
            'protocol_rankings': []
        }
        
        # 生成协议排名
        for i, stats in enumerate(protocol_stats, 1):
            protocol_info = {
                'rank': i,
                'address': stats['address'],
                'protocol_name': stats['protocol_name'],
                'address_type': stats['address_type'],
                'is_contract': stats['is_contract'],
                'interaction_count': stats['interaction_count'],
                'total_amount': stats['total_amount'],
                'avg_amount': stats['avg_amount'],
                'percentage_of_total': (stats['total_amount'] / total_amount * 100) if total_amount > 0 else 0
            }
            report['protocol_rankings'].append(protocol_info)
        
        return report
    
    def save_results(self, report):
        """保存监控结果
        
        Args:
            report (dict): 报告数据
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        config_suffix = f"{self.network}_{self.token}_{self.time_window_minutes}m"
        
        # 保存详细JSON报告
        json_filename = f"protocol_monitor_{config_suffix}_{timestamp}.json"
        json_filepath = os.path.join(self.output_dir, json_filename)
        
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        # 保存简化文本报告
        txt_filename = f"protocol_monitor_{config_suffix}_{timestamp}.txt"
        txt_filepath = os.path.join(self.output_dir, txt_filename)
        
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(f"{report['configuration']['network'].upper()} {report['configuration']['token']}协议监控报告\n")
            f.write(f"{'='*80}\n")
            f.write(f"监控时间: {report['timestamp']}\n")
            f.write(f"分析期间: {report['analysis_period']['start_time']} 到 {report['analysis_period']['end_time']} UTC\n")
            f.write(f"时间窗口: {report['configuration']['time_window_minutes']} 分钟\n")
            f.write(f"网络: {report['configuration']['network']}\n")
            f.write(f"代币: {report['configuration']['token']}\n")
            f.write(f"最小金额: {report['configuration']['min_amount']}\n")
            f.write(f"\n总计统计:\n")
            f.write(f"  总转账数: {report['summary']['total_transfers']:,} 笔\n")
            f.write(f"  总金额: {report['summary']['total_amount']:,.2f} {self.token}\n")
            f.write(f"  活跃协议数: {report['summary']['active_protocols']} 个\n")
            f.write(f"  平均金额: {report['summary']['avg_amount_per_transfer']:,.2f} {self.token}\n")
            f.write(f"\n协议排名 (按交互次数降序):\n")
            f.write(f"{'-'*100}\n")
            
            for protocol in report['protocol_rankings']:
                # 显示协议名称、地址类型和地址
                if protocol['protocol_name'] != 'Unknown':
                    header = f"#{protocol['rank']:2d}. {protocol['protocol_name']} [{protocol['address_type']}]"
                else:
                    header = f"#{protocol['rank']:2d}. 未知协议 [{protocol['address_type']}]"
                
                f.write(f"{header}\n")
                f.write(f"      地址: {protocol['address']}\n")
                f.write(f"      类型: {'合约地址' if protocol['is_contract'] else '外部账户 (EOA)'}\n")
                f.write(f"      交互次数: {protocol['interaction_count']:,} 次\n")
                f.write(f"      总金额: {protocol['total_amount']:,.2f} {self.token}\n")
                f.write(f"      平均金额: {protocol['avg_amount']:,.2f} {self.token}\n")
                f.write(f"      占比: {protocol['percentage_of_total']:.2f}%\n")
                f.write(f"\n")
        
        # 更新最新报告（覆盖式）
        latest_json = os.path.join(self.output_dir, f"latest_protocol_monitor_{config_suffix}.json")
        latest_txt = os.path.join(self.output_dir, f"latest_protocol_monitor_{config_suffix}.txt")
        
        with open(latest_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        with open(latest_txt, 'w', encoding='utf-8') as f:
            f.write(f"{report['configuration']['network'].upper()} {report['configuration']['token']}协议监控报告 (最新)\n")
            f.write(f"{'='*80}\n")
            f.write(f"监控时间: {report['timestamp']}\n")
            f.write(f"分析期间: {report['analysis_period']['start_time']} 到 {report['analysis_period']['end_time']} UTC\n")
            f.write(f"时间窗口: {report['configuration']['time_window_minutes']} 分钟\n")
            f.write(f"\n🏆 协议排名 (按交互次数降序):\n")
            f.write(f"{'-'*80}\n")
            
            for protocol in report['protocol_rankings']:
                # 显示协议名称、地址类型和地址
                if protocol['protocol_name'] != 'Unknown':
                    header = f"#{protocol['rank']:2d}. {protocol['protocol_name']} [{protocol['address_type']}]"
                else:
                    header = f"#{protocol['rank']:2d}. 未知协议 [{protocol['address_type']}]"
                
                f.write(f"{header}\n")
                f.write(f"      地址: {protocol['address']}\n")
                f.write(f"      类型: {'合约地址' if protocol['is_contract'] else '外部账户 (EOA)'}\n")
                f.write(f"      交互: {protocol['interaction_count']:,} 次\n")
                f.write(f"      金额: {protocol['total_amount']:,.0f} {self.token}\n")
                f.write(f"      占比: {protocol['percentage_of_total']:.1f}%\n")
                f.write(f"\n")
        
        logger.info(f"💾 结果已保存:")
        logger.info(f"   📄 详细报告: {json_filepath}")
        logger.info(f"   📝 文本报告: {txt_filepath}")
        logger.info(f"   📋 最新报告: {latest_txt}")
    
    def display_summary(self, report):
        """显示摘要信息"""
        if not report:
            return
        
        logger.info(f"\n📊 监控摘要:")
        logger.info(f"   配置: {report['configuration']['network'].upper()} {report['configuration']['token']}")
        logger.info(f"   时间窗口: {report['analysis_period']['start_time']} - {report['analysis_period']['end_time']} UTC")
        logger.info(f"   窗口长度: {report['configuration']['time_window_minutes']} 分钟")
        logger.info(f"   总转账: {report['summary']['total_transfers']} 笔")
        logger.info(f"   总金额: {report['summary']['total_amount']:,.0f} {self.token}")
        logger.info(f"   活跃协议: {report['summary']['active_protocols']} 个")
        
        logger.info(f"\n🏆 TOP 5 活跃协议:")
        for protocol in report['protocol_rankings'][:5]:
            if protocol['protocol_name'] != 'Unknown':
                name_display = protocol['protocol_name']
            else:
                name_display = "未知协议"
            
            # 显示地址的前6位和后4位
            address = protocol['address']
            short_addr = f"{address[:6]}...{address[-4:]}"
            
            # 地址类型标识
            addr_type = "📄" if protocol['is_contract'] else "👤"  # 📄 = 合约, 👤 = EOA
            
            logger.info(f"   #{protocol['rank']}. {name_display} {addr_type} ({short_addr}) - {protocol['interaction_count']} 次交互")
        logger.info("")
    
    def run_monitoring_cycle(self):
        """运行一次监控周期"""
        logger.info(f"{'='*80}")
        logger.info(f"🔄 开始新的监控周期")
        logger.info(f"⏰ 当前时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"📋 配置: {self.network.upper()} {self.token} (窗口: {self.time_window_minutes}分钟)")
        
        report = self.analyze_recent_activity()
        self.display_summary(report)
        
        logger.info(f"✅ 监控周期完成")
        logger.info(f"{'='*80}")
        logger.info("")
    
    def start_monitoring(self):
        """开始监控"""
        logger.info(f"🚀 启动可配置协议监控...")
        logger.info(f"   每{self.monitor_interval_minutes}分钟执行一次分析")
        logger.info(f"   分析窗口: {self.time_window_minutes}分钟")
        logger.info(f"   按 Ctrl+C 停止监控")
        logger.info("")
        
        # 立即执行一次
        self.run_monitoring_cycle()
        
        # 设置定时任务
        schedule.every(self.monitor_interval_minutes).minutes.do(self.run_monitoring_cycle)
        
        # 运行调度器
        while True:
            try:
                schedule.run_pending()
                time.sleep(10)  # 每10秒检查一次
            except KeyboardInterrupt:
                logger.info("\n🛑 收到停止信号，正在关闭监控...")
                break
            except Exception as e:
                logger.error(f"❌ 监控过程中出错: {e}")
                logger.info("⏳ 等待下次周期...")
                time.sleep(60)  # 出错后等待1分钟
        
        logger.info("👋 协议监控已停止")

def main():
    """主函数"""
    print("🔍 可配置多链代币协议监控器")
    print("=" * 60)
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("📖 功能说明:")
        print("  可配置的协议监控器，支持自定义代币、网络、时间窗口等参数")
        print("  分析指定时间窗口内的代币转账活动")
        print("  协议按交互数量降序排列")
        print("  自动识别已知协议名称")
        print()
        print("📝 使用方法:")
        print(f"  python {sys.argv[0]} [token] [network] [min_amount] [time_window] [interval]")
        print()
        print("📋 参数说明:")
        print("  token          - 代币名称 (可选，默认USDT)")
        print("  network        - 网络名称 (可选，默认ethereum)")
        print("  min_amount     - 最小转账金额 (可选，默认1000)")
        print("  time_window    - 分析时间窗口（分钟） (可选，默认5)")
        print("  interval       - 监控间隔（分钟） (可选，默认5)")
        print()
        print("🌐 支持的网络:")
        print("  ethereum       - 以太坊主网")
        print("  arbitrum       - Arbitrum One")
        print("  base           - Base")
        print("  bsc            - Binance Smart Chain")
        print()
        print("💰 支持的代币:")
        print("  USDT, USDC, DAI, WETH, ARB, BUSD, WBNB 等")
        print()
        print("📊 输出文件:")
        print("  monitor_output/protocol_monitor_{network}_{token}_{window}m_YYYYMMDD_HHMMSS.json")
        print("  monitor_output/protocol_monitor_{network}_{token}_{window}m_YYYYMMDD_HHMMSS.txt")
        print("  monitor_output/latest_protocol_monitor_{network}_{token}_{window}m.txt")
        print()
        print("🔧 环境变量:")
        print("  需要配置相应的API KEY环境变量")
        print()
        print("📋 示例:")
        print(f"  python {sys.argv[0]}                           # 默认: USDT ethereum 1000 5 5")
        print(f"  python {sys.argv[0]} USDT ethereum 1000 10 5   # 10分钟窗口，5分钟间隔")
        print(f"  python {sys.argv[0]} USDC bsc 5000 15 10       # BSC USDC，15分钟窗口，10分钟间隔")
        print(f"  python {sys.argv[0]} BUSD bsc 1000 5 3         # BSC BUSD，5分钟窗口，3分钟间隔")
        return
    
    try:
        # 获取参数
        token = "USDT"       # 默认代币
        network = "ethereum"  # 默认网络
        min_amount = 1000    # 默认最小金额
        time_window = 5      # 默认时间窗口（分钟）
        interval = 5         # 默认监控间隔（分钟）
        
        # 解析命令行参数
        if len(sys.argv) >= 2:
            token = sys.argv[1].upper()
        
        if len(sys.argv) >= 3:
            network = sys.argv[2].lower()
        
        if len(sys.argv) >= 4:
            try:
                min_amount = float(sys.argv[3])
            except ValueError:
                logger.error(f"⚠️ 警告: 无效的最小金额参数 '{sys.argv[3]}'，使用默认值1000")
                min_amount = 1000
        
        if len(sys.argv) >= 5:
            try:
                time_window = int(sys.argv[4])
                if time_window <= 0:
                    raise ValueError("时间窗口必须大于0")
            except ValueError:
                logger.error(f"⚠️ 警告: 无效的时间窗口参数 '{sys.argv[4]}'，使用默认值5分钟")
                time_window = 5
        
        if len(sys.argv) >= 6:
            try:
                interval = int(sys.argv[5])
                if interval <= 0:
                    raise ValueError("监控间隔必须大于0")
            except ValueError:
                logger.error(f"⚠️ 警告: 无效的监控间隔参数 '{sys.argv[5]}'，使用默认值5分钟")
                interval = 5
        
        print(f"📅 监控配置:")
        print(f"   代币: {token}")
        print(f"   网络: {network}")
        print(f"   最小金额: {min_amount}")
        print(f"   时间窗口: {time_window} 分钟")
        print(f"   监控间隔: {interval} 分钟")
        
        # 创建监控器实例（验证会在__init__中进行）
        monitor = ConfigurableProtocolMonitor(
            network=network,
            token=token, 
            min_amount=min_amount,
            time_window_minutes=time_window,
            monitor_interval_minutes=interval
        )
        
        # 开始监控
        monitor.start_monitoring()
        
    except Exception as e:
        logger.error(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()