# Lista MEV合约Withdraw工具使用说明

## 功能说明

这个脚本用于与BSC网络上的Lista MEV合约进行交互，调用`withdraw`方法从合约中取出资金。

## 参考交易

- 交易哈希: [0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f](https://bscscan.com/tx/0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f)
- 合约地址: `0x6402d64F035E18F9834591d3B994dFe41a0f162D`
- 网络: BSC (BNB Smart Chain)

## 环境要求

### 1. 依赖包
```bash
pip install web3 python-dotenv eth-account
```

### 2. 环境变量配置

在`.env`文件中需要配置以下变量：

```bash
# BSC RPC节点URL
BSC_RPC_URL=https://bsc-dataseed1.binance.org

# 钱包私钥（用于签名交易）
WALLET_PRIVATE_KEY=0x你的私钥
```

### 3. ABI文件

ABI文件已保存在：
```
abi/bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json
```

## 使用方法

### 基本使用

```bash
python lista_withdraw.py
```

程序会：
1. ✅ 连接到BSC网络
2. 💼 加载钱包账户
3. 📄 加载合约ABI
4. 💰 检查当前余额
5. 📋 显示合约信息
6. ⚠️ 询问是否确认执行
7. 🔄 执行withdraw操作（取出10个代币）
8. ⏳ 等待交易确认
9. ✅ 显示结果和更新后的余额

### 自定义取出金额

如果需要修改取出金额，编辑`lista_withdraw.py`中的这一行：

```python
# 调用withdraw方法，取出10个代币
amount = 10  # 修改这里的数值
```

## Withdraw函数签名

```solidity
function withdraw(
    uint256 assets,      // 要取出的资产数量（wei）
    address receiver,    // 接收地址
    address owner        // 所有者地址
) returns (uint256 shares)
```

### 参数说明

- `assets`: 要取出的资产数量（单位：wei）
- `receiver`: 接收地址（默认为当前钱包地址）
- `owner`: 所有者地址（默认为当前钱包地址）

## 输出示例

```
🚀 Lista MEV合约Withdraw工具
============================================================
✅ 成功连接到BSC网络
🌐 RPC URL: https://bsc-dataseed1.binance.org
💼 钱包地址: 0x你的地址
📄 加载ABI文件: abi/bsc_lista_mev_0x6402d64F035E18F9834591d3B994dFe41a0f162D.json
✅ 成功加载ABI，包含 157 个函数/事件
✅ 找到withdraw函数
   参数: ['assets:uint256', 'receiver:address', 'owner:address']
💰 BNB余额: 0.123456 BNB
💎 合约中的资产余额: 100.000000

============================================================
📋 合约信息
============================================================
📍 合约地址: 0x6402d64F035E18F9834591d3B994dFe41a0f162D
📛 名称: Lista Vault
🔖 符号: LISTA
🔢 小数位数: 18
💎 总资产: 1000000.00

⚠️ 即将执行withdraw操作，取出 10 个代币
是否继续? (y/n): y

============================================================
🔄 准备调用withdraw方法
============================================================
📍 合约地址: 0x6402d64F035E18F9834591d3B994dFe41a0f162D
💰 取出金额: 10 (wei: 10000000000000000000)
📬 接收地址: 0x你的地址
👤 所有者地址: 0x你的地址
🔢 Nonce: 123
⛽ Gas Price: 3.00 Gwei
🔨 构建交易...
✅ 交易构建成功
   Gas Limit: 500000
📊 估算Gas: 150000
   调整后Gas Limit: 180000
✍️ 签名交易...
📤 发送交易...
✅ 交易已发送!
📝 交易哈希: 0xabcd1234...
🔗 查看交易: https://bscscan.com/tx/0xabcd1234...
⏳ 等待交易确认...

============================================================
✅ 交易成功!
============================================================
📦 区块号: 12345678
⛽ Gas使用: 150000
💸 交易费用: 0.000450 BNB

============================================================
📊 更新后的余额:
============================================================
💰 BNB余额: 0.122006 BNB
💎 合约中的资产余额: 90.000000

✅ 操作完成!
🔗 交易链接: https://bscscan.com/tx/0xabcd1234...
```

## 安全注意事项

⚠️ **重要提醒**：

1. **私钥安全**：
   - 永远不要将私钥提交到git仓库
   - 确保`.env`文件在`.gitignore`中
   - 不要在公共场合分享私钥

2. **交易确认**：
   - 执行前会要求确认
   - 仔细检查钱包地址和金额
   - 确保账户有足够的BNB支付gas费

3. **网络确认**：
   - 确认连接到正确的网络（BSC主网）
   - 检查合约地址是否正确
   - 验证RPC节点是否可靠

4. **余额检查**：
   - 执行前检查合约中是否有足够的余额
   - 确保有足够的BNB支付交易费用

## 错误处理

### 常见错误

1. **无法连接到网络**
   ```
   ❌ 无法连接到BSC网络
   ```
   解决：检查RPC_URL是否正确，网络是否可访问

2. **私钥未配置**
   ```
   ❌ 未找到WALLET_PRIVATE_KEY环境变量
   ```
   解决：在`.env`文件中添加`WALLET_PRIVATE_KEY`

3. **余额不足**
   ```
   ❌ insufficient funds for gas * price + value
   ```
   解决：确保钱包有足够的BNB

4. **权限不足**
   ```
   ❌ execution reverted
   ```
   解决：检查是否有权限从合约withdraw

## 代码结构

```python
ListaWithdraw类
├── __init__()           # 初始化连接和账户
├── load_contract()      # 加载ABI和创建合约实例
├── check_balance()      # 检查余额
├── withdraw()           # 执行withdraw操作
└── get_contract_info()  # 获取合约信息
```

## 进阶使用

### 自定义接收地址

```python
# 修改withdraw调用
lista.withdraw(
    amount=10,
    receiver="0x接收地址",
    owner="0x所有者地址"
)
```

### 调整Gas设置

```python
# 在withdraw方法中修改
tx = self.contract.functions.withdraw(...).build_transaction({
    'gas': 300000,        # 调整gas limit
    'gasPrice': gas_price * 2,  # 使用2倍gas price加速
    ...
})
```

### 使用不同的RPC节点

```bash
# 在.env中添加备用节点
BSC_RPC_URL=https://bsc-dataseed2.binance.org
# 或使用第三方节点
BSC_RPC_URL=https://bsc.publicnode.com
```

## 相关资源

- [BSC官方文档](https://docs.bnbchain.org/)
- [Web3.py文档](https://web3py.readthedocs.io/)
- [BscScan](https://bscscan.com/)
- [参考交易](https://bscscan.com/tx/0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f)
