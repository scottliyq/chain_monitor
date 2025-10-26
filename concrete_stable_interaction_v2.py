#!/usr/bin/env python3
"""
Concrete_STABLE 合约交互工具 v2
支持真实签名模式和mock模式（Impersonate）
动态获取合约ABI，使用ERC4626标准的deposit(uint256 assets, address receiver)方法
"""

import sys
import os
from web3 import Web3
from decimal import Decimal
import json
import time
import requests
from dotenv import load_dotenv
from eth_account import Account

# 加载环境变量
load_dotenv()

class ConcreteStableInteractionV2:
    def __init__(self, mock_mode=False):
        """初始化合约交互器
        
        Args:
            mock_mode (bool): 是否使用mock模式（Impersonate）
        """
        # 合约地址
        self.CONCRETE_STABLE_ADDRESS = Web3.to_checksum_address("0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
        self.USDT_CONTRACT_ADDRESS = Web3.to_checksum_address("0xdAC17F958D2ee523a2206206994597C13D831ec7")
        
        # 模式设置
        self.mock_mode = mock_mode
        
        # Etherscan API配置
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.etherscan_api_url = "https://api.etherscan.io/v2/api"  # 使用v2 API
        
        # 从环境变量获取配置
        if mock_mode:
            self.wallet_address = self._get_mock_wallet_address()
            self.private_key = None
            self.account = None
            print(f"🎭 Mock模式 - 使用Impersonate")
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
        print(f"   Concrete_STABLE: {self.CONCRETE_STABLE_ADDRESS}")
        print(f"   USDT合约: {self.USDT_CONTRACT_ADDRESS}")
        print(f"   钱包地址: {self.wallet_address}")
        print()
        
        self.web3 = None
        self.usdt_contract = None
        self.concrete_contract = None
        self.concrete_abi = None
        self.usdt_abi = None
        
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
            # 默认使用一个有大量USDT的地址（Binance热钱包）
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
        # Mock模式下优先使用 MOCK_WEB3_RPC_URL
        if self.mock_mode:
            mock_rpc_url = os.getenv('MOCK_WEB3_RPC_URL')
            if mock_rpc_url:
                return mock_rpc_url.strip()
            else:
                print("⚠️ Mock模式下未找到MOCK_WEB3_RPC_URL，使用默认的本地节点")
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
                'User-Agent': 'Concrete_STABLE_Interaction_Tool/2.0',
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
                
        except requests.exceptions.Timeout:
            print(f"⚠️ 请求{contract_name}ABI超时 (15秒)")
            return None
        except requests.exceptions.ConnectionError:
            print(f"⚠️ 网络连接错误，无法访问Etherscan v2 API")
            return None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 网络请求异常: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ 响应数据不是有效的JSON格式: {e}")
            return None
        except Exception as e:
            print(f"⚠️ 获取{contract_name}ABI时发生未知错误: {e}")
            return None
    
    def _get_fallback_abis(self):
        """获取备用ABI"""
        # USDT合约备用ABI (完整的ERC20 + USDT特殊函数)
        usdt_fallback_abi = [
            # 标准 ERC20 函数
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "remaining", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_from", "type": "address"},
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transferFrom",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        # Concrete_STABLE备用ABI - ERC4626标准 + ERC20基础函数
        concrete_fallback_abi = [
            # ERC4626标准的deposit函数 - 这是主要使用的函数
            {
                "constant": False,
                "inputs": [
                    {"name": "assets", "type": "uint256"},
                    {"name": "receiver", "type": "address"}
                ],
                "name": "deposit",
                "outputs": [{"name": "shares", "type": "uint256"}],
                "type": "function"
            },
            # ERC4626预览函数
            {
                "constant": True,
                "inputs": [{"name": "assets", "type": "uint256"}],
                "name": "previewDeposit",
                "outputs": [{"name": "shares", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "shares", "type": "uint256"}],
                "name": "previewRedeem",
                "outputs": [{"name": "assets", "type": "uint256"}],
                "type": "function"
            },
            # ERC4626底层资产
            {
                "constant": True,
                "inputs": [],
                "name": "asset",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            },
            # ERC4626赎回函数
            {
                "constant": False,
                "inputs": [
                    {"name": "shares", "type": "uint256"},
                    {"name": "receiver", "type": "address"},
                    {"name": "owner", "type": "address"}
                ],
                "name": "redeem",
                "outputs": [{"name": "assets", "type": "uint256"}],
                "type": "function"
            },
            # 基础ERC20函数
            {
                "constant": True,
                "inputs": [{"name": "user", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "name",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            # 备用的简单deposit函数
            {
                "constant": False,
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            }
        ]
        
        return usdt_fallback_abi, concrete_fallback_abi
    
    def _get_contract_abis(self):
        """获取所有合约的ABI（支持重试机制）"""
        print(f"🔄 开始从Etherscan v2 API获取合约ABI...")
        
        # 获取备用ABI
        usdt_fallback, concrete_fallback = self._get_fallback_abis()
        
        # 获取USDT ABI（支持重试）
        print(f"\n📋 正在获取USDT合约ABI...")
        self.usdt_abi = self._get_contract_abi_with_retry(self.USDT_CONTRACT_ADDRESS, "USDT")
        if not self.usdt_abi:
            print(f"📋 使用USDT备用ABI (完整ERC20标准)")
            self.usdt_abi = usdt_fallback
        
        # 获取Concrete_STABLE ABI（支持重试）
        print(f"\n📋 正在获取Concrete_STABLE合约ABI...")
        concrete_abi = self._get_contract_abi_with_retry(self.CONCRETE_STABLE_ADDRESS, "Concrete_STABLE")
        if not concrete_abi:
            print(f"📋 使用Concrete_STABLE备用ABI (包含ERC4626标准函数)")
            self.concrete_abi = concrete_fallback
        else:
            # 检查ABI是否包含主要的ERC4626函数
            function_names = [func.get('name') for func in concrete_abi if func.get('type') == 'function']
            required_functions = ['asset', 'deposit', 'name', 'symbol', 'decimals']
            missing_functions = [f for f in required_functions if f not in function_names]
            
            if missing_functions:
                print(f"   ⚠️ ABI缺少重要函数: {missing_functions}")
                print(f"   🔄 合并备用ABI以补充缺失的函数...")
                # 合并备用ABI中缺失的函数
                for func in concrete_fallback:
                    if func.get('name') in missing_functions:
                        concrete_abi.append(func)
                print(f"   ✅ 合并后ABI包含 {len(concrete_abi)} 个函数")
            
            self.concrete_abi = concrete_abi
        
        # 分析获取到的ABI
        self._analyze_contract_functions()
    
    def _get_contract_abi_with_retry(self, contract_address, contract_name="", max_retries=2):
        """带重试机制的ABI获取"""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                wait_time = 2 ** attempt  # 指数退避
                print(f"   ⏳ 第{attempt + 1}次尝试 (等待 {wait_time}s)...")
                time.sleep(wait_time)
            
            abi = self._get_contract_abi(contract_address, contract_name)
            if abi:
                return abi
                
            if attempt < max_retries:
                print(f"   🔄 重试获取{contract_name}ABI...")
        
        print(f"   ❌ 经过{max_retries + 1}次尝试后仍无法获取{contract_name}ABI")
        return None
    
    def _analyze_contract_functions(self):
        """分析合约可用函数"""
        print(f"\n📊 合约函数分析:")
        
        try:
            # 分析USDT合约
            usdt_functions = []
            for func in self.usdt_abi:
                if func.get('type') == 'function' and 'name' in func:
                    func_name = func['name']
                    # 创建函数签名以区分重载函数
                    input_types = [inp.get('type', 'unknown') for inp in func.get('inputs', [])]
                    signature = f"{func_name}({','.join(input_types)})"
                    usdt_functions.append(signature)
            
            # 去重并排序
            usdt_functions = sorted(list(set(usdt_functions)))
            print(f"   USDT合约函数 ({len(usdt_functions)}个):")
            for i, func in enumerate(usdt_functions[:10]):  # 只显示前10个
                print(f"     {i+1}. {func}")
            if len(usdt_functions) > 10:
                print(f"     ... 还有 {len(usdt_functions) - 10} 个函数")
            
            # 分析Concrete_STABLE合约
            concrete_functions = []
            for func in self.concrete_abi:
                if func.get('type') == 'function' and 'name' in func:
                    func_name = func['name']
                    # 创建函数签名以区分重载函数
                    input_types = [inp.get('type', 'unknown') for inp in func.get('inputs', [])]
                    signature = f"{func_name}({','.join(input_types)})"
                    concrete_functions.append(signature)
            
            # 去重并排序
            concrete_functions = sorted(list(set(concrete_functions)))
            print(f"   Concrete_STABLE函数 ({len(concrete_functions)}个):")
            for i, func in enumerate(concrete_functions):
                print(f"     {i+1}. {func}")
            
            # 查找deposit函数的不同签名
            deposit_functions = []
            for func in self.concrete_abi:
                if func.get('type') == 'function' and func.get('name') == 'deposit':
                    deposit_functions.append(func)
            
            print(f"   \n🔍 找到 {len(deposit_functions)} 个deposit函数变体:")
            
            for i, func in enumerate(deposit_functions, 1):
                try:
                    inputs = func.get('inputs', [])
                    input_details = []
                    for inp in inputs:
                        inp_type = inp.get('type', 'unknown')
                        inp_name = inp.get('name', 'unnamed')
                        input_details.append(f"{inp_type} {inp_name}")
                    
                    signature = f"deposit({', '.join(input_details)})"
                    
                    outputs = func.get('outputs', [])
                    if outputs:
                        output_types = [out.get('type', 'unknown') for out in outputs]
                        signature += f" returns ({', '.join(output_types)})"
                    
                    print(f"     {i}. {signature}")
                    
                except Exception as e:
                    print(f"     {i}. 解析函数签名失败: {e}")
            
            self.deposit_functions = deposit_functions
            
        except Exception as e:
            print(f"⚠️ 分析合约函数时发生错误: {e}")
            print(f"   详细错误信息: {type(e).__name__}: {str(e)}")
            print(f"   将继续使用备用ABI...")
            # 如果分析失败，设置空的deposit_functions列表
            self.deposit_functions = []
        
        print()
    
    def _safe_call_function(self, contract, function_name, *args, **kwargs):
        """安全调用合约函数，处理重载函数的情况"""
        try:
            # 尝试直接调用
            func = getattr(contract.functions, function_name)
            if args or kwargs:
                return func(*args, **kwargs)
            else:
                return func()
        except AttributeError as e:
            print(f"⚠️ 函数 {function_name} 不存在于合约中: {e}")
            return None
        except Exception as e:
            # 如果是重载函数导致的错误，尝试其他方法
            if 'multiple functions' in str(e).lower() or 'ambiguous' in str(e).lower():
                print(f"⚠️ 检测到函数重载，尝试使用备用方法调用 {function_name}")
                return self._call_overloaded_function(contract, function_name, *args, **kwargs)
            else:
                print(f"⚠️ 调用函数 {function_name} 失败: {e}")
                return None
    
    def _call_overloaded_function(self, contract, function_name, *args, **kwargs):
        """处理重载函数的调用"""
        try:
            # 根据参数类型和数量尝试确定正确的函数签名
            abi = contract.abi
            matching_functions = []
            
            for func_abi in abi:
                if (func_abi.get('type') == 'function' and 
                    func_abi.get('name') == function_name):
                    inputs = func_abi.get('inputs', [])
                    if len(inputs) == len(args):
                        matching_functions.append(func_abi)
            
            if len(matching_functions) == 1:
                # 只有一个匹配的函数，使用它
                func_abi = matching_functions[0]
                inputs = func_abi.get('inputs', [])
                input_types = [inp['type'] for inp in inputs]
                signature = f"{function_name}({','.join(input_types)})"
                
                # 使用完整签名调用函数
                func = contract.get_function_by_signature(signature)
                if args or kwargs:
                    return func(*args, **kwargs)
                else:
                    return func()
            
            elif len(matching_functions) > 1:
                print(f"⚠️ 找到多个匹配的 {function_name} 函数，使用第一个")
                func_abi = matching_functions[0]
                inputs = func_abi.get('inputs', [])
                input_types = [inp['type'] for inp in inputs]
                signature = f"{function_name}({','.join(input_types)})"
                
                func = contract.get_function_by_signature(signature)
                if args or kwargs:
                    return func(*args, **kwargs)
                else:
                    return func()
            
            else:
                print(f"⚠️ 没有找到匹配的 {function_name} 函数")
                return None
                
        except Exception as e:
            print(f"⚠️ 调用重载函数 {function_name} 失败: {e}")
            return None
    
    def _init_contracts(self):
        """使用获取到的ABI初始化合约实例"""
        try:
            print(f"🔄 初始化合约实例...")
            
            # 创建USDT合约实例
            self.usdt_contract = self.web3.eth.contract(
                address=self.USDT_CONTRACT_ADDRESS,
                abi=self.usdt_abi
            )
            
            # 创建Concrete_STABLE合约实例
            self.concrete_contract = self.web3.eth.contract(
                address=self.CONCRETE_STABLE_ADDRESS,
                abi=self.concrete_abi
            )
            
            # 验证USDT合约连接
            try:
                usdt_symbol = self._safe_call_function(self.usdt_contract, 'symbol')
                usdt_decimals = self._safe_call_function(self.usdt_contract, 'decimals')
                
                if usdt_symbol and hasattr(usdt_symbol, 'call'):
                    usdt_symbol = usdt_symbol.call()
                if usdt_decimals and hasattr(usdt_decimals, 'call'):
                    usdt_decimals = usdt_decimals.call()
                    
                if usdt_symbol and usdt_decimals is not None:
                    print(f"✅ USDT合约连接成功: {usdt_symbol} (精度: {usdt_decimals})")
                else:
                    print(f"✅ USDT合约连接成功，但部分信息获取失败")
            except Exception as e:
                print(f"⚠️ USDT合约验证失败: {e}")
            
            # 验证Concrete_STABLE合约连接
            try:
                # 检查合约代码
                code = self.web3.eth.get_code(self.CONCRETE_STABLE_ADDRESS)
                if code == '0x':
                    print(f"⚠️ Concrete_STABLE地址没有合约代码")
                else:
                    print(f"✅ Concrete_STABLE合约连接成功 (代码长度: {len(code)} bytes)")
                    
                    # 尝试调用asset函数来验证这是ERC4626合约
                    try:
                        # 使用安全函数调用方法
                        asset_address = self._safe_call_function(self.concrete_contract, 'asset')
                        if asset_address and hasattr(asset_address, 'call'):
                            try:
                                asset_result = asset_address.call()
                                print(f"   底层资产: {asset_result}")
                                if asset_result.lower() == self.USDT_CONTRACT_ADDRESS.lower():
                                    print(f"   ✅ 确认为USDT的ERC4626合约")
                                else:
                                    print(f"   ⚠️ 底层资产不是USDT: {asset_result}")
                            except Exception as call_error:
                                print(f"   ⚠️ 调用asset函数失败: {call_error}")
                        elif asset_address:
                            # 直接返回了结果
                            print(f"   底层资产: {asset_address}")
                            if str(asset_address).lower() == self.USDT_CONTRACT_ADDRESS.lower():
                                print(f"   ✅ 确认为USDT的ERC4626合约")
                            else:
                                print(f"   ⚠️ 底层资产不是USDT: {asset_address}")
                        else:
                            print(f"   📋 无法获取底层资产地址")
                            
                    except Exception as asset_error:
                        print(f"   注意: 无法调用asset函数: {asset_error}")
                        
            except Exception as e:
                print(f"⚠️ Concrete_STABLE合约验证失败: {e}")
            
            print(f"✅ 合约初始化完成!")
            print()
            
        except Exception as e:
            raise Exception(f"❌ 合约初始化失败: {e}")
    
    def _enable_impersonate(self):
        """启用Impersonate模式"""
        try:
            print(f"🎭 启用Impersonate模式...")
            
            # 检查是否是支持impersonate的网络（通常是本地分叉）
            try:
                # 尝试impersonate账户
                self.web3.provider.make_request("hardhat_impersonateAccount", [self.wallet_address])
                print(f"✅ 成功impersonate地址: {self.wallet_address}")
                
                # 为该地址提供一些ETH用于gas费（如果余额不足）
                eth_balance = self.web3.eth.get_balance(self.wallet_address)
                if eth_balance < Web3.to_wei(0.1, 'ether'):
                    print(f"🔋 为地址充值ETH...")
                    self.web3.provider.make_request("hardhat_setBalance", [
                        self.wallet_address,
                        hex(Web3.to_wei(10, 'ether'))  # 充值10个ETH
                    ])
                    
            except Exception as imp_error:
                print(f"⚠️ Impersonate设置可能失败: {imp_error}")
                print(f"💡 如果在本地分叉环境中，这是正常的")
                
        except Exception as e:
            print(f"⚠️ Impersonate模式设置失败: {e}")
    
    def _build_transaction(self, contract_function, gas_limit=None):
        """构建交易（支持mock模式和真实模式）"""
        try:
            base_txn = {
                'from': self.wallet_address,
                'gasPrice': self.web3.eth.gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'chainId': self.web3.eth.chain_id
            }
            
            if gas_limit:
                base_txn['gas'] = gas_limit
                
            return contract_function.build_transaction(base_txn)
            
        except Exception as e:
            raise Exception(f"构建交易失败: {e}")
    
    def _send_transaction(self, txn):
        """发送交易（支持mock模式和真实模式）"""
        try:
            if self.mock_mode:
                # Mock模式：直接发送交易（已经impersonate）
                print(f"📤 发送Mock交易...")
                tx_hash = self.web3.eth.send_transaction(txn)
            else:
                # 真实模式：签名后发送
                print(f"📤 签名并发送交易...")
                signed_txn = self.web3.eth.account.sign_transaction(txn, self.private_key)
                # 兼容新版本Web3.py：使用raw_transaction而不是rawTransaction
                raw_transaction = getattr(signed_txn, 'raw_transaction', getattr(signed_txn, 'rawTransaction', None))
                if raw_transaction is None:
                    raise Exception("无法获取签名后的交易数据")
                tx_hash = self.web3.eth.send_raw_transaction(raw_transaction)
            
            print(f"   交易哈希: {tx_hash.hex()}")
            return tx_hash
            
        except Exception as e:
            raise Exception(f"发送交易失败: {e}")
    
    def get_balances(self):
        """查询当前余额"""
        try:
            # USDT余额 - 使用安全函数调用
            usdt_balance_func = self._safe_call_function(
                self.usdt_contract, 'balanceOf', self.wallet_address
            )
            usdt_balance_raw = usdt_balance_func.call() if hasattr(usdt_balance_func, 'call') else usdt_balance_func
            
            usdt_decimals_func = self._safe_call_function(self.usdt_contract, 'decimals')
            usdt_decimals = usdt_decimals_func.call() if hasattr(usdt_decimals_func, 'call') else usdt_decimals_func
            
            usdt_balance = Decimal(usdt_balance_raw) / Decimal(10 ** usdt_decimals)
            
            # ETH余额
            eth_balance_wei = self.web3.eth.get_balance(self.wallet_address)
            eth_balance = Web3.from_wei(eth_balance_wei, 'ether')
            
            # 当前授权额度 - 使用安全函数调用
            allowance_func = self._safe_call_function(
                self.usdt_contract, 'allowance', 
                self.wallet_address, self.CONCRETE_STABLE_ADDRESS
            )
            allowance_raw = allowance_func.call() if hasattr(allowance_func, 'call') else allowance_func
            allowance = Decimal(allowance_raw) / Decimal(10 ** usdt_decimals)
            
            return {
                'usdt_balance': float(usdt_balance),
                'usdt_balance_raw': usdt_balance_raw,
                'eth_balance': float(eth_balance),
                'eth_balance_wei': eth_balance_wei,
                'allowance': float(allowance),
                'allowance_raw': allowance_raw,
                'usdt_decimals': usdt_decimals
            }
            
        except Exception as e:
            raise Exception(f"查询余额失败: {e}")
    
    def approve_usdt(self, amount=None):
        """授权USDT给Concrete_STABLE合约"""
        try:
            print(f"🔄 准备授权USDT...")
            
            # 如果未指定数量，使用最大值
            if amount is None:
                # 使用uint256最大值
                amount_raw = 2**256 - 1
                print(f"   授权数量: 最大值 (2^256-1)")
            else:
                usdt_decimals = self.usdt_contract.functions.decimals().call()
                amount_raw = int(Decimal(amount) * Decimal(10 ** usdt_decimals))
                print(f"   授权数量: {amount:,.6f} USDT")
            
            # 构建交易
            approve_txn = self._build_transaction(
                self.usdt_contract.functions.approve(
                    self.CONCRETE_STABLE_ADDRESS,
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
            raise Exception(f"授权USDT失败: {e}")
    
    def deposit_usdt(self, amount):
        """存款USDT到Concrete_STABLE合约
        使用ERC4626标准的deposit函数: deposit(uint256 assets, address receiver)
        """
        try:
            print(f"🔄 准备存款 {amount:,.6f} USDT...")
            print(f"   使用ERC4626标准函数: deposit(uint256 assets, address receiver)")
            
            # 转换为合约单位
            usdt_decimals = self.usdt_contract.functions.decimals().call()
            amount_raw = int(Decimal(amount) * Decimal(10 ** usdt_decimals))
            
            print(f"   存款数量: {amount:,.6f} USDT ({amount_raw} raw)")
            print(f"   接收地址: {self.wallet_address}")
            
            # 检查余额和授权
            balances = self.get_balances()
            if balances['usdt_balance'] < amount:
                raise Exception(f"USDT余额不足: {balances['usdt_balance']:.6f} < {amount:.6f}")
            
            if balances['allowance'] < amount:
                raise Exception(f"授权额度不足: {balances['allowance']:.6f} < {amount:.6f}")
            
            # 使用ERC4626的deposit函数：deposit(uint256 assets, address receiver)
            contract_function = self.concrete_contract.functions.deposit(amount_raw, self.wallet_address)
            
            # 先进行模拟调用来检查是否会成功
            try:
                print(f"   🧪 进行模拟调用...")
                simulation_result = contract_function.call({'from': self.wallet_address})
                print(f"   ✅ 模拟调用成功，预期返回: {simulation_result}")
            except Exception as sim_error:
                print(f"   ❌ 模拟调用失败: {sim_error}")
                # 尝试预览deposit来获取更多信息
                try:
                    if any(func['name'] == 'previewDeposit' for func in self.concrete_abi):
                        preview_result = self.concrete_contract.functions.previewDeposit(amount_raw).call()
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
            raise Exception(f"存款USDT失败: {e}")
    
    def display_balances(self, balances):
        """显示余额信息"""
        print(f"📊 当前账户状态")
        print(f"{'='*50}")
        print(f"🏠 钱包地址: {self.wallet_address}")
        print(f"💰 USDT余额: {balances['usdt_balance']:,.6f} USDT")
        print(f"⛽ ETH余额: {balances['eth_balance']:.6f} ETH")
        print(f"✅ 授权额度: {balances['allowance']:,.6f} USDT")
        print(f"{'='*50}")

    def show_config(self):
        """显示当前配置信息"""
        print(f"🔧 当前配置信息")
        print(f"{'='*50}")
        print(f"🎯 运行模式: {'🎭 Mock模式 (Impersonate)' if self.mock_mode else '🔐 真实签名模式'}")
        print(f"🌐 RPC URL: {self.rpc_url}")
        print(f"🔗 网络ID: {self.network_id}")
        print(f"📍 钱包地址: {self.wallet_address}")
        print(f"🏦 Concrete_STABLE: {self.CONCRETE_STABLE_ADDRESS}")
        print(f"💰 USDT合约: {self.USDT_CONTRACT_ADDRESS}")
        if self.mock_mode:
            print(f"💡 Mock配置说明:")
            print(f"   - 使用环境变量: MOCK_WEB3_RPC_URL")
            print(f"   - Impersonate地址: MOCK_WALLET_ADDRESS")
            print(f"   - 无需私钥，本地分叉网络模拟交易")
        else:
            print(f"💡 真实模式说明:")
            print(f"   - 使用环境变量: WEB3_RPC_URL")
            print(f"   - 需要私钥: WALLET_PRIVATE_KEY")
            print(f"   - 真实网络，实际消耗Gas费用")
        print(f"{'='*50}")

def main():
    """主函数"""
    print("🏦 Concrete_STABLE 合约交互工具 v2 (ERC4626标准)")
    print("=" * 70)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("📖 使用方法:")
        print(f"  python {sys.argv[0]} <操作> [参数] [--mock]")
        print()
        print("📝 支持的操作:")
        print(f"  balance              - 查询余额")
        print(f"  config               - 显示当前配置信息")
        print(f"  approve [amount]     - 授权USDT (不指定amount则授权最大值)")
        print(f"  deposit <amount>     - 存款USDT (使用ERC4626标准)")
        print(f"  all <amount>         - 执行完整流程: 授权最大值 + 存款指定数量")
        print()
        print("🎭 模式选项:")
        print(f"  --mock              - 使用Mock模式（Impersonate，适用于本地分叉）")
        print(f"  (默认)             - 使用真实签名模式")
        print()
        print("📝 示例:")
        print(f"  python {sys.argv[0]} balance --mock")
        print(f"  python {sys.argv[0]} approve --mock")
        print(f"  python {sys.argv[0]} deposit 100 --mock")
        print(f"  python {sys.argv[0]} all 100 --mock")
        print()
        print("🔧 环境变量配置 (.env文件):")
        print("  # Mock模式 (本地分叉)")
        print("  MOCK_WALLET_ADDRESS=0xF977814e90dA44bFA03b6295A0616a897441aceC")
        print("  WEB3_RPC_URL=http://127.0.0.1:8545")
        print("  WEB3_NETWORK_ID=31337")
        print("  ETHERSCAN_API_KEY=YourApiKeyToken")
        return
    
    # 解析参数
    args = sys.argv[1:]
    mock_mode = '--mock' in args
    if mock_mode:
        args.remove('--mock')
    
    operation = args[0].lower() if args else 'balance'
    
    try:
        # 创建交互器实例
        interactor = ConcreteStableInteractionV2(mock_mode=mock_mode)
        
        if operation == "balance":
            # 查询余额
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        elif operation == "config":
            # 显示配置信息
            interactor.show_config()
            
        elif operation == "approve":
            # 授权USDT
            amount = None
            if len(args) > 1:
                amount = float(args[1])
            
            # 显示当前状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 执行授权
            tx_receipt = interactor.approve_usdt(amount)
            
            # 显示更新后的状态
            print()
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
        elif operation == "deposit":
            # 存款USDT
            if len(args) < 2:
                print("❌ 请指定存款数量")
                return
            
            amount = float(args[1])
            
            # 显示当前状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 执行存款
            tx_receipt = interactor.deposit_usdt(amount)
            
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
            
            print(f"🚀 执行完整流程: 授权最大值 + 存款 {deposit_amount:,.6f} USDT")
            print()
            
            # 显示初始状态
            balances = interactor.get_balances()
            interactor.display_balances(balances)
            
            # 步骤1: 授权最大值
            print(f"\n📍 步骤 1/2: 授权USDT")
            tx_receipt1 = interactor.approve_usdt()
            
            # 步骤2: 存款
            print(f"\n📍 步骤 2/2: 存款USDT")
            tx_receipt2 = interactor.deposit_usdt(deposit_amount)
            
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