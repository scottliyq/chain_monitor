# 代理合约ABI获取功能说明

## 功能概述

现在 `abi_fetcher.py` 支持自动检测代理合约并获取其实现合约的ABI。

## 主要改进

### 1. 自动代理检测
- 获取ABI前会自动检查地址是否为代理合约
- 如果是代理合约，会自动获取实现合约的地址
- 获取实现合约的完整ABI而不是代理合约的简单ABI

### 2. 代理信息记录
保存的ABI文件会包含完整的代理信息：
```json
{
  "network": "bsc",
  "contract_address": "0x实现合约地址",
  "is_proxy": true,
  "proxy_address": "0x代理合约地址",
  "implementation_address": "0x实现合约地址",
  "abi": [...]
}
```

### 3. 命令行选项
- 默认行为：自动检测并获取实现合约ABI
- `--no-proxy-check`：跳过代理检测，直接获取当前地址的ABI

## 使用示例

### 示例1：获取BSC上的USDT合约ABI（可能是代理）
```bash
python abi_fetcher.py bsc 0x55d398326f99059fF775485246999027B3197955 --name USDT_BSC
```

输出示例：
```
🔍 检测到代理合约!
   代理地址: 0x55d398326f99059fF775485246999027B3197955
   实现地址: 0x实现合约地址
🔄 将获取实现合约的ABI: 0x实现合约地址
✅ 成功获取ABI，包含 XX 个函数/事件
```

### 示例2：跳过代理检测
```bash
python abi_fetcher.py bsc 0x55d398326f99059fF775485246999027B3197955 --no-proxy-check
```

### 示例3：获取以太坊上的代理合约
```bash
python abi_fetcher.py ethereum 0xdAC17F958D2ee523a2206206994597C13D831ec7 --name USDT --analyze
```

### 示例4：获取Arbitrum上的合约
```bash
python abi_fetcher.py arbitrum 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1 --name WETH
```

## 支持的网络

所有Etherscan支持的网络都支持代理检测：
- Ethereum Mainnet
- Arbitrum One
- Base
- BNB Smart Chain (BSC)
- Polygon
- Optimism
- Avalanche C-Chain

## 代理合约类型支持

支持常见的代理合约模式：
- EIP-1967 透明代理
- UUPS代理
- Beacon代理
- 其他Etherscan能识别的代理类型

## 文件命名

- 代理合约：使用**代理地址**作为文件名，但保存的是**实现合约的ABI**
- 普通合约：直接使用合约地址作为文件名

示例：
```
bsc_USDT_BSC_0x55d398326f99059fF775485246999027B3197955.json  # 代理地址作为文件名
```

文件内容包含实现合约的完整ABI和代理信息。

## 技术实现

1. **代理检测**：使用Etherscan API的 `getsourcecode` 接口
2. **实现地址提取**：从返回的 `Implementation` 字段获取
3. **ABI获取**：使用实现合约地址调用 `getabi` 接口
4. **元数据保存**：在JSON文件中记录代理关系

## 注意事项

1. 需要有效的 `ETHERSCAN_API_KEY` 环境变量
2. 代理检测会额外调用一次API（先检测代理，再获取ABI）
3. 如果不需要代理检测，使用 `--no-proxy-check` 可以节省API调用
4. 文件使用代理地址命名便于后续查找和使用
