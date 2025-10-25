#!/usr/bin/env python3
"""
合约部署追踪工具
查找指定地址在最近7天内在以太坊主网上部署的所有合约地址
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timedelta
from web3 import Web3
from decimal import Decimal
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ContractDeploymentTracker:
    def __init__(self):
        """初始化合约部署追踪器"""
        # API配置
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', 'YourApiKeyToken')
        self.etherscan_api_url = "https://api.etherscan.io/v2/api"
        
        # Web3配置
        self.rpc_url = self._get_rpc_url()
        self.web3 = self._init_web3()
        
        # 时间配置
        self.days_back = 7
        self.current_time = int(time.time())
        self.start_time = self.current_time - (self.days_back * 24 * 60 * 60)
        
        print(f"🔧 配置信息:")
        print(f"   Etherscan API Key: {'***' + self.etherscan_api_key[-4:] if len(self.etherscan_api_key) > 4 else 'YourApiKeyToken'}")
        print(f"   RPC URL: {self.rpc_url}")
        print(f"   查询时间范围: {self.days_back} 天")
        print(f"   开始时间: {datetime.fromtimestamp(self.start_time)}")
        print(f"   结束时间: {datetime.fromtimestamp(self.current_time)}")
        print()
    
    def _get_rpc_url(self):
        """从环境变量获取RPC URL"""
        rpc_url = os.getenv('WEB3_RPC_URL')
        if not rpc_url:
            # 备选方案
            if os.getenv('WEB3_ALCHEMY_PROJECT_ID'):
                return f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('WEB3_ALCHEMY_PROJECT_ID')}"
            elif os.getenv('WEB3_INFURA_PROJECT_ID'):
                return f"https://mainnet.infura.io/v3/{os.getenv('WEB3_INFURA_PROJECT_ID')}"
            else:
                # 使用免费的公共RPC端点
                return "https://eth.llamarpc.com"
        
        return rpc_url.strip()
    
    def _init_web3(self):
        """初始化Web3连接"""
        try:
            provider = Web3.HTTPProvider(
                self.rpc_url,
                request_kwargs={'timeout': 30}
            )
            web3 = Web3(provider)
            
            # 验证连接
            chain_id = web3.eth.chain_id
            if chain_id != 1:
                print(f"⚠️ 警告: 当前连接的不是以太坊主网 (Chain ID: {chain_id})")
            
            return web3
            
        except Exception as e:
            print(f"⚠️ Web3连接失败: {e}")
            return None
    
    def get_transactions(self, address, page=1, per_page=5000):
        """获取地址的交易列表
        
        Args:
            address (str): 要查询的地址
            page (int): 页码
            per_page (int): 每页数量 (最大5000，确保page×per_page≤10000)
            
        Returns:
            list: 交易列表
        """
        try:
            print(f"🔍 获取地址 {address} 的交易记录 (页码: {page})")
            
            params = {
                'module': 'account',
                'action': 'txlist',
                'address': address,
                'startblock': 0,
                'endblock': 99999999,
                'page': page,
                'offset': per_page,
                'sort': 'desc',  # 降序，最新的交易在前
                'apikey': self.etherscan_api_key,
                'chainid': 1  # 以太坊主网
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=30)
            data = response.json()
            
            print(f"   API响应状态: {data.get('status')}, 消息: {data.get('message')}")
            
            if data['status'] == '1':
                transactions = data['result']
                print(f"   📦 获取到 {len(transactions)} 笔交易")
                return transactions
            else:
                print(data)
                print(f"   ❌ API错误: {data.get('message', 'Unknown error')}")
                # 如果是API key问题，提供建议
                if 'invalid' in data.get('message', '').lower() or 'api' in data.get('message', '').lower():
                    print(f"   💡 建议: 检查ETHERSCAN_API_KEY环境变量是否设置正确")
                return []
                
        except Exception as e:
            print(f"   ❌ 获取交易失败: {e}")
            return []
    
    def filter_recent_transactions(self, transactions):
        """筛选最近7天的交易
        
        Args:
            transactions (list): 交易列表
            
        Returns:
            list: 最近7天的交易
        """
        recent_transactions = []
        
        for tx in transactions:
            tx_timestamp = int(tx['timeStamp'])
            
            # 如果交易时间超过查询范围，跳出循环（因为是降序）
            if tx_timestamp < self.start_time:
                break
                
            recent_transactions.append(tx)
        
        print(f"🕐 最近{self.days_back}天内的交易: {len(recent_transactions)} 笔")
        return recent_transactions
    
    def find_contract_deployments(self, transactions):
        """从交易中找出合约部署交易
        
        Args:
            transactions (list): 交易列表
            
        Returns:
            list: 合约部署信息列表
        """
        deployments = []
        
        print(f"🔍 分析交易中的合约部署...")
        
        for tx in transactions:
            # 合约部署的特征：to字段为空，且交易成功
            if (tx['to'] == '' or tx['to'] is None) and tx['txreceipt_status'] == '1':
                deployment_info = {
                    'tx_hash': tx['hash'],
                    'deployer': tx['from'],
                    'block_number': int(tx['blockNumber']),
                    'timestamp': int(tx['timeStamp']),
                    'datetime': datetime.fromtimestamp(int(tx['timeStamp'])),
                    'gas_used': int(tx['gasUsed']),
                    'gas_price': int(tx['gasPrice']),
                    'input_data': tx['input'],
                    'contract_address': None  # 需要从交易收据获取
                }
                
                deployments.append(deployment_info)
        
        print(f"   📋 发现 {len(deployments)} 个可能的合约部署交易")
        return deployments
    
    def get_contract_addresses(self, deployments):
        """获取部署的合约地址
        
        Args:
            deployments (list): 部署交易列表
            
        Returns:
            list: 包含合约地址的部署信息
        """
        if not self.web3:
            print(f"⚠️ Web3连接不可用，无法获取合约地址")
            return deployments
        
        print(f"🔍 获取合约地址...")
        
        for i, deployment in enumerate(deployments, 1):
            try:
                print(f"   处理 {i}/{len(deployments)}: {deployment['tx_hash'][:10]}...")
                
                # 获取交易收据
                receipt = self.web3.eth.get_transaction_receipt(deployment['tx_hash'])
                
                if receipt and receipt.contractAddress:
                    deployment['contract_address'] = receipt.contractAddress
                    
                    # 验证合约代码
                    code = self.web3.eth.get_code(receipt.contractAddress)
                    deployment['contract_code_size'] = len(code)
                    deployment['has_code'] = len(code) > 2  # 0x 之后有内容
                    
                    print(f"     ✅ 合约地址: {receipt.contractAddress}")
                    print(f"     📏 代码大小: {len(code)} bytes")
                    
                else:
                    print(f"     ❌ 未找到合约地址")
                    
                # 添加延迟避免RPC限制
                time.sleep(0.1)
                
            except Exception as e:
                print(f"     ❌ 获取合约地址失败: {e}")
                deployment['contract_address'] = None
                deployment['error'] = str(e)
        
        return deployments
    
    def get_contract_info(self, contract_address):
        """获取合约的详细信息
        
        Args:
            contract_address (str): 合约地址
            
        Returns:
            dict: 合约信息
        """
        try:
            # 从Etherscan获取合约源码信息
            params = {
                'module': 'contract',
                'action': 'getsourcecode',
                'address': contract_address,
                'apikey': self.etherscan_api_key,
                'chainid': 1  # 以太坊主网
            }
            
            response = requests.get(self.etherscan_api_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == '1' and data['result']:
                source_info = data['result'][0]
                return {
                    'contract_name': source_info.get('ContractName', 'Unknown'),
                    'compiler_version': source_info.get('CompilerVersion', 'Unknown'),
                    'optimization_used': source_info.get('OptimizationUsed', 'Unknown'),
                    'source_code': source_info.get('SourceCode', ''),
                    'abi': source_info.get('ABI', ''),
                    'proxy': source_info.get('Proxy', '0') == '1',
                    'implementation': source_info.get('Implementation', '')
                }
            else:
                return {'error': 'No source code found'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def track_deployments(self, deployer_address):
        """追踪指定地址的合约部署
        
        Args:
            deployer_address (str): 部署者地址
            
        Returns:
            dict: 包含所有部署信息的结果
        """
        try:
            # 验证地址格式
            if not Web3.is_address(deployer_address):
                raise ValueError(f"无效的地址格式: {deployer_address}")
            
            deployer_address = Web3.to_checksum_address(deployer_address)
            
            print(f"🎯 追踪地址: {deployer_address}")
            print(f"📅 时间范围: 最近 {self.days_back} 天")
            print("=" * 60)
            
            # 获取交易列表
            all_transactions = []
            page = 1
            per_page = 5000  # 使用较小的页面大小
            
            while True:
                # 确保不超过API限制 (page × per_page ≤ 10000)
                if page * per_page > 10000:
                    print(f"⚠️ 达到API查询限制 (page×offset≤10000)，停止查询")
                    break
                    
                transactions = self.get_transactions(deployer_address, page=page, per_page=per_page)
                if not transactions:
                    break
                
                # 筛选最近的交易
                recent_txs = self.filter_recent_transactions(transactions)
                all_transactions.extend(recent_txs)
                
                # 如果这页的交易都不在时间范围内，停止查询
                if not recent_txs:
                    break
                
                page += 1
                
                time.sleep(0.2)  # API速率限制
            
            print(f"\n📊 总计获取 {len(all_transactions)} 笔最近交易")
            
            # 查找合约部署
            deployments = self.find_contract_deployments(all_transactions)
            
            if not deployments:
                print(f"❌ 在最近{self.days_back}天内未发现合约部署")
                return {
                    'deployer_address': deployer_address,
                    'query_period_days': self.days_back,
                    'query_start_time': datetime.fromtimestamp(self.start_time).isoformat(),
                    'query_end_time': datetime.fromtimestamp(self.current_time).isoformat(),
                    'total_transactions': len(all_transactions),
                    'deployments': [],
                    'contract_count': 0,
                    'query_time': datetime.now().isoformat()
                }
            
            # 获取合约地址
            deployments = self.get_contract_addresses(deployments)
            
            # 获取合约详细信息
            print(f"\n🔍 获取合约详细信息...")
            for deployment in deployments:
                if deployment.get('contract_address'):
                    print(f"   查询合约: {deployment['contract_address']}")
                    contract_info = self.get_contract_info(deployment['contract_address'])
                    deployment['contract_info'] = contract_info
                    time.sleep(0.2)  # API速率限制
            
            # 构造结果
            result = {
                'deployer_address': deployer_address,
                'query_period_days': self.days_back,
                'query_start_time': datetime.fromtimestamp(self.start_time).isoformat(),
                'query_end_time': datetime.fromtimestamp(self.current_time).isoformat(),
                'total_transactions': len(all_transactions),
                'deployments': deployments,
                'contract_count': len([d for d in deployments if d.get('contract_address')]),
                'query_time': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            raise Exception(f"追踪部署失败: {e}")
    
    def format_results(self, result):
        """格式化并显示结果"""
        print(f"\n📊 合约部署追踪结果")
        print(f"{'='*80}")
        print(f"🏠 部署者地址: {result['deployer_address']}")
        print(f"📅 查询时间范围: {result['query_period_days']} 天")
        print(f"🕐 开始时间: {result['query_start_time']}")
        print(f"🕐 结束时间: {result['query_end_time']}")
        print(f"📦 总交易数: {result['total_transactions']:,}")
        print(f"🏭 部署的合约数: {result['contract_count']}")
        print(f"{'='*80}")
        
        if not result['deployments']:
            print(f"❌ 在查询时间范围内未发现合约部署")
            return
        
        for i, deployment in enumerate(result['deployments'], 1):
            print(f"\n📋 合约 #{i}")
            print(f"   🔗 交易哈希: {deployment['tx_hash']}")
            print(f"   🏠 合约地址: {deployment.get('contract_address', 'N/A')}")
            print(f"   📦 区块号: {deployment['block_number']:,}")
            print(f"   🕐 部署时间: {deployment['datetime']}")
            print(f"   ⛽ Gas使用: {deployment['gas_used']:,}")
            print(f"   💰 Gas价格: {Web3.from_wei(deployment['gas_price'], 'gwei'):.2f} Gwei")
            
            if deployment.get('contract_address') and deployment.get('has_code'):
                print(f"   📏 合约代码大小: {deployment['contract_code_size']:,} bytes")
                
                # 显示合约信息
                contract_info = deployment.get('contract_info', {})
                if contract_info and 'error' not in contract_info:
                    print(f"   📝 合约名称: {contract_info.get('contract_name', 'Unknown')}")
                    print(f"   🔧 编译器版本: {contract_info.get('compiler_version', 'Unknown')}")
                    print(f"   ⚡ 优化: {contract_info.get('optimization_used', 'Unknown')}")
                    if contract_info.get('proxy'):
                        print(f"   🔄 代理合约: 是")
                        if contract_info.get('implementation'):
                            print(f"   🎯 实现合约: {contract_info['implementation']}")
                elif 'error' in contract_info:
                    print(f"   ⚠️ 合约信息: {contract_info['error']}")
            else:
                print(f"   ⚠️ 合约可能已销毁或无代码")
    
    def save_results(self, result, output_dir="temp"):
        """保存结果到文件"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            address_suffix = result['deployer_address'][-8:]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存JSON详细数据
            json_filename = f"contract_deployments_{address_suffix}_{timestamp}.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            
            # 保存简化的文本报告
            txt_filename = f"contract_deployments_{address_suffix}_{timestamp}.txt"
            txt_filepath = os.path.join(output_dir, txt_filename)
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(f"合约部署追踪报告\n")
                f.write(f"{'='*50}\n")
                f.write(f"部署者地址: {result['deployer_address']}\n")
                f.write(f"查询时间范围: {result['query_period_days']} 天\n")
                f.write(f"查询时间: {result['query_time']}\n")
                f.write(f"总交易数: {result['total_transactions']:,}\n")
                f.write(f"部署的合约数: {result['contract_count']}\n\n")
                
                if result['deployments']:
                    f.write(f"部署的合约列表:\n")
                    f.write(f"{'-'*50}\n")
                    for i, deployment in enumerate(result['deployments'], 1):
                        f.write(f"{i}. 合约地址: {deployment.get('contract_address', 'N/A')}\n")
                        f.write(f"   交易哈希: {deployment['tx_hash']}\n")
                        f.write(f"   部署时间: {deployment['datetime']}\n")
                        f.write(f"   区块号: {deployment['block_number']:,}\n")
                        
                        contract_info = deployment.get('contract_info', {})
                        if contract_info and 'error' not in contract_info:
                            f.write(f"   合约名称: {contract_info.get('contract_name', 'Unknown')}\n")
                        f.write(f"\n")
                else:
                    f.write(f"在查询时间范围内未发现合约部署。\n")
            
            print(f"\n💾 结果已保存:")
            print(f"   📄 详细数据: {json_filepath}")
            print(f"   📝 文本报告: {txt_filepath}")
            
            return json_filepath, txt_filepath
            
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")
            return None, None

