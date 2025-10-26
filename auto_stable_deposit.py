#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动定时存款程序
每隔10分钟自动调用concrete_stable_interaction_v2.py的deposit方法存入11 USDT
成功时播放提醒音
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import subprocess
import platform

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(__file__))

try:
    from concrete_stable_interaction_v2 import ConcreteStableInteractionV2
except ImportError as e:
    print(f"❌ 无法导入ConcreteStableInteractionV2: {e}")
    print("请确保concrete_stable_interaction_v2.py文件在同一目录下")
    sys.exit(1)

class AutoDepositBot:
    """自动存款机器人"""
    
    def __init__(self, mock_mode=False, preprod_mode=False, deposit_amount=11.0, interval_minutes=10, single_deposit=False):
        """
        初始化自动存款机器人
        
        Args:
            mock_mode (bool): 是否使用mock模式
            preprod_mode (bool): 是否使用preprod模式  
            deposit_amount (float): 每次存款金额（USDT）
            interval_minutes (int): 存款间隔（分钟）
            single_deposit (bool): 是否为单次存款模式（存款成功后持续播放提醒音）
        """
        self.mock_mode = mock_mode
        self.preprod_mode = preprod_mode
        self.deposit_amount = deposit_amount
        self.interval_minutes = interval_minutes
        self.single_deposit = single_deposit
        self.alert_sound_path = os.path.join(os.path.dirname(__file__), 'resource', 'alert.mp3')
        
        # 设置日志
        self._setup_logging()
        
        # 统计信息
        self.total_attempts = 0
        self.successful_deposits = 0
        self.failed_deposits = 0
        self.total_deposited = 0.0
        self.start_time = datetime.now()
        self.deposit_completed = False  # 用于单次存款模式
        
        self.logger.info(f"🤖 自动存款机器人启动")
        self.logger.info(f"   存款金额: {deposit_amount} USDT")
        self.logger.info(f"   存款间隔: {interval_minutes} 分钟")
        self.logger.info(f"   运行模式: {'Mock' if mock_mode else 'Preprod' if preprod_mode else 'Real'}")
        self.logger.info(f"   单次存款: {'是' if single_deposit else '否'}")
        
        if single_deposit:
            self.logger.info(f"⚠️ 单次存款模式: 成功存款一次后将持续播放提醒音")
        
    def _setup_logging(self):
        """设置日志"""
        # 创建logs目录
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志文件名
        log_filename = f"auto_deposit_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = os.path.join(log_dir, log_filename)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def play_alert_sound(self):
        """播放提醒音"""
        try:
            if not os.path.exists(self.alert_sound_path):
                self.logger.warning(f"⚠️ 提醒音文件不存在: {self.alert_sound_path}")
                # 使用系统默认提醒音
                self._play_system_alert()
                return
                
            system = platform.system().lower()
            
            if system == "darwin":  # macOS
                subprocess.run(['afplay', self.alert_sound_path], check=True)
            elif system == "linux":
                # 尝试多种Linux音频播放器
                players = ['mpg123', 'mplayer', 'ffplay', 'paplay']
                for player in players:
                    try:
                        subprocess.run([player, self.alert_sound_path], 
                                     check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                else:
                    self.logger.warning("⚠️ 未找到可用的音频播放器")
                    self._play_system_alert()
            elif system == "windows":
                import winsound
                winsound.PlaySound(self.alert_sound_path, winsound.SND_FILENAME)
            else:
                self.logger.warning(f"⚠️ 不支持的操作系统: {system}")
                self._play_system_alert()
                
            self.logger.info("🔊 播放提醒音成功")
            
        except Exception as e:
            self.logger.error(f"❌ 播放提醒音失败: {e}")
            self._play_system_alert()
    
    def _play_system_alert(self):
        """播放系统默认提醒音"""
        try:
            system = platform.system().lower()
            if system == "darwin":  # macOS
                subprocess.run(['osascript', '-e', 'beep'], check=True)
            elif system == "linux":
                subprocess.run(['speaker-test', '-t', 'sine', '-f', '1000', '-l', '1'], 
                             check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "windows":
                import winsound
                winsound.Beep(1000, 500)  # 1000Hz, 500ms
        except Exception as e:
            self.logger.error(f"❌ 播放系统提醒音失败: {e}")
    
    def create_interactor(self) -> Optional[ConcreteStableInteractionV2]:
        """创建合约交互器实例"""
        try:
            interactor = ConcreteStableInteractionV2(
                mock_mode=self.mock_mode,
                preprod_mode=self.preprod_mode
            )
            return interactor
        except Exception as e:
            self.logger.error(f"❌ 创建合约交互器失败: {e}")
            return None
    
    def check_balance_and_allowance(self, interactor: ConcreteStableInteractionV2) -> bool:
        """检查余额和授权额度是否足够"""
        try:
            balances = interactor.get_balances()
            usdt_balance = balances['usdt_balance']
            allowance = balances['allowance']
            
            self.logger.info(f"💰 当前USDT余额: {usdt_balance:.6f}")
            self.logger.info(f"✅ 当前授权额度: {allowance:.6f}")
            
            if usdt_balance < self.deposit_amount:
                self.logger.warning(f"⚠️ USDT余额不足: {usdt_balance} < {self.deposit_amount}")
                return False
                
            if allowance < self.deposit_amount:
                self.logger.warning(f"⚠️ 授权额度不足: {allowance} < {self.deposit_amount}")
                self.logger.info(f"🔄 尝试自动授权...")
                
                # 尝试自动授权
                try:
                    approve_result = interactor.approve_usdt()  # 授权最大值
                    if approve_result:
                        # approve_usdt返回的是交易回执(tx_receipt)，不是交易哈希
                        if hasattr(approve_result, 'transactionHash'):
                            tx_hash = approve_result.transactionHash.hex()
                            self.logger.info(f"✅ 自动授权成功: {tx_hash}")
                        else:
                            self.logger.info(f"✅ 自动授权成功: 区块号 {approve_result.get('blockNumber', 'Unknown')}")
                        time.sleep(5)  # 等待交易确认
                        return True
                    else:
                        self.logger.error(f"❌ 自动授权失败")
                        return False
                except Exception as approve_error:
                    self.logger.error(f"❌ 自动授权异常: {approve_error}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 检查余额和授权失败: {e}")
            return False
    
    def attempt_deposit(self) -> bool:
        """尝试执行存款"""
        self.total_attempts += 1
        
        self.logger.info(f"🚀 开始第 {self.total_attempts} 次存款尝试...")
        
        # 创建合约交互器
        interactor = self.create_interactor()
        if not interactor:
            self.failed_deposits += 1
            return False
        
        # 检查余额和授权
        if not self.check_balance_and_allowance(interactor):
            self.failed_deposits += 1
            return False
        
        # 执行存款
        try:
            self.logger.info(f"💎 开始存款 {self.deposit_amount} USDT...")
            
            tx_result = interactor.deposit_usdt(self.deposit_amount)
            
            if tx_result:
                self.successful_deposits += 1
                self.total_deposited += self.deposit_amount
                
                self.logger.info(f"✅ 存款成功!")
                
                # 从交易回执中提取交易哈希
                if hasattr(tx_result, 'transactionHash'):
                    tx_hash = tx_result.transactionHash.hex()
                    self.logger.info(f"   交易哈希: {tx_hash}")
                else:
                    self.logger.info(f"   区块号: {tx_result.get('blockNumber', 'Unknown')}")
                
                self.logger.info(f"   存款金额: {self.deposit_amount} USDT")
                self.logger.info(f"   累计存款: {self.total_deposited} USDT")
                
                # 播放提醒音
                self.play_alert_sound()
                
                # 如果是单次存款模式，标记存款已完成
                if self.single_deposit:
                    self.deposit_completed = True
                    self.logger.info(f"🎯 单次存款完成，进入持续提醒模式...")
                
                return True
            else:
                self.failed_deposits += 1
                self.logger.error(f"❌ 存款失败: 未返回交易回执")
                return False
                
        except Exception as e:
            self.failed_deposits += 1
            self.logger.error(f"❌ 存款异常: {e}")
            return False
    
    def print_statistics(self):
        """打印统计信息"""
        runtime = datetime.now() - self.start_time
        
        self.logger.info(f"\n📊 运行统计:")
        self.logger.info(f"   运行时间: {runtime}")
        self.logger.info(f"   总尝试次数: {self.total_attempts}")
        self.logger.info(f"   成功次数: {self.successful_deposits}")
        self.logger.info(f"   失败次数: {self.failed_deposits}")
        self.logger.info(f"   成功率: {(self.successful_deposits/max(self.total_attempts,1)*100):.1f}%")
        self.logger.info(f"   累计存款: {self.total_deposited} USDT")
        
        if self.successful_deposits > 0:
            avg_interval = runtime.total_seconds() / self.successful_deposits / 60
            self.logger.info(f"   平均存款间隔: {avg_interval:.1f} 分钟")
    
    def run(self):
        """运行自动存款机器人"""
        self.logger.info(f"🎯 自动存款机器人开始运行...")
        self.logger.info(f"   按 Ctrl+C 停止")
        
        try:
            while True:
                try:
                    # 检查是否为单次存款模式且已完成存款
                    if self.single_deposit and self.deposit_completed:
                        self.logger.info(f"🔊 持续播放提醒音...")
                        self.play_alert_sound()
                        
                        # 打印统计信息（每次播放提醒音后）
                        self.print_statistics()
                        
                        # 等待间隔时间后再次播放
                        self.logger.info(f"⏰ 等待 {self.interval_minutes} 分钟后再次播放提醒音...")
                        time.sleep(self.interval_minutes * 60)
                        continue
                    
                    # 如果尚未存款成功，执行存款尝试
                    if not (self.single_deposit and self.deposit_completed):
                        success = self.attempt_deposit()
                        
                        # 打印统计信息
                        self.print_statistics()
                        
                        # 如果是单次存款模式且存款成功，下次循环将进入持续提醒模式
                        if self.single_deposit and success:
                            # 立即播放一次提醒音，然后进入持续模式
                            next_time = datetime.now() + timedelta(minutes=self.interval_minutes)
                            self.logger.info(f"⏰ 下次播放提醒音时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        elif not self.single_deposit:
                            # 常规模式：计算下次存款时间
                            next_time = datetime.now() + timedelta(minutes=self.interval_minutes)
                            self.logger.info(f"⏰ 下次存款时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # 等待指定间隔
                        if not (self.single_deposit and success):
                            self.logger.info(f"😴 等待 {self.interval_minutes} 分钟...")
                            time.sleep(self.interval_minutes * 60)
                    
                except KeyboardInterrupt:
                    self.logger.info(f"\n⏹️ 收到停止信号...")
                    break
                except Exception as e:
                    self.logger.error(f"❌ 运行过程中发生异常: {e}")
                    self.logger.info(f"⏳ 等待 {self.interval_minutes} 分钟后重试...")
                    time.sleep(self.interval_minutes * 60)
                    
        except KeyboardInterrupt:
            self.logger.info(f"\n⏹️ 程序被用户中断")
        finally:
            self.logger.info(f"🏁 自动存款机器人停止运行")
            self.print_statistics()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='自动定时存款程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python auto_deposit.py                          # 默认设置（真实模式，11 USDT，10分钟）
  python auto_deposit.py --mock                   # Mock模式
  python auto_deposit.py --preprod                # Preprod模式
  python auto_deposit.py --amount 20 --interval 5 # 每5分钟存入20 USDT
  python auto_deposit.py --mock --amount 1 --interval 1  # Mock模式，每1分钟存入1 USDT（测试用）
  python auto_deposit.py --single --mock           # 单次存款模式（Mock）
  python auto_deposit.py --single --amount 50      # 单次存入50 USDT后持续提醒

模式说明:
  真实模式   - 连接真实网络，实际消耗Gas费用
  Preprod模式 - 连接本地RPC，使用真实私钥签名
  Mock模式   - 连接本地RPC，使用Impersonate模式
  单次模式   - 成功存款一次后不再存款，持续播放提醒音
        """
    )
    
    parser.add_argument('--mock', action='store_true', help='使用Mock模式（Impersonate）')
    parser.add_argument('--preprod', action='store_true', help='使用Preprod模式（真实签名 + 本地RPC）')
    parser.add_argument('--amount', type=float, default=11.0, help='每次存款金额（USDT，默认11）')
    parser.add_argument('--interval', type=int, default=10, help='存款间隔（分钟，默认10）')
    parser.add_argument('--single', action='store_true', help='单次存款模式（存款成功后持续播放提醒音）')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.mock and args.preprod:
        print("❌ 错误: 不能同时使用 --mock 和 --preprod 参数")
        return
    
    if args.amount <= 0:
        print("❌ 错误: 存款金额必须大于0")
        return
        
    if args.interval <= 0:
        print("❌ 错误: 存款间隔必须大于0分钟")
        return
    
    print("🤖 自动定时存款程序")
    print("=" * 50)
    
    # 创建并运行机器人
    bot = AutoDepositBot(
        mock_mode=args.mock,
        preprod_mode=args.preprod,
        deposit_amount=args.amount,
        interval_minutes=args.interval,
        single_deposit=args.single
    )
    
    bot.run()

if __name__ == "__main__":
    main()