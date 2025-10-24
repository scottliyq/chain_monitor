# Brownie 以太坊余额查询工具

## 简介
这是一个使用Brownie框架查询以太坊地址余额的工具，支持ETH和主流ERC20代币的余额查询。

## 安装和配置

### 1. 安装Brownie
```bash
pip install eth-brownie
```

### 2. 初始化Brownie项目（可选）
```bash
# 在项目目录中初始化Brownie
brownie init

# 或者使用现有项目
cd /Users/scottliyq/go/hardhat_space/chain_monitor
```

### 3. 配置网络（可选）
创建 `brownie-config.yaml` 文件来配置网络设置：

```yaml
dependencies:
  - OpenZeppelin/openzeppelin-contracts@4.8.0

compiler:
  solc:
    version: 0.8.19

networks:
  default: mainnet
  mainnet:
    host: https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
    gas_limit: 6721975
    gas_buffer: 1.1
    gas_price: 20000000000
  goerli:
    host: https://eth-goerli.g.alchemy.com/v2/YOUR_API_KEY
    gas_limit: 6721975
    gas_price: 20000000000
```

## 功能特性

### 🔍 支持的查询功能
- **ETH余额查询** - 原生以太坊余额
- **ERC20代币余额** - 支持主流代币
- **批量地址查询** - 一次查询多个地址
- **代币信息获取** - 名称、符号、小数位数等
- **结果保存** - JSON格式保存查询结果

### 💰 支持的代币
- USDT (Tether)
- USDC (USD Coin)
- DAI (Dai Stablecoin)
- WETH (Wrapped Ether)
- UNI (Uniswap)
- LINK (Chainlink)
- WBTC (Wrapped Bitcoin)

## 使用方法

### 1. 基本使用
```bash
cd /Users/scottliyq/go/hardhat_space/chain_monitor
python brownie_balance_checker.py
```

### 2. 网络配置
如果需要使用自定义RPC节点，请设置环境变量：

```bash
export WEB3_INFURA_PROJECT_ID="7740df87fbfb4bcbad72ac80b9e5e6fc"
export WEB3_ALCHEMY_PROJECT_ID="your_alchemy_project_id"
```

### 3. 运行示例
脚本提供三种查询模式：

#### 模式1：单个地址查询
```
请选择查询模式:
1. 查询单个地址
2. 查询多个地址  
3. 使用示例地址

请输入选择 (1-3): 1
请输入以太坊地址: 0x6503de9fe77d256d9d823f2d335ce83ece9e153f
```

#### 模式2：批量地址查询
```
请输入选择 (1-3): 2
请输入多个地址，每行一个，输入空行结束:
0x6503de9fe77d256d9d823f2d335ce83ece9e153f
0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503
[空行结束]
```

#### 模式3：示例地址
```
请输入选择 (1-3): 3
使用示例地址进行查询...
```

## 输出示例

### 单地址余额显示
```
📊 地址余额查询结果
🔗 地址: 0x6503de9fe77d256d9d823f2d335ce83ece9e153f
🌐 网络: mainnet
================================================================================
💰 ETH          1.234567
   
💰 USDT      1000.123456
   📝 合约: 0xdAC17F958D2ee523a2206206994597C13D831ec7

💰 USDC       500.000000
   📝 合约: 0xA0b86a33E6441b57ee3e4BEd34CE66fcEe8d5c4

📈 共找到 3 种有余额的资产
🔗 Etherscan: https://etherscan.io/address/0x6503de9fe77d256d9d823f2d335ce83ece9e153f
```

### 批量查询汇总
```
🔍 开始批量检查 3 个地址...
📊 [1/3] 检查地址: 0x6503de9f...e9e153f
   ✅ 找到 5 种有余额的资产
📊 [2/3] 检查地址: 0x47ac0Fb4...6D503
   ✅ 找到 8 种有余额的资产
📊 [3/3] 检查地址: 0x8894E0a0...2D4E3
   ✅ 找到 3 种有余额的资产

📊 批量查询汇总:
   0x6503de9fe77d256d9d823f2d335ce83ece9e153f: 5 种资产
   0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503: 8 种资产
   0x8894E0a0c962CB723c1976a4421c95949bE2D4E3: 3 种资产

💾 结果已保存到: temp/ethereum_balances_20251024_162030.json
```