def main():
    """主函数"""
    print("🏭 以太坊合约部署追踪工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("📖 使用方法:")
        print(f"  python {sys.argv[0]} <部署者地址> [天数]")
        print()
        print("📝 示例:")
        print(f"  python {sys.argv[0]} 0x1234...5678")
        print(f"  python {sys.argv[0]} 0x1234...5678 3")
        print()
        print("🔧 环境变量配置 (.env文件):")
        print("  ETHERSCAN_API_KEY=YourEtherscanApiKey")
        print("  WEB3_RPC_URL=https://eth.llamarpc.com")
        print()
        print("🎯 一些知名部署者地址:")
        print("  Vitalik Buterin: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        print("  Uniswap Deployer: 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984")
        print("  OpenZeppelin: 0x4f2083f5fBede34C2714aF59e9076b4Ebf31e5F0")
        return
    
    deployer_address = sys.argv[1].strip()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    
    try:
        # 创建追踪器实例
        tracker = ContractDeploymentTracker()
        tracker.days_back = days
        tracker.start_time = tracker.current_time - (days * 24 * 60 * 60)
        
        # 追踪合约部署
        result = tracker.track_deployments(deployer_address)
        
        # 显示结果
        tracker.format_results(result)
        
        # 保存结果
        tracker.save_results(result)
        
        print(f"\n✅ 追踪完成!")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()