# Concrete_STABLE 合约交互工具

## 概述
`concrete_stable_interaction.py` 是一个与 Concrete_STABLE 代理合约交互的工具，支持 USDT 授权和存款操作。

## 功能特性

- ✅ **环境变量配置** - 从 `.env` 文件读取私钥和 RPC 配置
- ✅ **代理合约支持** - 支持与代理合约交互
- ✅ **USDT 授权** - 支持授权指定数量或最大值给合约
- ✅ **USDT 存款** - 支持存款指定数量的 USDT
- ✅ **完整流程** - 一键执行授权+存款操作
- ✅ **余额查询** - 查询 USDT、ETH 余额和授权额度
- ✅ **交易追踪** - 显示详细的交易信息和确认状态

## 合约信息

- **Concrete_STABLE 合约**: `0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f`
- **USDT 合约**: `0xdAC17F958D2ee523a2206206994597C13D831ec7`
- **网络**: Ethereum 主网

## 环境配置

### 1. 设置 `.env` 文件
```bash
# RPC 配置
WEB3_RPC_URL = https://eth.llamarpc.com
WEB3_NETWORK_ID = 1

# 钱包私钥 (请替换为您的实际私钥)
WALLET_PRIVATE_KEY = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

### 2. 安装依赖
```bash
pip install web3 python-dotenv eth-account
```

## 使用方法

### 1. 查询余额
```bash
python concrete_stable_interaction.py balance
```

输出示例：
```
📊 当前账户状态
==================================================
🏠 钱包地址: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
💰 USDT余额: 0.000000 USDT
⛽ ETH余额: 0.000000 ETH
✅ 授权额度: 0.000000 USDT
==================================================
```

### 2. 授权 USDT

#### 授权最大值（推荐）
```bash
python concrete_stable_interaction.py approve
```

#### 授权指定数量
```bash
python concrete_stable_interaction.py approve 50000
```

### 3. 存款 USDT
```bash
python concrete_stable_interaction.py deposit 20000
```

### 4. 完整流程（授权最大值 + 存款）
```bash
python concrete_stable_interaction.py all 20000
```

## 操作示例

### 完整的交互流程

1. **查询初始状态**
   ```bash
   python concrete_stable_interaction.py balance
   ```

2. **授权 USDT 给合约**
   ```bash
   python concrete_stable_interaction.py approve
   ```

3. **存款 20,000 USDT**
   ```bash
   python concrete_stable_interaction.py deposit 20000
   ```

或者一键完成：
```bash
python concrete_stable_interaction.py all 20000
```

## 交易流程详解

### 授权流程
1. 检查当前余额和授权状态
2. 构建 `approve` 交易（授权 USDT 给 Concrete_STABLE 合约）
3. 估算 Gas 费用
4. 签名并发送交易
5. 等待交易确认
6. 显示交易结果

### 存款流程
1. 检查 USDT 余额是否充足
2. 检查授权额度是否充足
3. 构建 `deposit` 交易
4. 估算 Gas 费用
5. 签名并发送交易
6. 等待交易确认
7. 显示交易结果

## 安全注意事项

### 私钥安全
- ⚠️ **绝不要在生产环境中硬编码私钥**
- 🔒 使用环境变量或安全的密钥管理方案
- 🚫 不要将包含私钥的 `.env` 文件提交到代码仓库

### 交易确认
- ✅ 每笔交易都会等待网络确认
- 📊 显示详细的 Gas 费用估算
- 🔍 提供交易哈希用于区块链浏览器查询

### 合约风险
- 🔍 工具假设 Concrete_STABLE 是可信的代理合约
- ⚠️ 在主网使用前请充分测试
- 💡 建议先在测试网验证合约功能

## 错误处理

### 常见错误及解决方案

1. **余额不足**
   ```
   ❌ USDT余额不足: 1000.000000 < 20000.000000
   ```
   解决：确保钱包有足够的 USDT

2. **授权不足**
   ```
   ❌ 授权额度不足: 0.000000 < 20000.000000
   ```
   解决：先执行授权操作

3. **Gas 不足**
   ```
   ❌ 交易失败: insufficient funds for gas
   ```
   解决：确保钱包有足够的 ETH 支付 Gas 费

4. **网络连接问题**
   ```
   ❌ Web3连接失败: HTTPConnectionPool...
   ```
   解决：检查 RPC URL 和网络连接

## 技术实现

### 核心组件

- **ConcreteStableInteraction 类**: 主要交互逻辑
- **合约 ABI**: USDT ERC20 标准 + Concrete_STABLE 基本功能
- **交易管理**: Web3.py 交易构建、签名、发送
- **错误处理**: 完善的异常处理和用户友好的错误信息

### Gas 优化

- **USDT 授权**: 100,000 Gas 限制
- **存款操作**: 200,000 Gas 限制
- **动态 Gas Price**: 使用网络当前 Gas Price

### 兼容性

- 支持 Web3.py v6+
- 兼容主网和测试网
- 支持代理合约模式

## 开发和测试

### 测试环境
```bash
# 使用本地 Ganache 分叉
WEB3_RPC_URL = http://127.0.0.1:8545
WEB3_NETWORK_ID = 31337
```

### 主网环境
```bash
# 使用公共 RPC 或您的节点
WEB3_RPC_URL = https://eth.llamarpc.com
WEB3_NETWORK_ID = 1
```

## 扩展功能

### 可添加的功能
- 提取/赎回操作
- 批量操作支持
- 交易历史查询
- 更多 DeFi 协议集成
- 实时价格查询

### 自定义配置
- 可调整的 Gas 限制
- 自定义 Gas Price 策略
- 多钱包支持
- 代理合约自动检测