## 编程接口

### 基本用法
```python
from brownie_balance_checker import EthereumBalanceChecker

# 创建查询器
checker = EthereumBalanceChecker("mainnet")

# 查询ETH余额
eth_balance = checker.get_eth_balance("0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
print(f"ETH余额: {eth_balance} ETH")

# 查询USDT余额
usdt_balance = checker.get_token_balance(
    "0x6503de9fe77d256d9d823f2d335ce83ece9e153f",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7"
)
print(f"USDT余额: {usdt_balance} USDT")

# 查询所有余额
all_balances = checker.get_all_balances("0x6503de9fe77d256d9d823f2d335ce83ece9e153f")
checker.display_balances("0x6503de9fe77d256d9d823f2d335ce83ece9e153f", all_balances)

# 断开连接
checker.disconnect_network()
```

### 自定义代币查询
```python
# 添加自定义代币
custom_token = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"  # UNI
balance = checker.get_token_balance(address, custom_token)

# 获取代币信息
token_info = checker.get_token_info(custom_token)
print(f"代币名称: {token_info['name']}")
print(f"代币符号: {token_info['symbol']}")
print(f"小数位数: {token_info['decimals']}")
```

## 文件输出

查询结果会保存为JSON格式：

```json
{
  "network": "mainnet",
  "query_time": "20251024_162030",
  "total_addresses": 3,
  "results": {
    "0x6503de9fe77d256d9d823f2d335ce83ece9e153f": {
      "ETH": {
        "symbol": "ETH",
        "balance": 1.234567,
        "address": "native",
        "decimals": 18
      },
      "USDT": {
        "symbol": "USDT",
        "balance": 1000.123456,
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "name": "Tether USD",
        "decimals": 6
      }
    }
  }
}
```

## 网络支持

### 支持的网络
- **mainnet** - 以太坊主网
- **goerli** - Goerli测试网
- **sepolia** - Sepolia测试网
- **polygon-main** - Polygon主网
- **arbitrum-main** - Arbitrum主网

### 切换网络
```python
# 连接到不同网络
checker = EthereumBalanceChecker("goerli")  # 测试网
checker = EthereumBalanceChecker("polygon-main")  # Polygon
```

## 故障排除

### 常见问题

1. **导入错误**
   ```
   错误: No module named 'brownie'
   解决: pip install eth-brownie
   ```

2. **网络连接失败**
   ```
   错误: 连接网络失败
   解决: 检查网络配置，设置正确的RPC URL
   ```

3. **RPC节点限制**
   ```
   错误: 请求过于频繁
   解决: 使用付费的RPC服务或添加请求延迟
   ```

### 性能优化

1. **批量查询优化**
   ```python
   # 添加延迟避免RPC限制
   import time
   time.sleep(0.1)  # 每次查询间隔100ms
   ```

2. **合约实例缓存**
   ```python
   # 脚本已自动缓存合约实例，避免重复创建
   ```

## 扩展功能

### 添加新代币
在 `TOKEN_CONTRACTS` 字典中添加新代币：

```python
TOKEN_CONTRACTS['NEW_TOKEN'] = '0x...'  # 代币合约地址
```

### 集成价格数据
可以集成CoinGecko或其他价格API：

```python
def get_token_price(symbol):
    # 调用价格API
    pass

def calculate_portfolio_value(balances):
    total_value = 0
    for token, info in balances.items():
        price = get_token_price(info['symbol'])
        value = info['balance'] * price
        total_value += value
    return total_value
```

## 安全注意事项

1. **只读操作** - 此工具只进行查询，不会发送交易
2. **RPC安全** - 使用可信的RPC节点
3. **私钥安全** - 不需要私钥，只进行查询操作
4. **网络验证** - 确认连接到正确的网络

## 许可证

本工具基于MIT许可证开源。