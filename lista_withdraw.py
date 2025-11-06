#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lista MEV合约定期Withdraw脚本
功能：定期检查并调用withdraw方法从合约中取出资金
参考交易：https://bscscan.com/tx/0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f
"""

import os
import json
import time
import argparse
from typing import Optional
from datetime import datetime
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class ListaWithdraw:
    """Lista MEV合约Withdraw操作类"""
    
    def __init__(self):
        """初始化"""
        # 合约地址
        self.contract_address = "0x6402d64F035E18F9834591d3B994dFe41a0f162D"
        
        # BSC RPC URL
        self.rpc_url = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed1.binance.org')
        
        # 初始化Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if not self.w3.is_connected():
            raise Exception("❌ 无法连接到BSC网络")
        
        logger.info(f"✅ 成功连接到BSC网络")
        logger.info(f"🌐 RPC URL: {self.rpc_url}")
        
        # 加载私钥
        private_key = os.getenv('WALLET_PRIVATE_KEY')
        if not private_key:
            raise Exception("❌ 未找到WALLET_PRIVATE_KEY环境变量")
        
        # 确保私钥格式正确
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        
        logger.info(f"� 私钥: {private_key[:10]}...{private_key[-8:]}")
        logger.info(f"�💼 对应地址: {self.wallet_address}")
        
        # 加载合约ABI
        self.contract = self.load_contract()
        
        # 获取当前余额
        self.check_balance()
    
    def load_contract(self):
        """加载合约ABI并创建合约实例"""
        abi_file = os.path.join(
            os.path.dirname(__file__),
            'abi',
            'bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json'
        )
        
        if not os.path.exists(abi_file):
            raise Exception(f"❌ ABI文件不存在: {abi_file}")
        
        logger.info(f"📄 加载ABI文件: {abi_file}")
        
        with open(abi_file, 'r', encoding='utf-8') as f:
            abi_data = json.load(f)
        
        abi = abi_data.get('abi', [])
        
        if not abi:
            raise Exception("❌ ABI数据为空")
        
        logger.info(f"✅ 成功加载ABI，包含 {len(abi)} 个函数/事件")
        
        # 检查是否有withdraw函数
        withdraw_func = None
        for item in abi:
            if item.get('type') == 'function' and item.get('name') == 'withdraw':
                withdraw_func = item
                break
        
        if withdraw_func:
            logger.info(f"✅ 找到withdraw函数")
            inputs = withdraw_func.get('inputs', [])
            logger.info(f"   参数: {[inp.get('name') + ':' + inp.get('type') for inp in inputs]}")
        else:
            logger.warning(f"⚠️ 未找到withdraw函数")
        
        # 创建合约实例
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=abi
        )
        
        return contract
    
    def check_balance(self):
        """检查钱包和合约余额"""
        # BNB余额
        bnb_balance = self.w3.eth.get_balance(self.wallet_address)
        bnb_balance_ether = self.w3.from_wei(bnb_balance, 'ether')
        
        logger.info(f"💰 BNB余额: {bnb_balance_ether:.6f} BNB")
        
        # 检查合约中的资产余额
        try:
            # 尝试调用balanceOf函数
            balance = self.contract.functions.balanceOf(self.wallet_address).call()
            balance_formatted = self.w3.from_wei(balance, 'ether')
            logger.info(f"💎 合约中的资产余额: {balance_formatted:.6f}")
        except Exception as e:
            logger.warning(f"⚠️ 无法获取合约余额: {e}")
        
        return bnb_balance
    
    def get_max_withdraw(self) -> float:
        """获取最大可取出金额"""
        try:
            max_withdraw_wei = self.contract.functions.maxWithdraw(self.wallet_address).call()
            max_withdraw = self.w3.from_wei(max_withdraw_wei, 'ether')
            return float(max_withdraw)
        except Exception as e:
            logger.error(f"❌ 获取最大可取出金额失败: {e}")
            return 0.0
    
    def withdraw(self, amount: float, receiver: Optional[str] = None, owner: Optional[str] = None):
        """
        调用合约的withdraw方法
        
        Args:
            amount: 要取出的金额（单位：ether）
            receiver: 接收地址（默认为当前钱包地址）
            owner: 所有者地址（默认为当前钱包地址）
        """
        if receiver is None:
            receiver = self.wallet_address
        
        if owner is None:
            owner = self.wallet_address
        
        # 转换金额为wei
        amount_wei = self.w3.to_wei(amount, 'ether')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 准备调用withdraw方法")
        logger.info(f"{'='*60}")
        logger.info(f"📍 合约地址: {self.contract_address}")
        logger.info(f"💰 取出金额: {amount} (wei: {amount_wei})")
        logger.info(f"📬 接收地址: {receiver}")
        logger.info(f"👤 所有者地址: {owner}")
        
        try:
            # 获取当前nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            logger.info(f"🔢 Nonce: {nonce}")
            
            # 获取gas price
            gas_price = self.w3.eth.gas_price
            logger.info(f"⛽ Gas Price: {self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")
            
            # 构建交易
            logger.info(f"🔨 构建交易...")
            
            # 调用withdraw函数
            # withdraw(uint256 assets, address receiver, address owner)
            tx = self.contract.functions.withdraw(
                amount_wei,
                Web3.to_checksum_address(receiver),
                Web3.to_checksum_address(owner)
            ).build_transaction({
                'from': self.wallet_address,
                'nonce': nonce,
                'gas': 500000,  # 预估gas limit
                'gasPrice': gas_price,
                'chainId': 56  # BSC链ID
            })
            
            logger.info(f"✅ 交易构建成功")
            logger.info(f"   Gas Limit: {tx['gas']}")
            
            # 估算实际需要的gas
            try:
                estimated_gas = self.w3.eth.estimate_gas(tx)
                logger.info(f"📊 估算Gas: {estimated_gas}")
                # 使用估算的gas并增加20%作为缓冲
                tx['gas'] = int(estimated_gas * 1.2)
                logger.info(f"   调整后Gas Limit: {tx['gas']}")
            except Exception as e:
                logger.warning(f"⚠️ Gas估算失败，使用默认值: {e}")
                logger.warning(f"⚠️ 这可能表示交易会失败，原因可能是:")
                logger.warning(f"   1. 合约余额不足")
                logger.warning(f"   2. 没有权限执行withdraw")
                logger.warning(f"   3. 取出金额超过可用余额")
                logger.warning(f"   4. 合约有其他限制条件")
                
                # 尝试获取更多信息
                try:
                    # 检查shares余额
                    shares_balance = self.contract.functions.balanceOf(self.wallet_address).call()
                    logger.info(f"   当前shares余额: {self.w3.from_wei(shares_balance, 'ether'):.6f}")
                    
                    # 检查maxWithdraw
                    max_withdraw = self.contract.functions.maxWithdraw(self.wallet_address).call()
                    logger.info(f"   最大可取出: {self.w3.from_wei(max_withdraw, 'ether'):.6f}")
                    
                    if amount_wei > max_withdraw:
                        logger.error(f"   ❌ 错误: 取出金额 ({amount}) 超过最大可取出金额 ({self.w3.from_wei(max_withdraw, 'ether'):.6f})")
                        return None
                except Exception as check_error:
                    logger.warning(f"   无法获取详细信息: {check_error}")
            
            # 签名交易
            logger.info(f"✍️ 签名交易...")
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            
            # 发送交易
            logger.info(f"📤 发送交易...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"✅ 交易已发送!")
            logger.info(f"📝 交易哈希: {tx_hash_hex}")
            logger.info(f"🔗 查看交易: https://bscscan.com/tx/{tx_hash_hex}")
            
            # 等待交易确认
            logger.info(f"⏳ 等待交易确认...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                logger.info(f"\n{'='*60}")
                logger.info(f"✅ 交易成功!")
                logger.info(f"{'='*60}")
                logger.info(f"📦 区块号: {receipt['blockNumber']}")
                logger.info(f"⛽ Gas使用: {receipt['gasUsed']}")
                logger.info(f"💸 交易费用: {self.w3.from_wei(receipt['gasUsed'] * gas_price, 'ether'):.6f} BNB")
                
                # 检查更新后的余额
                logger.info(f"\n{'='*60}")
                logger.info(f"📊 更新后的余额:")
                logger.info(f"{'='*60}")
                self.check_balance()
                
                return tx_hash_hex
            else:
                logger.error(f"❌ 交易失败!")
                logger.error(f"📝 交易哈希: {tx_hash_hex}")
                logger.error(f"📦 区块号: {receipt['blockNumber']}")
                logger.error(f"⛽ Gas使用: {receipt['gasUsed']}")
                logger.error(f"🔗 查看详情: https://bscscan.com/tx/{tx_hash_hex}")
                
                # 尝试解析revert原因
                try:
                    tx_details = self.w3.eth.get_transaction(tx_hash)
                    logger.error(f"📋 交易详情: {tx_details}")
                except Exception as e:
                    logger.error(f"无法获取交易详情: {e}")
                
                return None
                
        except Exception as e:
            logger.error(f"❌ 交易执行失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            
            # 打印详细错误信息
            import traceback
            logger.error(f"详细错误:\n{traceback.format_exc()}")
            
            return None
    
    def get_contract_info(self):
        """获取合约基本信息"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 合约信息")
        logger.info(f"{'='*60}")
        logger.info(f"📍 合约地址: {self.contract_address}")
        
        try:
            # 尝试获取合约名称
            name = self.contract.functions.name().call()
            logger.info(f"📛 名称: {name}")
        except:
            pass
        
        try:
            # 尝试获取合约符号
            symbol = self.contract.functions.symbol().call()
            logger.info(f"🔖 符号: {symbol}")
        except:
            pass
        
        try:
            # 尝试获取小数位数
            decimals = self.contract.functions.decimals().call()
            logger.info(f"🔢 小数位数: {decimals}")
        except:
            pass
        
        try:
            # 尝试获取总供应量
            total_supply = self.contract.functions.totalSupply().call()
            total_supply_formatted = self.w3.from_wei(total_supply, 'ether')
            logger.info(f"📊 总供应量: {total_supply_formatted:.2f}")
        except:
            pass
        
        try:
            # 尝试获取总资产
            total_assets = self.contract.functions.totalAssets().call()
            total_assets_formatted = self.w3.from_wei(total_assets, 'ether')
            logger.info(f"💎 总资产: {total_assets_formatted:.2f}")
        except:
            pass


