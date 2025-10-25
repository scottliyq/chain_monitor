#!/usr/bin/env python3
"""
简化的合约函数调试工具
尝试不同的存款函数调用方式
"""

import sys
import os
from web3 import Web3
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

class SimpleDebugger:
    def __init__(self, mock_mode=False):
        self.CONCRETE_STABLE_ADDRESS = Web3.toChecksumAddress("0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        self.USDT_CONTRACT_ADDRESS = Web3.toChecksumAddress("0xdAC17F958D2ee523a2206206994597C13D831ec7")
        
        self.mock_mode = mock_mode
        self.rpc_url = os.getenv('WEB3_RPC_URL', 'http://127.0.0.1:8545')
        
        if mock_mode:
            self.wallet_address = Web3.toChecksumAddress(os.getenv('MOCK_WALLET_ADDRESS', '0xF977814e90dA44bFA03b6295A0616a897441aceC'))
        else:
            from eth_account import Account
            private_key = os.getenv('WALLET_PRIVATE_KEY')
            self.account = Account.from_key(private_key)
            self.wallet_address = self.account.address
        
        # 初始化Web3
        provider = Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 30})
        self.web3 = Web3(provider)
        
        print(f"🔧 连接到: {self.rpc_url}")
        print(f"💼 钱包地址: {self.wallet_address}")
        print(f"🎭 Mock模式: {mock_mode}")
        
        if mock_mode:
            self._enable_impersonate()
    
    def _enable_impersonate(self):
        """启用Impersonate模式"""
        try:
            self.web3.provider.make_request("hardhat_impersonateAccount", [self.wallet_address])
            print(f"✅ 成功impersonate地址")
        except:
            print(f"⚠️ Impersonate可能失败（正常情况）")
    
    def try_different_deposit_functions(self, amount):
        """尝试不同的存款函数"""
        amount_raw = int(Decimal(amount) * Decimal(10 ** 6))  # USDT 6位小数
        
        print(f"🧪 测试不同的存款函数，数量: {amount} USDT ({amount_raw} raw)")
        print()
        
        # 可能的函数签名
        test_functions = [
            # 基本deposit函数
            {
                "name": "deposit(uint256)",
                "abi": {"constant": False, "inputs": [{"name": "amount", "type": "uint256"}], "name": "deposit", "outputs": [], "type": "function"},
                "params": [amount_raw]
            },
            # 带接收地址的deposit
            {
                "name": "deposit(uint256,address)",
                "abi": {"constant": False, "inputs": [{"name": "amount", "type": "uint256"}, {"name": "to", "type": "address"}], "name": "deposit", "outputs": [], "type": "function"},
                "params": [amount_raw, self.wallet_address]
            },
            # USDT代币地址的deposit
            {
                "name": "deposit(address,uint256)",
                "abi": {"constant": False, "inputs": [{"name": "token", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "deposit", "outputs": [], "type": "function"},
                "params": [self.USDT_CONTRACT_ADDRESS, amount_raw]
            },
            # ERC4626风格的deposit
            {
                "name": "deposit(uint256,address)",
                "abi": {"constant": False, "inputs": [{"name": "assets", "type": "uint256"}, {"name": "receiver", "type": "address"}], "name": "deposit", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
                "params": [amount_raw, self.wallet_address]
            }
        ]
        
        for i, func_test in enumerate(test_functions, 1):
            print(f"📍 测试 {i}: {func_test['name']}")
            
            try:
                # 创建合约实例
                contract = self.web3.eth.contract(
                    address=self.CONCRETE_STABLE_ADDRESS,
                    abi=[func_test['abi']]
                )
                
                # 尝试调用
                function_call = getattr(contract.functions, func_test['abi']['name'])(*func_test['params'])
                
                # 模拟调用
                try:
                    result = function_call.call({'from': self.wallet_address})
                    print(f"   ✅ 模拟调用成功: {result}")
                    
                    # 如果模拟成功，尝试实际交易
                    print(f"   🚀 尝试实际交易...")
                    txn = function_call.build_transaction({
                        'from': self.wallet_address,
                        'gas': 300000,
                        'gasPrice': self.web3.eth.gas_price,
                        'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                        'chainId': self.web3.eth.chain_id
                    })
                    
                    if self.mock_mode:
                        tx_hash = self.web3.eth.send_transaction(txn)
                    else:
                        signed_txn = self.web3.eth.account.sign_transaction(txn, os.getenv('WALLET_PRIVATE_KEY'))
                        tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    
                    print(f"   ✅ 交易发送成功: {tx_hash.hex()}")
                    
                    # 等待确认
                    receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                    if receipt.status == 1:
                        print(f"   🎉 交易确认成功! Gas使用: {receipt.gasUsed:,}")
                        return True
                    else:
                        print(f"   ❌ 交易失败")
                    
                except Exception as call_error:
                    print(f"   ❌ 调用失败: {call_error}")
                    
            except Exception as e:
                print(f"   ❌ 函数不存在或参数错误: {e}")
            
            print()
        
        return False
    
    def check_contract_functions(self):
        """检查合约的可用函数"""
        print(f"🔍 尝试检测合约函数...")
        
        # 常见的函数选择器
        common_selectors = {
            "0xb6b55f25": "deposit(uint256)",
            "0xe2bbb158": "deposit(uint256,address)", 
            "0x47e7ef24": "deposit(address,uint256)",
            "0x6e553f65": "deposit(uint256,address)",  # ERC4626
            "0xa9059cbb": "transfer(address,uint256)",
            "0x095ea7b3": "approve(address,uint256)",
            "0x70a08231": "balanceOf(address)"
        }
        
        print(f"📋 检查常见函数选择器:")
        for selector, signature in common_selectors.items():
            try:
                # 构造调用数据
                call_data = selector + "0" * 56  # 加上32字节的零参数
                
                result = self.web3.eth.call({
                    'to': self.CONCRETE_STABLE_ADDRESS,
                    'data': call_data
                })
                print(f"   ✅ {signature}: 可能存在")
            except Exception as e:
                error_msg = str(e)
                if "revert" in error_msg.lower():
                    print(f"   🔄 {signature}: 存在但参数错误")
                else:
                    print(f"   ❌ {signature}: 不存在")

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python simple_debug.py test <amount> [--mock]")
        print("  python simple_debug.py functions [--mock]")
        print()
        print("示例:")
        print("  python simple_debug.py test 100 --mock")
        print("  python simple_debug.py functions --mock")
        return
    
    args = sys.argv[1:]
    mock_mode = '--mock' in args
    if mock_mode:
        args.remove('--mock')
    
    operation = args[0] if args else 'test'
    
    debugger = SimpleDebugger(mock_mode=mock_mode)
    
    if operation == "test":
        amount = float(args[1]) if len(args) > 1 else 100.0
        debugger.try_different_deposit_functions(amount)
    elif operation == "functions":
        debugger.check_contract_functions()

if __name__ == "__main__":
    main()