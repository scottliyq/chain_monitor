# Test Directory

该目录主要包含项目的测试脚本。

## 文件说明

### 测试脚本
- `test_token_addresses.py` - 测试多链代币地址常量功能
- `test_hyperliquid_sdk.py` - Hyperliquid SDK测试

演示脚本已移动到 `examples/`，调试脚本已移动到 `debug/`。

## 运行说明

这些脚本现在位于 `tests/` 子目录中，推荐从项目根目录运行：

### 方式1：从项目根目录运行
```bash
cd /path/to/chain_monitor
python tests/test_token_addresses.py
python examples/balance_surge_demo.py
```

## 注意事项

- 所有测试脚本都已经配置了正确的导入路径，可以访问 `src/` 中的模块
- 运行测试前请确保环境变量已正确配置（.env文件）
- 某些测试可能需要网络连接和API密钥

## 环境变量要求

运行测试前请确保以下环境变量已设置：

```bash
# 必需的环境变量
ETHERSCAN_API_KEY=你的_etherscan_api_密钥

# 可选的环境变量
WEB3_RPC_URL=https://eth.llamarpc.com
WEB3_NETWORK_ID=1
```