def run_withdraw_cycle(lista: ListaWithdraw, withdraw_amount: float) -> bool:
    """
    执行一次withdraw周期
    
    Args:
        lista: ListaWithdraw实例
        withdraw_amount: 配置的取出金额
        
    Returns:
        是否成功执行withdraw
    """
    try:
        # 获取最大可取出金额
        max_withdraw = lista.get_max_withdraw()
        
        logger.info(f"💎 最大可取出金额: {max_withdraw:.6f}")
        logger.info(f"⚙️ 配置取出金额: {withdraw_amount:.6f}")
        
        # 检查是否满足取出条件
        if max_withdraw < withdraw_amount:
            logger.warning(f"⚠️ 最大可取出金额 ({max_withdraw:.6f}) 小于配置金额 ({withdraw_amount:.6f})")
            logger.warning(f"⏭️ 跳过本次取出，等待下次检查")
            return False
        
        # 计算实际取出金额
        # 规则：max(最大可取出 * 70%, 配置金额)，但不超过最大可取出 * 90%
        amount_70_percent = max_withdraw * 0.7
        amount_90_percent = max_withdraw * 0.9
        
        # 取70%和配置金额中的较大值
        actual_amount = max(amount_70_percent, withdraw_amount)
        
        # 确保不超过90%
        if actual_amount > amount_90_percent:
            actual_amount = amount_90_percent
        
        logger.info(f"📊 取出金额计算:")
        logger.info(f"   最大可取出 70%: {amount_70_percent:.6f}")
        logger.info(f"   最大可取出 90%: {amount_90_percent:.6f}")
        logger.info(f"   配置取出金额: {withdraw_amount:.6f}")
        logger.info(f"   实际取出金额: {actual_amount:.6f}")
        
        logger.info(f"✅ 满足取出条件，开始执行withdraw操作")
        
        # 执行withdraw
        tx_hash = lista.withdraw(actual_amount)
        
        if tx_hash:
            logger.info(f"✅ 取出操作完成!")
            logger.info(f"🔗 交易链接: https://bscscan.com/tx/{tx_hash}")
            return True
        else:
            logger.error(f"❌ 取出操作失败!")
            return False
    
    except Exception as e:
        logger.error(f"❌ 执行withdraw周期失败: {e}")
        import traceback
        logger.error(f"详细错误:\n{traceback.format_exc()}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Lista MEV合约定期Withdraw工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 每60秒检查一次，每次取出0.5个代币
  python lista_withdraw.py --interval 60 --amount 0.5
  
  # 每30秒检查一次，每次取出1个代币
  python lista_withdraw.py --interval 30 --amount 1.0
  
  # 只执行一次（不循环）
  python lista_withdraw.py --amount 0.5 --once
        """
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=60,
        help='检查间隔时间（秒），默认60秒'
    )
    
    parser.add_argument(
        '--amount', '-a',
        type=float,
        required=True,
        help='每次取出的金额（必需参数）'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='只执行一次，不循环'
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Lista MEV合约定期Withdraw工具")
    logger.info("=" * 60)
    logger.info(f"⚙️ 配置信息:")
    logger.info(f"   检查间隔: {args.interval} 秒")
    logger.info(f"   取出金额: {args.amount}")
    logger.info(f"   运行模式: {'单次执行' if args.once else '循环执行'}")
    logger.info("=" * 60)
    
    try:
        # 创建实例
        lista = ListaWithdraw()
        
        # 显示合约信息
        lista.get_contract_info()
        
        if args.once:
            # 单次执行模式
            logger.info(f"\n🔄 执行单次withdraw检查")
            logger.info("=" * 60)
            success = run_withdraw_cycle(lista, args.amount)
            if success:
                logger.info(f"\n✅ 单次执行完成")
            else:
                logger.info(f"\n⚠️ 单次执行未满足条件或失败")
        else:
            # 循环执行模式
            logger.info(f"\n� 开始循环执行，每 {args.interval} 秒检查一次")
            logger.info(f"💡 按 Ctrl+C 停止程序")
            logger.info("=" * 60)
            
            cycle_count = 0
            success_count = 0
            fail_count = 0
            
            while True:
                cycle_count += 1
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 第 {cycle_count} 次检查 - {current_time}")
                logger.info(f"{'='*60}")
                
                success = run_withdraw_cycle(lista, args.amount)
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                
                logger.info(f"\n📊 统计信息:")
                logger.info(f"   总检查次数: {cycle_count}")
                logger.info(f"   成功取出: {success_count}")
                logger.info(f"   跳过/失败: {fail_count}")
                
                # 等待下次检查
                logger.info(f"\n⏰ 等待 {args.interval} 秒后进行下次检查...")
                logger.info(f"{'='*60}")
                time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info(f"\n\n🛑 收到停止信号，程序退出")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        import traceback
        logger.error(f"详细错误:\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
