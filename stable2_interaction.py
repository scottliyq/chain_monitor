#!/usr/bin/env python3
"""
Stable2 合约交互工具
支持真实签名模式和mock模式（Impersonate）
动态获取合约ABI，使用ERC4626标准的deposit(uint256 assets, address receiver)方法
合约地址: 0xd9b2CB2FBAD204Fc548787EF56B918c845FCce40
"""

import sys
import os
from web3 import Web3
from decimal import Decimal
import json
import time
import requests
import glob
from typing import Optional
from dotenv import load_dotenv
from eth_account import Account

# 加载环境变量
load_dotenv()

class Stable2Interaction:
    def __init__(self, mock_mode=False, preprod_mode=False):
        """初始化合约交互器
        
        Args:
            mock_mode (bool): 是否使用mock模式（Impersonate）
            preprod_mode (bool): 是否使用preprod模式（本地RPC + 真实签名）
        """
        # 合约地址
        self.STABLE2_ADDRESS = Web3.to_checksum_address("0xd9b2CB2FBAD204Fc548787EF56B918c845FCce40")
        self.USDC_CONTRACT_ADDRESS = Web3.to_checksum_address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
        
        # 模式设置
        self.mock_mode = mock_mode
        self.preprod_mode = preprod_mode
        
        # 确保不会同时启用两种模式
        if mock_mode and preprod_mode:
            raise ValueError("❌ 不能同时启用mock模式和preprod模式")
        
        # Etherscan API配置
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.etherscan_api_url = "https://api.etherscan.io/v2/api"  # 使用v2 API
        
        # 从环境变量获取配置
        if mock_mode:
            self.wallet_address = self._get_mock_wallet_address()
            self.private_key = None
            self.account = None
            print(f"🎭 Mock模式 - 使用Impersonate")
        elif preprod_mode:
            self.private_key = self._get_private_key()
            self.account = Account.from_key(self.private_key)
            self.wallet_address = self.account.address
            print(f"🧪 Preprod模式 - 真实签名 + 本地RPC")
        else:
            self.private_key = self._get_private_key()
            self.account = Account.from_key(self.private_key)
            self.wallet_address = self.account.address
            print(f"🔐 真实签名模式")
            
        self.rpc_url = self._get_rpc_url()
        self.network_id = self._get_network_id()
        
        print(f"🔧 配置信息:")
        print(f"   RPC URL: {self.rpc_url}")
        print(f"   Network ID: {self.network_id}")
        print(f"   Stable2合约: {self.STABLE2_ADDRESS}")
        print(f"   USDC合约: {self.USDC_CONTRACT_ADDRESS}")
        print(f"   钱包地址: {self.wallet_address}")
        print()
        
        self.web3 = None
        self.usdc_contract = None
        self.stable2_contract = None
        self.stable2_abi = None
        self.usdc_abi = None
        
        self._init_web3()
        
        # 动态获取合约ABI并初始化合约
        self._get_contract_abis()
        self._init_contracts()
        
        # 如果是mock模式，启用impersonate
        if self.mock_mode:
            self._enable_impersonate()
    
    def _get_mock_wallet_address(self):
        """从环境变量获取Mock模式下的钱包地址"""
        wallet_address = os.getenv('MOCK_WALLET_ADDRESS')
        if not wallet_address:
            # 默认使用一个有大量USDC的地址（Binance热钱包）
            wallet_address = "0xF977814e90dA44bFA03b6295A0616a897441aceC"
            print(f"⚠️ 未设置MOCK_WALLET_ADDRESS，使用默认地址: {wallet_address}")
        
        return Web3.to_checksum_address(wallet_address)
    
    def _get_private_key(self):
        """从环境变量获取私钥"""
        private_key = os.getenv('WALLET_PRIVATE_KEY')
        if not private_key:
            raise ValueError("❌ 未找到私钥配置，请在.env文件中设置 WALLET_PRIVATE_KEY")
        
        # 检查是否是占位符
        if private_key == "0x1234...5678" or "..." in private_key:
            raise ValueError("❌ 请将WALLET_PRIVATE_KEY替换为真实的私钥")
        
        # 确保私钥格式正确
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        return private_key
    
    def _get_rpc_url(self):
        """从环境变量获取RPC URL"""
        # Mock模式和Preprod模式都优先使用 MOCK_WEB3_RPC_URL
        if self.mock_mode or self.preprod_mode:
            mock_rpc_url = os.getenv('MOCK_WEB3_RPC_URL')
            if mock_rpc_url:
                return mock_rpc_url.strip()
            else:
                mode_name = "Mock模式" if self.mock_mode else "Preprod模式"
                print(f"⚠️ {mode_name}下未找到MOCK_WEB3_RPC_URL，使用默认的本地节点")
                return "http://127.0.0.1:8545"
        
        # 真实模式下使用 WEB3_RPC_URL
        rpc_url = os.getenv('WEB3_RPC_URL')
        if not rpc_url:
            # 备选方案
            if os.getenv('WEB3_ALCHEMY_PROJECT_ID'):
                return f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('WEB3_ALCHEMY_PROJECT_ID')}"
            elif os.getenv('WEB3_INFURA_PROJECT_ID'):
                return f"https://mainnet.infura.io/v3/{os.getenv('WEB3_INFURA_PROJECT_ID')}"
            else:
                raise ValueError("❌ 未找到RPC URL配置，请在.env文件中设置 WEB3_RPC_URL")
        
        return rpc_url.strip()
    
    def _get_network_id(self):
        """从环境变量获取Network ID"""
        network_id = os.getenv('WEB3_NETWORK_ID', '1')  # 默认为主网
        try:
            return int(network_id)
        except ValueError:
            print(f"⚠️ 无效的Network ID: {network_id}，使用默认值: 1")
            return 1
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            print(f"🔄 连接到RPC节点...")
            
            # 设置连接超时
            provider = Web3.HTTPProvider(
                self.rpc_url,
                request_kwargs={'timeout': 30}
            )
            self.web3 = Web3(provider)
            
            # 检查连接
            try:
                chain_id = self.web3.eth.chain_id
                block_number = self.web3.eth.block_number
                
                print(f"✅ 连接成功!")
                print(f"   链ID: {chain_id}")
                print(f"   当前区块: {block_number:,}")
                
                # 检查网络ID是否匹配
                if chain_id != self.network_id:
                    print(f"⚠️ 网络ID不匹配! 配置: {self.network_id}, 实际: {chain_id}")
                    
            except Exception as conn_error:
                raise Exception(f"连接验证失败: {conn_error}")
            
        except Exception as e:
            raise Exception(f"❌ Web3连接失败: {e}")
    
    def _get_contract_abi(self, contract_address, contract_name=""):
        """从Etherscan v2 API获取合约ABI"""
        try:
            print(f"🔍 正在从Etherscan v2 API获取{contract_name}合约ABI: {contract_address}")
            
            # Etherscan v2 API 参数
            params = {
                'chainid': 1,  # 以太坊主网
                'module': 'contract',
                'action': 'getabi',
                'address': contract_address,
                'apikey': self.etherscan_api_key
            }
            
            # 设置更合适的请求头
            headers = {
                'User-Agent': 'Stable2_Interaction_Tool/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                self.etherscan_api_url, 
                params=params, 
                headers=headers,
                timeout=15
            )
            
            # 检查HTTP状态码
            if response.status_code != 200:
                print(f"⚠️ HTTP请求失败: {response.status_code}")
                return None
                
            data = response.json()
            
            if data.get('status') == '1' and data.get('result'):
                try:
                    abi = json.loads(data['result'])
                    print(f"✅ 成功从v2 API获取{contract_name}ABI，包含 {len(abi)} 个函数")
                    return abi
                except json.JSONDecodeError as e:
                    print(f"⚠️ ABI数据格式错误: {e}")
                    return None
            else:
                # 详细的错误分析
                error_msg = data.get('message', 'Unknown error')
                result_msg = data.get('result', '')
                status = data.get('status', '')
                
                print(f"⚠️ Etherscan v2 API返回错误:")
                print(f"   状态: {status}")
                print(f"   消息: {error_msg}")
                
                if result_msg:
                    # 分析具体错误类型
                    if 'NOTOK' in str(status):
                        if 'rate limit' in str(result_msg).lower():
                            print(f"   📝 API频率限制，请稍后重试")
                        elif 'invalid api key' in str(result_msg).lower():
                            print(f"   🔑 API密钥无效")
                            print(f"   💡 提示: 请检查 .env 文件中的 ETHERSCAN_API_KEY")
                        elif 'contract source code not verified' in str(result_msg).lower():
                            print(f"   📋 合约源代码未在Etherscan验证")
                        elif 'max rate limit reached' in str(result_msg).lower():
                            print(f"   ⏰ 达到最大请求频率限制")
                        else:
                            print(f"   详细: {result_msg}")
                    
                return None
                
        except Exception as e:
            print(f"⚠️ 获取合约ABI失败: {e}")
            return None
    
    def _find_local_abi_file(self, contract_address, contract_name=""):
        """在本地abi目录查找ABI文件"""
        try:
            # 规范化地址（不带0x前缀，小写）
            addr_normalized = contract_address.lower().replace('0x', '')
            
            # 查找abi目录
            abi_dir = os.path.join(os.path.dirname(__file__), 'abi')
            
            if not os.path.exists(abi_dir):
                print(f"⚠️ abi目录不存在: {abi_dir}")
                return None
            
            # 搜索模式：
            # 1. ethereum_stable2_0x{address}.json
            # 2. stable2_0x{address}.json  
            # 3. *{address}*.json
            patterns = [
                f"ethereum_stable2_0x{addr_normalized}.json",
                f"ethereum_stable2_{contract_address}.json",
                f"stable2_0x{addr_normalized}.json",
                f"stable2_{contract_address}.json",
                f"*{addr_normalized}*.json"
            ]
            
            for pattern in patterns:
                search_path = os.path.join(abi_dir, pattern)
                matching_files = glob.glob(search_path, recursive=False)
                
                if matching_files:
                    abi_file = matching_files[0]
                    print(f"✅ 找到本地ABI文件: {os.path.basename(abi_file)}")
                    
                    with open(abi_file, 'r', encoding='utf-8') as f:
                        abi_data = json.load(f)
                        
                    # 处理可能的ABI文件格式
                    if isinstance(abi_data, dict):
                        if 'abi' in abi_data:
                            abi = abi_data['abi']
                        elif 'result' in abi_data:
                            abi = json.loads(abi_data['result']) if isinstance(abi_data['result'], str) else abi_data['result']
                        else:
                            abi = abi_data
                    else:
                        abi = abi_data
                    
                    print(f"   包含 {len(abi)} 个函数/事件")
                    return abi
            
            print(f"⚠️ 未找到{contract_name}的本地ABI文件")
            return None
            
        except Exception as e:
            print(f"⚠️ 读取本地ABI文件失败: {e}")
            return None
    
    def _get_contract_abis(self):
        """获取合约ABI（优先使用本地文件，失败则从Etherscan获取）"""
        print(f"\n🔍 获取合约ABI...")
        print(f"{'='*50}")
        
        # 获取Stable2合约ABI
        print(f"📋 Stable2合约:")
        self.stable2_abi = self._find_local_abi_file(self.STABLE2_ADDRESS, "Stable2")
        if not self.stable2_abi:
            print(f"   尝试从Etherscan获取...")
            self.stable2_abi = self._get_contract_abi(self.STABLE2_ADDRESS, "Stable2")
        
        if not self.stable2_abi:
            raise Exception("无法获取Stable2合约ABI")
        
        # 获取USDC合约ABI
        print(f"\n📋 USDC合约:")
        self.usdc_abi = self._find_local_abi_file(self.USDC_CONTRACT_ADDRESS, "USDC")
        if not self.usdc_abi:
            print(f"   尝试从Etherscan获取...")
            self.usdc_abi = self._get_contract_abi(self.USDC_CONTRACT_ADDRESS, "USDC")
        
        if not self.usdc_abi:
            raise Exception("无法获取USDC合约ABI")
        
        print(f"{'='*50}\n")
    
    def _init_contracts(self):
        """初始化合约实例"""
        try:
            print(f"🔄 初始化合约实例...")
            
            # 初始化Stable2合约
            self.stable2_contract = self.web3.eth.contract(
                address=self.STABLE2_ADDRESS,
                abi=self.stable2_abi
            )
            print(f"✅ Stable2合约已初始化")
            
            # 初始化USDC合约
            self.usdc_contract = self.web3.eth.contract(
                address=self.USDC_CONTRACT_ADDRESS,
                abi=self.usdc_abi
            )
            print(f"✅ USDC合约已初始化")
            print()
            
        except Exception as e:
            raise Exception(f"初始化合约失败: {e}")
    
    def _enable_impersonate(self):
        """启用Impersonate模式（Anvil/Hardhat）"""
        try:
            print(f"🎭 启用Impersonate模式...")
            print(f"   目标地址: {self.wallet_address}")
            
            # 使用 anvil_impersonateAccount
            result = self.web3.provider.make_request(
                'anvil_impersonateAccount',
                [self.wallet_address]
            )
            
            if 'error' in result:
                raise Exception(f"Impersonate失败: {result['error']}")
            
            print(f"✅ Impersonate模式已启用")
            print()
            
        except Exception as e:
            print(f"⚠️ 启用Impersonate失败: {e}")
            print(f"   请确保使用支持impersonate的本地节点（Anvil/Hardhat）")
            raise
    
    def _build_transaction(self, contract_function, gas_limit=None):
        """构建交易"""
        try:
            # 获取nonce
            nonce = self.web3.eth.get_transaction_count(self.wallet_address)
            
            # 获取gas price
            gas_price = self.web3.eth.gas_price
            
            # 构建交易基础参数
            txn_params = {
                'from': self.wallet_address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'chainId': self.network_id
            }
            
            # 估算gas或使用指定的gas limit
            if gas_limit:
                txn_params['gas'] = gas_limit
            else:
                estimated_gas = contract_function.estimate_gas(txn_params)
                txn_params['gas'] = int(estimated_gas * 1.2)  # 增加20%缓冲
            
            # 构建完整交易
            txn = contract_function.build_transaction(txn_params)
            
            return txn
            
        except Exception as e:
            raise Exception(f"构建交易失败: {e}")
    
    def _send_transaction(self, txn):
        """发送交易"""
        try:
            if self.mock_mode:
                # Mock模式：直接发送交易（不签名）
                tx_hash = self.web3.eth.send_transaction(txn)
            else:
                # 真实模式：签名后发送
                signed_txn = self.web3.eth.account.sign_transaction(txn, self.private_key)
                # 兼容不同版本的web3.py：raw_transaction (新版) 或 rawTransaction (旧版)
                raw_tx = getattr(signed_txn, 'raw_transaction', None) or getattr(signed_txn, 'rawTransaction', None)
                if raw_tx is None:
                    raise Exception("无法获取签名后的原始交易数据")
                tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
            
            print(f"📤 交易已发送: {tx_hash.hex()}")
            return tx_hash
            
        except Exception as e:
            raise Exception(f"发送交易失败: {e}")
    
    def get_balances(self):
        """获取账户余额信息"""
        try:
            # ETH余额
            eth_balance = self.web3.eth.get_balance(self.wallet_address)
            eth_balance_ether = Web3.from_wei(eth_balance, 'ether')
            
            # USDC余额
            usdc_balance_raw = self.usdc_contract.functions.balanceOf(self.wallet_address).call()
            usdc_decimals = self.usdc_contract.functions.decimals().call()
            usdc_balance = float(Decimal(usdc_balance_raw) / Decimal(10 ** usdc_decimals))
            
            # USDC授权额度
            allowance_raw = self.usdc_contract.functions.allowance(
                self.wallet_address,
                self.STABLE2_ADDRESS
            ).call()
            allowance = float(Decimal(allowance_raw) / Decimal(10 ** usdc_decimals))
            
            return {
                'eth_balance': float(eth_balance_ether),
                'usdc_balance': usdc_balance,
                'allowance': allowance
            }
            
        except Exception as e:
            raise Exception(f"获取余额失败: {e}")
    
    def approve_usdc(self, amount=None):
        """授权USDC到Stable2合约
        
        Args:
            amount: 授权数量，如果为None则授权最大值
        """
        try:
            print(f"🔄 准备授权USDC到Stable2合约...")
            
            if amount is None:
                # 使用uint256最大值
                amount_raw = 2**256 - 1
                print(f"   授权数量: 最大值 (2^256-1)")
            else:
                usdc_decimals = self.usdc_contract.functions.decimals().call()
                amount_raw = int(Decimal(amount) * Decimal(10 ** usdc_decimals))
                print(f"   授权数量: {amount:,.6f} USDC")
            
            # 构建交易
            approve_txn = self._build_transaction(
                self.usdc_contract.functions.approve(
                    self.STABLE2_ADDRESS,
                    amount_raw
                ),
                gas_limit=100000
            )
            
            print(f"   交易详情:")
            print(f"     Gas: {approve_txn['gas']:,}")
            print(f"     Gas Price: {Web3.from_wei(approve_txn['gasPrice'], 'gwei'):.2f} Gwei")
            print(f"     预估费用: {Web3.from_wei(approve_txn['gas'] * approve_txn['gasPrice'], 'ether'):.6f} ETH")
            
            # 发送交易
            tx_hash = self._send_transaction(approve_txn)
            
            # 等待确认
            print(f"⏳ 等待交易确认...")
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if tx_receipt.status == 1:
                print(f"✅ 授权交易成功!")
                print(f"   区块号: {tx_receipt.blockNumber}")
                print(f"   实际Gas使用: {tx_receipt.gasUsed:,}")
                return tx_receipt
            else:
                raise Exception("授权交易失败")
                
        except Exception as e:
            raise Exception(f"授权USDC失败: {e}")
    
    def deposit_usdc(self, amount):
        """存款USDC到Stable2合约
        使用ERC4626标准的deposit函数: deposit(uint256 assets, address receiver)
        """
        try:
            print(f"🔄 准备存款 {amount:,.6f} USDC...")
            print(f"   使用ERC4626标准函数: deposit(uint256 assets, address receiver)")
            
            # 转换为合约单位
            usdc_decimals = self.usdc_contract.functions.decimals().call()
            amount_raw = int(Decimal(amount) * Decimal(10 ** usdc_decimals))
            
            print(f"   存款数量: {amount:,.6f} USDC ({amount_raw} raw)")
            print(f"   接收地址: {self.wallet_address}")
            
            # 检查余额和授权
            balances = self.get_balances()
            if balances['usdc_balance'] < amount:
                raise Exception(f"USDC余额不足: {balances['usdc_balance']:.6f} < {amount:.6f}")
            
            if balances['allowance'] < amount:
                raise Exception(f"授权额度不足: {balances['allowance']:.6f} < {amount:.6f}")
            
            # 使用ERC4626的deposit函数：deposit(uint256 assets, address receiver)
            contract_function = self.stable2_contract.functions.deposit(amount_raw, self.wallet_address)
            
            # 先进行模拟调用来检查是否会成功
            try:
                print(f"   🧪 进行模拟调用...")
                simulation_result = contract_function.call({'from': self.wallet_address})
                print(f"   ✅ 模拟调用成功，预期返回: {simulation_result}")
            except Exception as sim_error:
                print(f"   ❌ 模拟调用失败: {sim_error}")
                # 尝试预览deposit来获取更多信息
                try:
                    if any(func['name'] == 'previewDeposit' for func in self.stable2_abi):
                        preview_result = self.stable2_contract.functions.previewDeposit(amount_raw).call()
                        print(f"   💡 预览存款结果: {preview_result} shares")
                except:
                    pass
                raise Exception(f"存款模拟失败，交易可能会revert: {sim_error}")
            
            # 构建交易
            deposit_txn = self._build_transaction(
                contract_function,
                gas_limit=300000  # 增加gas限制
            )
            
            print(f"   交易详情:")
            print(f"     Gas: {deposit_txn['gas']:,}")
            print(f"     Gas Price: {Web3.from_wei(deposit_txn['gasPrice'], 'gwei'):.2f} Gwei")
            print(f"     预估费用: {Web3.from_wei(deposit_txn['gas'] * deposit_txn['gasPrice'], 'ether'):.6f} ETH")
            
            # 发送交易
            tx_hash = self._send_transaction(deposit_txn)
            
            # 等待确认
            print(f"⏳ 等待交易确认...")
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if tx_receipt.status == 1:
                print(f"✅ 存款交易成功!")
                print(f"   区块号: {tx_receipt.blockNumber}")
                print(f"   实际Gas使用: {tx_receipt.gasUsed:,}")
                
                # 显示交易日志
                if tx_receipt.logs:
                    print(f"   交易日志数量: {len(tx_receipt.logs)}")
                    for i, log in enumerate(tx_receipt.logs):
                        print(f"     日志 {i+1}: {log.topics[0].hex() if log.topics else 'No topics'}")
                
                return tx_receipt
            else:
                raise Exception("存款交易失败")
                
        except Exception as e:
            raise Exception(f"存款USDC失败: {e}")
    
    def display_balances(self, balances):
        """显示余额信息"""
        print(f"📊 当前账户状态")
        print(f"{'='*50}")
        print(f"🏠 钱包地址: {self.wallet_address}")
        print(f"💰 USDC余额: {balances['usdc_balance']:,.6f} USDC")
        print(f"⛽ ETH余额: {balances['eth_balance']:.6f} ETH")
        print(f"✅ 授权额度: {balances['allowance']:,.6f} USDC")
        print(f"{'='*50}")

    def show_config(self):
        """显示配置信息"""
        from datetime import datetime
        
        print(f"\n🔧 当前配置信息")
        print(f"{'='*50}")
        
        # 运行模式
        if self.mock_mode:
            mode_text = "🎭 Mock模式（Impersonate）"
        elif self.preprod_mode:
            mode_text = "🧪 Preprod模式（本地RPC + 真实签名）"
        else:
            mode_text = "🔐 真实签名模式"
        
        print(f"🎯 运行模式: {mode_text}")
        print(f"🌐 RPC URL: {self.rpc_url}")
        print(f"🔗 网络ID: {self.network_id}")
        print(f"📍 钱包地址: {self.wallet_address}")
        print(f"🏦 Stable2合约: {self.STABLE2_ADDRESS}")
        print(f"💰 USDC合约: {self.USDC_CONTRACT_ADDRESS}")
        
        # 检查存款窗口期
        try:
            deposit_start = self.stable2_contract.functions.depositStart().call()
            deposit_end = self.stable2_contract.functions.depositEnd().call()
            current_time = self.web3.eth.get_block('latest')['timestamp']
            max_deposit = self.stable2_contract.functions.maxDeposit().call()
            deposit_cap = self.stable2_contract.functions.depositCap().call()
            
            print(f"\n⏰ 存款窗口期信息")
            print(f"{'='*50}")
            print(f"📅 开始时间: {datetime.fromtimestamp(deposit_start).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"📅 结束时间: {datetime.fromtimestamp(deposit_end).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"🕐 当前时间: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            if current_time < deposit_start:
                wait_seconds = deposit_start - current_time
                wait_minutes = wait_seconds // 60
                print(f"❌ 状态: 存款窗口尚未开启")
                print(f"⏳ 还需等待: {wait_minutes} 分钟 ({wait_seconds} 秒)")
            elif current_time > deposit_end:
                print(f"❌ 状态: 存款窗口已关闭")
            else:
                remain_seconds = deposit_end - current_time
                remain_hours = remain_seconds // 3600
                print(f"✅ 状态: 存款窗口开放中")
                print(f"⏳ 剩余时间: {remain_hours} 小时")
            
            print(f"\n� 存款限额")
            print(f"{'='*50}")
            print(f"📊 合约存款上限: {deposit_cap / 1e6:,.2f} USDC")
            print(f"💰 当前可存款额度: {max_deposit / 1e6:,.2f} USDC")
            
            if max_deposit == 0:
                print(f"⚠️  警告: 当前无法存款（窗口未开启或已达上限）")
        except Exception as e:
            print(f"\n⚠️  无法获取存款窗口信息: {e}")

def main():
    """主函数"""
    print(f"🚀 Stable2合约交互工具")
    print(f"{'='*50}")
    print(f"合约地址: 0xd9b2CB2FBAD204Fc548787EF56B918c845FCce40")
    print(f"{'='*50}\n")
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python stable2_interaction.py <operation> [args]")
        print()
        print("操作:")
        print("  balance                    - 查看账户余额")
        print("  approve [amount]           - 授权USDC（不指定amount则授权最大值）")
        print("  deposit <amount>           - 存款USDC")
        print("  all <amount>               - 完整流程: 授权 + 存款")
        print("  config                     - 显示配置信息")
        print()
        print("模式选项:")
        print("  --mock                     - 使用Mock模式（Impersonate）")
        print("  --preprod                  - 使用Preprod模式（本地RPC + 真实签名）")
        print()
        print("示例:")
        print("  python stable2_interaction.py balance")
        print("  python stable2_interaction.py approve")
        print("  python stable2_interaction.py deposit 100")
        print("  python stable2_interaction.py all 100")
        print("  python stable2_interaction.py --mock balance")
        print("  python stable2_interaction.py --preprod deposit 100")
        sys.exit(1)
    
    try:
        # 解析命令行参数
        args = sys.argv[1:]
        
        # 检查模式选项
        mock_mode = '--mock' in args
        preprod_mode = '--preprod' in args
        
        # 移除模式标志
        args = [arg for arg in args if arg not in ['--mock', '--preprod']]
        
        if len(args) < 1:
            print("❌ 请指定操作")
            sys.exit(1)
        
        operation = args[0].lower()
        
        # 创建交互器实例
        interactor = Stable2Interaction(mock_mode=mock_mode, preprod_mode=preprod_mode)
        
        if operation == "config":
            # 显示配置
            interactor.show_config()
            
        elif operation == "balance":
            # 查看余额
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        elif operation == "approve":
            # 授权USDC
            if len(args) >= 2:
                amount = float(args[1])
            else:
                amount = None  # 授权最大值
            
            # 显示当前状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 执行授权
            tx_receipt = interactor.approve_usdc(amount)
            
            # 显示更新后的状态
            print()
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        elif operation == "deposit":
            # 存款USDC
            if len(args) < 2:
                print("❌ 请指定存款数量")
                return
            
            amount = float(args[1])
            
            # 显示当前状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 执行存款
            tx_receipt = interactor.deposit_usdc(amount)
            
            # 显示更新后的状态
            print()
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        elif operation == "all":
            # 完整流程: 授权 + 存款
            if len(args) < 2:
                print("❌ 请指定存款数量")
                return
            
            deposit_amount = float(args[1])
            
            print(f"🚀 执行完整流程: 授权最大值 + 存款 {deposit_amount:,.6f} USDC")
            print()
            
            # 显示初始状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 步骤1: 授权最大值
            print(f"\n📍 步骤 1/2: 授权USDC")
            tx_receipt1 = interactor.approve_usdc()
            
            # 步骤2: 存款
            print(f"\n📍 步骤 2/2: 存款USDC")
            tx_receipt2 = interactor.deposit_usdc(deposit_amount)
            
            # 显示最终状态
            print(f"\n🎉 完整流程执行完成!")
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        else:
            print(f"❌ 未知操作: {operation}")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
