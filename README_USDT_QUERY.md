# USDT余额查询工具

## 概述
`usdt_balance_query.py` 是一个从 `.env` 文件读取配置的 USDT 余额查询工具，支持本地分叉网络和远程 RPC 端点。

## 功能特性

- ✅ **环境变量配置** - 从 `.env` 文件读取 RPC URL 和 Network ID
- ✅ **Web3.py 兼容性** - 支持最新版本的 Web3.py 库
- ✅ **地址验证** - 自动验证和转换地址格式
- ✅ **多币种查询** - 同时查询 USDT 和 ETH 余额
- ✅ **详细信息** - 显示区块信息、网络ID、链ID 等
- ✅ **结果保存** - 自动保存查询结果到 JSON 文件
- ✅ **错误处理** - 完善的错误处理和诊断信息

## 使用方法

### 1. 环境配置
在 `.env` 文件中设置：
```bash
# 本地 Ganache 分叉
WEB3_RPC_URL = http://127.0.0.1:8545
WEB3_NETWORK_ID = 31337

# 或者使用远程 RPC (主网)
# WEB3_RPC_URL = https://eth.llamarpc.com
# WEB3_NETWORK_ID = 1
```

### 2. 运行查询
```bash
# 查询指定地址的 USDT 余额
python usdt_balance_query.py 0x72edac30ed6f6918fe8186109b6106c292de6f3a

# 查询 Binance 热钱包
python usdt_balance_query.py 0xF977814e90dA44bFA03b6295A0616a897441aceC
```

### 3. 查看帮助
```bash
python usdt_balance_query.py
```

## 输出示例

```
🔍 USDT余额查询工具 (环境变量配置版)
==================================================
🔧 配置信息:
   RPC URL: http://127.0.0.1:8545
   Network ID: 31337
   USDT合约: 0xdAC17F958D2ee523a2206206994597C13D831ec7

🔄 连接到RPC节点...
✅ 连接成功!
   链ID: 31337
   当前区块: 23,643,321
✅ USDT合约连接成功!
   代币符号: USDT
   精度: 6

🔍 验证地址格式: 0xF977814e90dA44bFA03b6295A0616a897441aceC
✅ 地址验证成功: 0xF977814e90dA44bFA03b6295A0616a897441aceC
🔍 查询地址: 0xF977814e90dA44bFA03b6295A0616a897441aceC

📊 余额查询结果
============================================================
🏠 地址: 0xF977814e90dA44bFA03b6295A0616a897441aceC
💰 USDT余额: 22,794,505,957.500568 USDT
⛽ ETH余额: 638622.375438 ETH
📦 区块高度: 23,643,321
🕐 区块时间: 2025-10-24 07:00:11
🌐 网络ID: 31337 (链ID: 31337)
🔗 RPC端点: http://127.0.0.1:8545
============================================================

📋 原始数据:
   USDT原始余额: 22794505957500570
   USDT精度: 6
   ETH原始余额: 638622375438464935632972 wei

💾 结果已保存到: temp/usdt_balance_7441aceC_20251024_202952.json

✅ 查询完成!
```

## 技术实现

### Web3.py 兼容性修复
程序解决了新版本 Web3.py 的兼容性问题：

1. **连接验证**: 使用 `chain_id` 和 `block_number` 替代已移除的 `is_connected()`
2. **地址验证**: 使用 `Web3.isAddress()` 和 `Web3.toChecksumAddress()`
3. **单位转换**: 使用 `Web3.fromWei()` 替代实例方法

### 核心组件

- **USDTBalanceQuery 类**: 主要查询逻辑
- **环境变量管理**: 支持多种 RPC 配置方式
- **地址验证**: 完整的地址格式检查
- **结果格式化**: 人性化的结果显示
- **文件保存**: JSON 格式的结果持久化

## 测试地址

```bash
# Ganache 默认账户
0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266

# 有USDT余额的地址
0x72edac30ed6f6918fe8186109b6106c292de6f3a  # ~21K USDT

# Binance 热钱包 (大额)
0xF977814e90dA44bFA03b6295A0616a897441aceC  # ~22B USDT

# Concrete_STABLE
0x6503de9fe77d256d9d823f2d335ce83ece9e153f
```

## 文件结构

```
temp/
├── usdt_balance_92de6f3A_20251024_202942.json  # 查询结果
└── usdt_balance_7441aceC_20251024_202952.json  # 查询结果
```

## 错误处理

程序包含完善的错误处理：
- RPC 连接失败
- 地址格式错误
- 合约调用失败
- 网络ID不匹配警告

## 依赖要求

```bash
pip install web3 python-dotenv
```

## 配置选项

支持多种 RPC 配置方式：
1. `WEB3_RPC_URL` - 直接指定 RPC URL
2. `WEB3_ALCHEMY_PROJECT_ID` - Alchemy API 密钥
3. `WEB3_INFURA_PROJECT_ID` - Infura 项目 ID