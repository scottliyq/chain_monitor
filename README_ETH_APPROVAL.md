# 以太坊USDT授权脚本使用说明

## 功能描述
`eth_usdt_approval.py` 是一个用于在以太坊主网上授权USDT使用的Python脚本。它可以：

1. 检查钱包ETH和USDT余额
2. 查看当前USDT授权额度  
3. 向指定合约授权USDT使用权限
4. 处理代理合约的情况
5. 支持EIP-1559和legacy交易类型
6. 提供模拟和实际发送两种模式

## 目标合约
- **目标合约地址**: `0x6503de9fe77d256d9d823f2d335ce83ece9e153f`
- **USDT合约地址**: `0xdAC17F958D2ee523a2206206994597C13D831ec7`

## 安装依赖

```bash
pip install web3
```

## 环境变量设置

### 必需环境变量
```bash
# 以太坊RPC节点URL（推荐使用Infura、Alchemy等）
export ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"

# 私钥（可选，如果只查询状态可以不设置）
export ETH_PRIVATE_KEY="your_private_key_here"
```

### RPC节点获取方式
1. **Infura**: https://infura.io/
2. **Alchemy**: https://alchemy.com/
3. **QuickNode**: https://quicknode.com/

## 使用方法

### 1. 基本使用
```bash
cd /Users/scottliyq/go/hardhat_space/chain_monitor
python eth_usdt_approval.py
```

### 2. 只查询状态（无需私钥）
如果没有设置私钥，脚本会进入只读模式，可以查询任意地址的状态。

### 3. 交互式操作
脚本运行后会显示菜单：
```
请选择操作:
1. 授权USDT (模拟)
2. 授权USDT (实际发送)  
3. 检查状态
4. 退出
```

## 安全注意事项

### ⚠️ 重要警告
1. **私钥安全**: 永远不要在代码中硬编码私钥
2. **测试先行**: 首次使用建议用模拟模式测试
3. **Gas费用**: 确保账户有足够ETH支付gas费用
4. **网络确认**: 确认连接的是以太坊主网

### 🔐 私钥管理建议
```bash
# 方法1: 环境变量（推荐）
export ETH_PRIVATE_KEY="0x..."

# 方法2: .env文件
echo "ETH_PRIVATE_KEY=0x..." > .env

# 方法3: 硬件钱包（最安全）
# 可以修改代码支持硬件钱包签名
```

## 代码功能详解

### 主要类: USDTApprovalManager

#### 初始化
```python
manager = USDTApprovalManager(rpc_url, private_key=None)
```

#### 查询方法
```python
# 获取USDT余额
balance = manager.get_usdt_balance(address)

# 获取授权额度
allowance = manager.get_usdt_allowance(owner, spender)

# 检查代理实现
impl = manager.check_proxy_implementation()
```

#### 授权方法
```python
# 模拟授权
result = manager.approve_usdt(amount, dry_run=True)

# 实际授权
result = manager.approve_usdt(amount, dry_run=False)
```

## 代理合约处理

脚本会自动检测代理合约：

1. **方法调用**: 尝试调用 `implementation()` 方法
2. **存储槽读取**: 使用EIP-1967标准存储槽
3. **自动适配**: 根据检测结果调整调用方式

## Gas费用优化

### EIP-1559支持
- 自动检测网络支持情况
- 动态计算base fee和priority fee
- 智能回退到legacy交易

### Gas估算
- 自动估算交易gas限制
- 增加20%安全余量
- 实时显示预计费用

## 错误处理

### 常见错误及解决方案

1. **连接失败**
   ```
   错误: 无法连接到以太坊节点
   解决: 检查RPC_URL是否正确，网络是否正常
   ```

2. **余额不足**
   ```
   错误: 余额不足
   解决: 确保账户有足够的USDT和ETH
   ```

3. **Gas估算失败**
   ```
   错误: gas估算失败
   解决: 脚本会使用默认值，通常可以正常执行
   ```

4. **交易失败**
   ```
   错误: 交易被回滚
   解决: 检查合约状态，可能需要调整gas价格
   ```

## 输出示例

### 状态检查
```
📊 状态检查 - 0x742d35Cc6635C0532925a3b8d5c9b37D36d2...
============================================================
💰 ETH余额: 1.234567 ETH
💰 USDT余额: 10,000.00 USDT  
🔐 USDT授权额度: 0.00 USDT
📋 代理合约实现地址: 0x...
⛽ Gas (EIP-1559): base=20.5 gwei
```

### 授权交易
```
🎯 准备授权 1,000.00 USDT 给合约 0x6503de9fe77d256d9d823f2d335ce83ece9e153f
📊 当前USDT余额: 10,000.00
📊 当前授权额度: 0.00 USDT
⛽ 估算gas限制: 65,000
💰 预计交易费用: 0.001300 ETH
✅ 交易已发送!
🔗 交易哈希: 0x...
🔗 Etherscan: https://etherscan.io/tx/0x...
✅ 交易确认成功!
📊 新授权额度: 1,000.00 USDT
```

## 扩展功能

### 批量授权
可以修改脚本支持批量授权多个合约：

```python
contracts = [
    "0x6503de9fe77d256d9d823f2d335ce83ece9e153f",
    "0x...",  # 其他合约地址
]

for contract in contracts:
    result = manager.approve_usdt_to_contract(contract, amount)
```

### 定时检查
可以添加定时检查功能：

```python
import schedule
import time

def check_allowances():
    for contract in contracts:
        allowance = manager.get_usdt_allowance(my_address, contract)
        if allowance < threshold:
            print(f"⚠️ {contract} 授权额度不足: {allowance}")

schedule.every(1).hours.do(check_allowances)
```

## 技术支持

如果遇到问题，请检查：

1. **网络连接**: 确保RPC节点可访问
2. **API密钥**: 确保Infura/Alchemy API密钥有效
3. **账户余额**: 确保有足够的ETH和USDT
4. **合约状态**: 在Etherscan上确认合约状态正常
5. **Gas价格**: 网络拥堵时可能需要提高gas价格

## 免责声明

本脚本仅供学习和研究使用。使用前请：

- 充分理解代码逻辑
- 在测试网络上验证
- 确保私钥安全
- 自行承担使用风险

作者不对使用本脚本造成的任何损失负责。