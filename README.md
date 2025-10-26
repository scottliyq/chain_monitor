# Chain Monitor 工具集

一个综合性的区块链监控和交互工具集，提供了从合约交互到数据分析的完整解决方案。

## 📋 目录

- [环境配置](#环境配置)
- [核心工具](#核心工具)
- [监控工具](#监控工具)
- [分析工具](#分析工具)
- [查询工具](#查询工具)
- [辅助工具](#辅助工具)
- [安装和配置](#安装和配置)

## 🔧 环境配置

确保在项目根目录下有 `.env` 文件，包含必要的环境变量：

```env
# RPC 配置
WEB3_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
MOCK_WEB3_RPC_URL=http://localhost:8545

# API 配置
ETHERSCAN_API_KEY=YOUR_ETHERSCAN_API_KEY
MORALIS_API_KEY=YOUR_MORALIS_API_KEY

# 钱包配置
PRIVATE_KEY=YOUR_PRIVATE_KEY
MOCK_ADDRESS=0x_YOUR_ADDRESS_FOR_IMPERSONATE
```

## 🎯 核心工具

### 1. 合约交互工具 (concrete_stable_interaction_v2.py)

**功能**：与 Concrete_STABLE 合约进行交互，支持存款、查询余额等操作

**使用方法**：
```bash
# 真实模式 - 连接真实网络
python concrete_stable_interaction_v2.py

# Mock模式 - 使用本地RPC和地址模拟
python concrete_stable_interaction_v2.py --mock

# Preprod模式 - 本地RPC + 真实私钥签名
python concrete_stable_interaction_v2.py --preprod

# 查看配置信息
python concrete_stable_interaction_v2.py --show-config

# 显示帮助
python concrete_stable_interaction_v2.py --help
```

**主要功能**：
- 查询 USDT 余额和授权额度
- 存款 USDT 到 Concrete_STABLE 合约
- 查询 Concrete_STABLE 代币余额
- 三种运行模式：真实、Mock、Preprod

### 2. 自动定时存款程序 (auto_deposit.py)

**功能**：自动定时执行存款操作，支持音频提醒

**使用方法**：
```bash
# 默认设置（真实模式，11 USDT，10分钟间隔）
python auto_deposit.py

# Mock模式测试
python auto_deposit.py --mock

# Preprod模式
python auto_deposit.py --preprod

# 自定义金额和间隔
python auto_deposit.py --amount 20 --interval 5

# 单次存款模式（成功后持续播放提醒音）
python auto_deposit.py --single --mock

# 快速测试
python auto_deposit.py --mock --amount 1 --interval 1
```

**参数说明**：
- `--mock`: 使用Mock模式
- `--preprod`: 使用Preprod模式
- `--amount`: 每次存款金额（USDT，默认11）
- `--interval`: 存款间隔（分钟，默认10）
- `--single`: 单次存款模式

### 3. ABI获取工具 (abi_fetcher.py)

**功能**：从多个区块链网络获取合约ABI并保存到本地

**使用方法**：
```bash
# 获取以太坊主网合约ABI
python abi_fetcher.py ethereum 0xContractAddress

# 获取其他网络的ABI
python abi_fetcher.py arbitrum 0xContractAddress
python abi_fetcher.py base 0xContractAddress
python abi_fetcher.py polygon 0xContractAddress

# 分析ABI内容
python abi_fetcher.py ethereum 0xContractAddress --analyze

# 显示支持的网络
python abi_fetcher.py --help
```

**支持的网络**：
- Ethereum (ethereum, eth, mainnet)
- Arbitrum (arbitrum, arb)
- Base (base)
- BSC (bsc, binance)
- Polygon (polygon, matic)
- Optimism (optimism, op)
- Avalanche (avalanche, avax)

## 📊 监控工具

### 4. 余额激增监控 (balance_surge_monitor.py)

**功能**：监控最近24小时USDT余额新增超过5M且48小时前余额<100k的地址

**使用方法**：
```bash
python balance_surge_monitor.py
```

### 5. 可配置协议监控 (configurable_protocol_monitor.py)

**功能**：可配置的多协议监控工具

**使用方法**：
```bash
python configurable_protocol_monitor.py
```

## 🔍 分析工具

### 6. 代币存款分析器 (token_deposit_analyzer.py)

**功能**：分析指定时间范围内的代币转账，列出交互数量大于10的所有合约

**使用方法**：
```bash
python token_deposit_analyzer.py
```

### 7. Concrete Stable分析 (analyze_concrete_stable.py)

**功能**：分析Concrete Stable合约的相关数据

**使用方法**：
```bash
python analyze_concrete_stable.py
```

### 8. 地址交互分析 (analyze_address_interactions.py)

**功能**：分析地址之间的交互关系

**使用方法**：
```bash
python analyze_address_interactions.py
```

### 9. 地址交集分析器 (address_intersection_analyzer.py)

**功能**：分析多个地址集合的交集

**使用方法**：
```bash
python address_intersection_analyzer.py
```

### 10. 批量地址分析器 (batch_address_analyzer.py)

**功能**：批量分析多个地址的相关信息

**使用方法**：
```bash
python batch_address_analyzer.py
```

## 🔎 查询工具

### 11. USDT余额查询 (usdt_balance_query.py)

**功能**：查询指定地址的USDT余额

**使用方法**：
```bash
python usdt_balance_query.py
```

### 12. USDT快速检查 (usdt_quick_check.py)

**功能**：快速检查USDT相关信息

**使用方法**：
```bash
python usdt_quick_check.py
```

### 13. 历史代币余额检查器 (historical_token_balance_checker.py)

**功能**：查询历史代币余额

**使用方法**：
```bash
# 基本用法
python historical_token_balance_checker.py

# 带参数的用法
python historical_token_balance_checker.py --address 0xYourAddress --block 18000000
```

### 14. SQLite地址查询器 (sqlite_address_querier.py)

**功能**：从SQLite数据库查询地址信息

**使用方法**：
```bash
python sqlite_address_querier.py
```

## 🛠️ 辅助工具

### 15. 区块时间转换器 (block_time_converter.py)

**功能**：区块号和时间戳之间的转换

**使用方法**：
```bash
python block_time_converter.py
```

### 16. 地址信息更新器 (address_info_updater.py)

**功能**：更新地址标签和相关信息

**使用方法**：
```bash
python address_info_updater.py
```

### 17. Moralis API客户端 (moralis_api_client.py)

**功能**：Moralis API的封装客户端

**使用方法**：
```python
# 作为模块导入使用
from moralis_api_client import MoralisAPIClient
```

### 18. 播放提醒音 (play_alert.py)

**功能**：播放音频提醒

**使用方法**：
```bash
python play_alert.py
```

### 19. 地址常量 (address_constant.py)

**功能**：定义常用的地址常量

**使用方法**：
```python
# 作为模块导入使用
from address_constant import USDT_ADDRESS, CONCRETE_STABLE_ADDRESS
```

## 📦 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥和配置
```

### 3. 创建必要目录

程序运行时会自动创建以下目录：
- `abi/` - ABI文件存储
- `logs/` - 日志文件
- `results/` - 分析结果
- `resource/` - 音频资源

### 4. 音频提醒配置

将提醒音文件 `alert.mp3` 放入 `resource/` 目录下，用于自动存款程序的音频提醒。

## 📝 使用注意事项

1. **API限制**：注意各种API的调用限制，避免超出配额
2. **网络连接**：确保网络连接稳定，特别是在进行合约交互时
3. **私钥安全**：妥善保管私钥，不要提交到版本控制系统
4. **测试环境**：建议先在Mock模式下测试，确认无误后再使用真实模式
5. **Gas费用**：真实模式下的操作会消耗Gas费用，请确保账户有足够的ETH

## 🚨 免责声明

本工具集仅供学习和研究使用。使用者应当：
- 理解区块链交易的不可逆性
- 承担因使用本工具而产生的所有风险
- 遵守相关法律法规
- 在生产环境使用前进行充分测试

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。