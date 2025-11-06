# Lista Withdraw 快速开始

## 📋 文件说明

- `lista_withdraw.py` - 主程序，执行withdraw操作
- `test_lista_connection.py` - 测试连接和ABI加载
- `LISTA_WITHDRAW_README.md` - 完整使用文档

## �� 快速开始

### 1. 测试连接（推荐先执行）

```bash
python test_lista_connection.py
```

这会测试：
- ✅ BSC网络连接
- ✅ 钱包加载
- ✅ ABI文件加载
- ✅ 合约信息获取
- ✅ 余额查询

### 2. 执行Withdraw

```bash
python lista_withdraw.py
```

这会：
- 🔄 调用withdraw方法
- 💰 取出10个代币
- ⏳ 等待交易确认
- ✅ 显示结果

## ⚙️ 配置检查

确保`.env`文件包含：

```bash
BSC_RPC_URL=https://bsc-dataseed1.binance.org
WALLET_PRIVATE_KEY=0x你的私钥
```

## 📝 参考交易

[0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f](https://bscscan.com/tx/0x3dc2f3c361df0e6d37b2b3deb188bbbf99211f10c6a621d98ffaa703b7ae5a2f)

## 🔧 修改取出金额

编辑 `lista_withdraw.py` 第 298 行：

```python
amount = 10  # 修改这个数值
```

## ⚠️ 安全提醒

- 私钥不要泄露
- 确认地址和金额
- 确保有足够的BNB支付gas
