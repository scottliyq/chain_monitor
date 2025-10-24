#!/usr/bin/env python3
"""
合约调试工具
分析合约调用失败的原因，包括ABI检查、合约状态分析等
"""

import sys
import os
from web3 import Web3
from decimal import Decimal
import json
import time
from dotenv import load_dotenv
import requests

# 加载环境变量
load_dotenv()

class ContractDebugger:
    def __init__(self):
        """初始化调试器"""
        # 合约地址
        self.CONCRETE_STABLE_ADDRESS = Web3.toChecksumAddress("0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        self.USDT_CONTRACT_ADDRESS = Web3.toChecksumAddress("0xdAC17F958D2ee523a2206206994597C13D831ec7")
        
        # 从环境变量获取配置
        self.rpc_url = self._get_rpc_url()
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        
        print(f"🔍 合约调试工具")
        print(f"🔧 配置信息:")
        print(f"   RPC URL: {self.rpc_url}")
        print(f"   Concrete_STABLE: {self.CONCRETE_STABLE_ADDRESS}")
        print(f"   USDT合约: {self.USDT_CONTRACT_ADDRESS}")
        print(f"   Etherscan API: {'✅' if self.etherscan_api_key else '❌'}")
        print()
        
        # 初始化Web3连接
        self._init_web3()
    
    def _get_rpc_url(self):
        """从环境变量获取RPC URL"""
        rpc_url = os.getenv('WEB3_RPC_URL', 'https://eth.llamarpc.com')
        return rpc_url.strip()
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            provider = Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 30})
            self.web3 = Web3(provider)
            
            chain_id = self.web3.eth.chain_id
            block_number = self.web3.eth.block_number
            
            print(f"✅ 连接成功!")
            print(f"   链ID: {chain_id}")
            print(f"   当前区块: {block_number:,}")
            print()
            
        except Exception as e:
            raise Exception(f"❌ Web3连接失败: {e}")
    
    def get_contract_info_from_etherscan(self, address):
        """从Etherscan获取合约信息"""
        if not self.etherscan_api_key:
            print("⚠️ 未配置Etherscan API密钥，跳过ABI获取")
            return None
        
        try:
            print(f"🔍 从Etherscan获取合约信息: {address}")
            
            # 获取合约ABI
            abi_url = f"https://api.etherscan.io/api?module=contract&action=getabi&address={address}&apikey={self.etherscan_api_key}"
            abi_response = requests.get(abi_url, timeout=10)
            abi_data = abi_response.json()
            
            if abi_data['status'] == '1':
                abi = json.loads(abi_data['result'])
                print(f"✅ 成功获取ABI，包含 {len(abi)} 个函数/事件")
                
                # 分析函数
                functions = [item for item in abi if item['type'] == 'function']
                events = [item for item in abi if item['type'] == 'event']
                
                print(f"   函数数量: {len(functions)}")
                print(f"   事件数量: {len(events)}")
                
                # 查找关键函数
                key_functions = ['deposit', 'withdraw', 'approve', 'transfer']
                found_functions = []
                
                for func in functions:
                    func_name = func['name'].lower()
                    for key_func in key_functions:
                        if key_func in func_name:
                            found_functions.append(func)
                
                if found_functions:
                    print(f"🎯 找到关键函数:")
                    for func in found_functions:
                        inputs = [f"{inp['type']} {inp['name']}" for inp in func.get('inputs', [])]
                        print(f"     {func['name']}({', '.join(inputs)})")
                
                return {
                    'abi': abi,
                    'functions': functions,
                    'events': events,
                    'key_functions': found_functions
                }
            else:
                print(f"❌ 获取ABI失败: {abi_data.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"⚠️ Etherscan API调用失败: {e}")
            return None
    
    def check_contract_code(self, address):
        """检查合约代码"""
        try:
            print(f"🔍 检查合约代码: {address}")
            code = self.web3.eth.get_code(address)
            
            if code == b'':
                print(f"❌ 地址 {address} 不是合约地址")
                return False
            else:
                print(f"✅ 确认是合约地址，代码长度: {len(code)} 字节")
                return True
                
        except Exception as e:
            print(f"❌ 检查合约代码失败: {e}")
            return False
    
    def check_proxy_contract(self, address):
        """检查是否为代理合约"""
        try:
            print(f"🔍 检查代理合约模式: {address}")
            
            # 常见的代理合约存储槽
            proxy_slots = [
                "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",  # EIP-1967
                "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",  # Custom
                "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"   # Another common slot
            ]
            
            for slot in proxy_slots:
                try:
                    storage_value = self.web3.eth.get_storage_at(address, slot)
                    if storage_value != b'\x00' * 32:
                        impl_address = Web3.toChecksumAddress('0x' + storage_value[-20:].hex())
                        if impl_address != '0x' + '00' * 20:
                            print(f"✅ 发现代理合约，实现地址: {impl_address}")
                            return impl_address
                except:
                    continue
            
            print("ℹ️ 不是标准代理合约或无法检测到实现地址")
            return None
            
        except Exception as e:
            print(f"⚠️ 代理合约检查失败: {e}")
            return None
    
    def simulate_deposit_call(self, amount, from_address):
        """模拟deposit调用"""
        try:
            print(f"🧪 模拟deposit调用")
            print(f"   数量: {amount}")
            print(f"   调用地址: {from_address}")
            
            # 基本的deposit函数ABI
            deposit_abi = {
                "constant": False,
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            }
            
            # 创建合约实例
            contract = self.web3.eth.contract(
                address=self.CONCRETE_STABLE_ADDRESS,
                abi=[deposit_abi]
            )
            
            # 转换数量
            amount_raw = int(Decimal(amount) * Decimal(10 ** 6))  # USDT有6位小数
            
            # 模拟调用
            try:
                result = contract.functions.deposit(amount_raw).call({
                    'from': from_address
                })
                print(f"✅ 模拟调用成功，结果: {result}")
                return True
            except Exception as call_error:
                print(f"❌ 模拟调用失败: {call_error}")
                
                # 尝试解析错误信息
                error_str = str(call_error)
                if "revert" in error_str.lower():
                    print(f"💡 交易会被回滚，可能的原因:")
                    print(f"   1. 余额不足")
                    print(f"   2. 授权不足")
                    print(f"   3. 合约暂停")
                    print(f"   4. 不在白名单")
                    print(f"   5. 函数参数错误")
                
                return False
                
        except Exception as e:
            print(f"❌ 模拟调用设置失败: {e}")
            return False
    
    def check_usdt_balance_and_allowance(self, address):
        """检查USDT余额和授权"""
        try:
            print(f"💰 检查USDT状态: {address}")
            
            # USDT合约ABI
            usdt_abi = [
                {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
                {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
            ]
            
            usdt_contract = self.web3.eth.contract(
                address=self.USDT_CONTRACT_ADDRESS,
                abi=usdt_abi
            )
            
            # 查询余额
            balance_raw = usdt_contract.functions.balanceOf(address).call()
            balance = Decimal(balance_raw) / Decimal(10 ** 6)
            
            # 查询授权
            allowance_raw = usdt_contract.functions.allowance(
                address, 
                self.CONCRETE_STABLE_ADDRESS
            ).call()
            allowance = Decimal(allowance_raw) / Decimal(10 ** 6)
            
            print(f"   USDT余额: {balance:,.6f}")
            print(f"   授权额度: {allowance:,.6f}")
            
            return {
                'balance': float(balance),
                'allowance': float(allowance),
                'balance_raw': balance_raw,
                'allowance_raw': allowance_raw
            }
            
        except Exception as e:
            print(f"❌ 检查USDT状态失败: {e}")
            return None
    
    def analyze_failed_transaction(self, tx_hash):
        """分析失败的交易"""
        try:
            print(f"🔍 分析失败交易: {tx_hash}")
            
            # 获取交易收据
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                tx = self.web3.eth.get_transaction(tx_hash)
                
                print(f"📊 交易信息:")
                print(f"   状态: {'成功' if receipt.status == 1 else '失败'}")
                print(f"   Gas限制: {tx.gas:,}")
                print(f"   Gas使用: {receipt.gasUsed:,}")
                print(f"   Gas价格: {Web3.fromWei(tx.gasPrice, 'gwei'):.2f} Gwei")
                print(f"   从地址: {tx['from']}")
                print(f"   到地址: {tx.to}")
                print(f"   数值: {Web3.fromWei(tx.value, 'ether'):.6f} ETH")
                print(f"   输入数据长度: {len(tx.input)} 字节")
                
                if receipt.status == 0:
                    print(f"❌ 交易失败，可能原因:")
                    print(f"   1. Gas不足")
                    print(f"   2. 合约函数revert")
                    print(f"   3. 权限不足")
                    print(f"   4. 参数错误")
                
                return receipt, tx
                
            except Exception as e:
                print(f"❌ 获取交易信息失败: {e}")
                return None, None
                
        except Exception as e:
            print(f"❌ 分析交易失败: {e}")
            return None, None
    
    def comprehensive_debug(self, deposit_amount, from_address):
        """综合调试分析"""
        print(f"🔬 开始综合调试分析")
        print(f"=" * 60)
        
        # 1. 检查合约代码
        print(f"📍 步骤 1: 合约代码检查")
        concrete_is_contract = self.check_contract_code(self.CONCRETE_STABLE_ADDRESS)
        usdt_is_contract = self.check_contract_code(self.USDT_CONTRACT_ADDRESS)
        print()
        
        # 2. 检查代理合约
        print(f"📍 步骤 2: 代理合约检查")
        impl_address = self.check_proxy_contract(self.CONCRETE_STABLE_ADDRESS)
        print()
        
        # 3. 获取合约ABI
        print(f"📍 步骤 3: 获取合约ABI")
        concrete_info = self.get_contract_info_from_etherscan(self.CONCRETE_STABLE_ADDRESS)
        if impl_address:
            impl_info = self.get_contract_info_from_etherscan(impl_address)
        print()
        
        # 4. 检查USDT状态
        print(f"📍 步骤 4: USDT余额和授权检查")
        usdt_status = self.check_usdt_balance_and_allowance(from_address)
        print()
        
        # 5. 模拟函数调用
        print(f"📍 步骤 5: 模拟deposit调用")
        simulation_result = self.simulate_deposit_call(deposit_amount, from_address)
        print()
        
        # 6. 生成调试报告
        print(f"📊 调试报告摘要")
        print(f"=" * 60)
        print(f"✅ Concrete_STABLE是合约: {concrete_is_contract}")
        print(f"✅ USDT是合约: {usdt_is_contract}")
        print(f"🔄 检测到代理合约: {impl_address is not None}")
        print(f"📜 获取到ABI: {concrete_info is not None}")
        if usdt_status:
            print(f"💰 USDT余额充足: {usdt_status['balance'] >= deposit_amount}")
            print(f"✅ 授权额度充足: {usdt_status['allowance'] >= deposit_amount}")
        print(f"🧪 模拟调用成功: {simulation_result}")
        
        return {
            'contracts_valid': concrete_is_contract and usdt_is_contract,
            'proxy_detected': impl_address,
            'abi_available': concrete_info is not None,
            'usdt_status': usdt_status,
            'simulation_success': simulation_result
        }

def main():
    """主函数"""
    print("🔬 合约调试工具")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("📖 使用方法:")
        print(f"  python {sys.argv[0]} debug <amount> <address>")
        print(f"  python {sys.argv[0]} analyze <tx_hash>")
        print(f"  python {sys.argv[0]} info <contract_address>")
        print()
        print("📝 示例:")
        print(f"  python {sys.argv[0]} debug 100 0xF977814e90dA44bFA03b6295A0616a897441aceC")
        print(f"  python {sys.argv[0]} analyze 0x1234...5678")
        print(f"  python {sys.argv[0]} info 0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        return
    
    debugger = ContractDebugger()
    operation = sys.argv[1].lower()
    
    try:
        if operation == "debug":
            if len(sys.argv) < 4:
                print("❌ 请提供数量和地址")
                return
            
            amount = float(sys.argv[2])
            address = Web3.toChecksumAddress(sys.argv[3])
            
            result = debugger.comprehensive_debug(amount, address)
            
        elif operation == "analyze":
            if len(sys.argv) < 3:
                print("❌ 请提供交易哈希")
                return
            
            tx_hash = sys.argv[2]
            debugger.analyze_failed_transaction(tx_hash)
            
        elif operation == "info":
            if len(sys.argv) < 3:
                print("❌ 请提供合约地址")
                return
            
            address = Web3.toChecksumAddress(sys.argv[2])
            debugger.check_contract_code(address)
            debugger.check_proxy_contract(address)
            debugger.get_contract_info_from_etherscan(address)
            
        else:
            print(f"❌ 未知操作: {operation}")
            
    except Exception as e:
        print(f"❌ 调试失败: {e}")

if __name__ == "__main__":
    main()