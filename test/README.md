# Test Directory

该目录包含项目的测试脚本、演示程序和调试工具。

## 文件说明

### 测试脚本
- `test_token_addresses.py` - 测试多链代币地址常量功能
- `test_hyperliquid_sdk.py` - Hyperliquid SDK测试

### 演示程序
- `balance_surge_demo.py` - 余额激增监控使用示例
- `demo_analyzer.py` - 地址交互分析演示

### 调试工具
- `simple_debug.py` - 简化的合约函数调试工具

### Jupyter Notebook
- `test.ipynb` - 测试和实验用的Jupyter Notebook

## 运行说明

由于这些脚本现在位于 test 子目录中，运行时有两种方式：

### 方式1：从项目根目录运行
```bash
cd /path/to/chain_monitor
python test/test_token_addresses.py
python test/balance_surge_demo.py
```

### 方式2：进入test目录运行
```bash
cd /path/to/chain_monitor/test
python test_token_addresses.py
python balance_surge_demo.py
```

## 注意事项

- 所有测试脚本都已经配置了正确的导入路径，可以访问上级目录的模块
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