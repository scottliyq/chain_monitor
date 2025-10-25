# Chain Monitor - 区块链监控工具集

一个功能完整的以太坊区块链监控和分析工具集，支持 USDT 大额转账监控、余额查询、合约交互、地址分析等多种功能。

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制并修改环境变量模板：
```bash
cp .env.template .env
```

编辑 `.env` 文件，填入您的配置：
```env
# Etherscan API 密钥（必需）
ETHERSCAN_API_KEY=你的_etherscan_api_密钥

# RPC 配置（可选，使用免费节点或付费服务）
WEB3_RPC_URL=https://eth.llamarpc.com
WEB3_NETWORK_ID=1

# 钱包私钥（仅交互功能需要）
WALLET_PRIVATE_KEY=0x...

# Mock 模式配置（测试用）
MOCK_WALLET_ADDRESS=0xF977814e90dA44bFA03b6295A0616a897441aceC
```

### 3. 快速启动
```bash
# 使用统一启动器（推荐）
python monitor_launcher.py

# 或直接使用具体工具
python usdt_deposit_analyzer.py '2025-10-24 00:00:00' '2025-10-24 23:59:59' 1000000
```

---

## 📋 功能目录

- [🔍 USDT 大额转账分析](#-usdt-大额转账分析)
- [📈 余额激增监控](#-余额激增监控)
- [🌐 地址交互分析](#-地址交互分析)
- [🎯 Concrete_STABLE 专项分析](#-concrete_stable-专项分析)
- [💰 余额查询工具](#-余额查询工具)
- [🔗 合约部署追踪](#-合约部署追踪)
- [🤝 合约交互工具](#-合约交互工具)
- [🎭 Mock 模式开发](#-mock-模式开发)
- [🔐 USDT 授权工具](#-usdt-授权工具)

---

## 🔍 USDT 大额转账分析

### 功能特性
- **时间范围查询**: 支持 UTC 时间参数，精确到秒
- **分段查询**: 自动将大时间范围拆分为 10 分钟段，绕过 API 10k 记录限制
- **智能过滤**: 支持最小金额阈值过滤
- **合约识别**: 自动识别已知的 DeFi 协议和交易所地址
- **详细统计**: 提供转账统计、地址分析和趋势报告

### 使用方法
```bash
# 基本用法：分析指定时间范围的大额转账
python usdt_deposit_analyzer.py '2025-10-24 00:00:00' '2025-10-24 23:59:59' 1000000

# 分析最近1小时超过500万的转账
python usdt_quick_check.py 5000000 1
```

### 输出示例
```
🔍 USDT 大额转账分析报告
================================================================================
📊 分析时间段: 2025-10-24 00:00:00 UTC 至 2025-10-24 23:59:59 UTC
🧱 区块范围: 21,000,000 - 21,007,200 (共7,200个区块)
📈 总转账数: 45,234
💰 大额转账数: 156
💵 大额转账总金额: 2,500,000,000.00 USDT
📤 唯一发送地址: 89
📥 唯一接收地址: 123
🎯 最小金额阈值: 1,000,000 USDT

💎 交互次数最多的合约 (前10):
================================================================================
1. Binance (0xF977814e90dA44bFA03b6295A0616a897441aceC)
   💰 总金额: 890,234,567.89 USDT | 📊 交易次数: 45
2. UniswapV3Pool (0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36)
   💰 总金额: 234,567,890.12 USDT | 📊 交易次数: 23
```

---

## 📈 余额激增监控

### 监控目标
发现最近24小时内余额大幅增长的地址，用于识别：
- 大额资金流入
- 新的大户地址
- 异常资金聚集

### 监控条件
- 最近24小时 USDT 余额新增 ≥ 可配置阈值（默认5M USDT）
- 48小时前余额 < 可配置阈值（默认100K USDT）

### 使用方法
```bash
# 监控余额激增（24小时新增≥1000万，48小时前<50万）
python balance_surge_monitor.py 10000000 500000

# 或使用多功能工具
python usdt_quick_check.py
# 然后选择功能 2
```

### 输出示例
```
🎉 发现 3 个符合条件的地址!
================================================================================
📊 总计余额增长: 18,500,000.00 USDT
📊 平均增长倍数: 25,600.3%

🏆 #1 地址: 0x1234567890abcdef1234567890abcdef12345678
   📊 48小时前余额: 50,000.00 USDT
   📊 当前余额: 8,050,000.00 USDT
   📈 余额增长: 8,000,000.00 USDT
   📥 24小时接收: 8,100,000.00 USDT
   📊 增长倍数: 16,000.0%
   🔗 查看详情: https://etherscan.io/address/0x1234567890abcdef1234567890abcdef12345678
```

---

## 🌐 地址交互分析

### 功能特性
- 分析指定地址的所有 USDT 转账记录
- 识别主要的资金来源和去向
- 统计交互频率和金额
- 生成详细的交互报告和地址列表

### 使用方法
```bash
# 分析任意地址的交互（最近30天）
python balance_surge_monitor.py
# 然后选择功能 2

# 地址交集分析
python address_intersection_analyzer.py usdt_results.json concrete_stable_addresses.txt
```

### 特色功能
- 🎯 双向交互分析（发送和接收）
- 📊 交互模式识别
- 💰 大额交互地址筛选
- ⏰ 时间模式分析
- 📝 自动生成地址列表文件

---

## 🎯 Concrete_STABLE 专项分析

### 目标合约
- **Concrete_STABLE 合约**: `0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f`

### 功能特性
- 专门分析 Concrete_STABLE 地址的交互模式
- 识别与该合约交互的所有地址
- 统计资金流入流出情况
- 生成专项分析报告

### 使用方法
```bash
# 分析最近7天的 Concrete_STABLE 交互
python analyze_concrete_stable.py 7

# 分析最近30天
python analyze_concrete_stable.py 30
```

---

## 💰 余额查询工具

### Brownie 框架查询工具

支持 ETH 和主流 ERC20 代币的余额查询。

#### 支持的代币
- USDT (Tether)
- USDC (USD Coin)  
- DAI (Dai Stablecoin)
- WETH (Wrapped Ether)
- UNI (Uniswap)
- LINK (Chainlink)
- WBTC (Wrapped Bitcoin)

#### 使用方法
```bash
# 运行 Brownie 余额查询
python brownie_balance_checker.py

# 或使用 Web3.py 版本
python usdt_balance_query.py 0x地址
```

#### 输出示例
```
📊 地址余额查询结果
🔗 地址: 0x6503de9fe77d256d9d823f2d335ce83ece9e153f
🌐 网络: mainnet
================================================================================
💰 ETH          1.234567
💰 USDT      1000.123456 (合约: 0xdAC17F958D2ee523a2206206994597C13D831ec7)
💰 USDC       500.000000 (合约: 0xA0b86a33E6441b57ee3e4BEd34CE66fcEe8d5c4)
📈 共找到 3 种有余额的资产
```

### 环境变量配置版本

从 `.env` 文件读取配置的 USDT 余额查询工具。

#### 特性
- ✅ 支持本地分叉网络和远程 RPC 端点
- ✅ Web3.py 最新版本兼容
- ✅ 地址验证和格式转换
- ✅ 详细的网络信息显示
- ✅ 结果自动保存为 JSON

---

## 🔗 合约部署追踪

### 功能特性
- 🔍 智能查找指定地址部署的所有合约
- 📊 获取合约详细信息（部署时间、Gas费用、代码大小等）
- 🏷️ 从 Etherscan 获取合约元数据
- 💾 生成 JSON 和 TXT 格式报告
- 🎭 提供模拟数据演示

### 使用方法
```bash
# 查找最近7天的合约部署
python contract_deployment_tracker.py 0x地址

# 查找最近3天的合约部署  
python contract_deployment_tracker.py 0x地址 3

# 运行演示版本（无需API密钥）
python contract_deployment_demo.py 0x地址
```

### 知名地址示例
- `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` - Vitalik Buterin
- `0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984` - Uniswap相关
- `0x4f2083f5fBede34C2714aF59e9076b4Ebf31e5F0` - OpenZeppelin

---

## 🤝 合约交互工具

### Concrete_STABLE 交互工具

与 Concrete_STABLE 代理合约进行交互的专用工具。

#### 功能特性
- ✅ USDT 授权和存款操作
- ✅ 完整的交易流程管理
- ✅ 余额和授权额度查询
- ✅ 详细的交易追踪
- ✅ 代理合约支持

#### 使用方法
```bash
# 查询余额
python concrete_stable_interaction.py balance

# 授权USDT（最大值）
python concrete_stable_interaction.py approve

# 授权指定数量
python concrete_stable_interaction.py approve 50000

# 存款USDT
python concrete_stable_interaction.py deposit 20000

# 一键完成（授权+存款）
python concrete_stable_interaction.py all 20000
```

#### 安全注意事项
- ⚠️ 绝不要硬编码私钥
- � 使用环境变量管理密钥
- 🚫 不要提交包含私钥的文件
- 🔍 在主网使用前请充分测试

---

## 🎭 Mock 模式开发

### 功能特性
Mock 模式允许在本地分叉环境中测试合约交互，无需真实私钥。

#### 核心优势
- ✅ **无需真实私钥**即可测试合约交互
- ✅ **支持任意地址模拟**，可测试各种场景
- ✅ **完整的交易流程**，包括 Gas 估算和确认
- ✅ **开发友好**，显著降低测试成本和风险

#### 使用方法
```bash
# 启动本地分叉（需要 Hardhat/Ganache）
# 然后使用 Mock 模式

# 查询余额（Mock模式）
python concrete_stable_interaction.py balance --mock

# 授权USDT（Mock模式）
python concrete_stable_interaction.py approve 50000 --mock

# 存款USDT（Mock模式）
python concrete_stable_interaction.py deposit 20000 --mock
```

#### 环境配置
```bash
# 本地 Ganache 分叉配置
WEB3_RPC_URL = http://127.0.0.1:8545
WEB3_NETWORK_ID = 31337
MOCK_WALLET_ADDRESS = 0xF977814e90dA44bFA03b6295A0616a897441aceC  # Binance热钱包
```

#### 测试结果
```
✅ 余额查询: 成功显示 Binance 热钱包余额
✅ USDT 授权: 交易成功，授权额度正确更新
❌ USDT 存款: 交易回滚，需要进一步调试合约
```

---

## 🔐 USDT 授权工具

### 功能描述
专用的以太坊 USDT 授权脚本，支持向指定合约授权 USDT 使用权限。

#### 目标合约
- **目标合约地址**: `0x6503de9fe77d256d9d823f2d335ce83ece9e153f`
- **USDT合约地址**: `0xdAC17F958D2ee523a2206206994597C13D831ec7`

#### 功能特性
- 检查钱包 ETH 和 USDT 余额
- 查看当前 USDT 授权额度
- 向指定合约授权 USDT 使用权限
- 处理代理合约的情况
- 支持 EIP-1559 和 legacy 交易类型
- 提供模拟和实际发送两种模式

#### 使用方法
```bash
# 基本使用
python eth_usdt_approval.py

# 环境变量设置
export ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
export ETH_PRIVATE_KEY="your_private_key_here"
```

#### 交互式菜单
```
请选择操作:
1. 授权USDT (模拟)
2. 授权USDT (实际发送)  
3. 检查状态
4. 退出
```

#### 安全建议
```bash
# 推荐的私钥管理方式
export ETH_PRIVATE_KEY="0x..."  # 环境变量（推荐）
echo "ETH_PRIVATE_KEY=0x..." > .env  # .env文件
# 硬件钱包集成（最安全）
```

---

## 🛠️ 系统架构

### 核心组件

#### 时间转换系统
- **block_time_converter.py**: 独立的 UTC 时间到区块号转换工具
- 支持多种时间格式输入
- 完整的时区处理和验证
- 集成 Etherscan API V2

#### 地址管理系统  
- **address_constant.py**: 集中化的合约地址管理
- 包含主流 DeFi 协议和交易所地址
- 支持地址别名和分类

#### 查询优化系统
- **分段查询**: 自动将大时间范围拆分为小段，绕过 API 限制
- **智能缓存**: 避免重复的 API 调用
- **错误重试**: 自动处理网络异常和 API 限制

### 文件组织

```
chain_monitor/
├── 🚀 monitor_launcher.py          # 统一启动器
├── 📊 usdt_deposit_analyzer.py     # USDT大额转账分析
├── 📈 balance_surge_monitor.py     # 余额激增监控
├── 🌐 address_intersection_analyzer.py  # 地址交集分析
├── 🎯 analyze_concrete_stable.py   # Concrete_STABLE专项分析
├── 💰 usdt_balance_query.py        # USDT余额查询
├── 🔗 contract_deployment_tracker.py  # 合约部署追踪
├── 🤝 concrete_stable_interaction.py  # 合约交互工具
├── 🔐 eth_usdt_approval.py         # USDT授权工具
├── ⚙️ block_time_converter.py      # 时间转换工具
├── 📝 address_constant.py          # 地址常量管理
└── 📚 README.md                    # 本文档
```

---

## ⚙️ 高级配置

### API 配置
```env
# Etherscan API
ETHERSCAN_API_KEY=你的API密钥

# RPC 节点
WEB3_RPC_URL=https://eth.llamarpc.com
# 或付费服务
# WEB3_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_PROJECT_ID
# WEB3_RPC_URL=https://mainnet.infura.io/v3/YOUR_PROJECT_ID
```

### 数据库集成
```env
# PostgreSQL 配置
db_url=postgresql://user:password@localhost:5432/database
```

### 通知设置
```env
# IFTTT Webhook
IFTTT_KEY=你的_ifttt_webhook_密钥
```

### 性能优化
- 使用付费 API 密钥提高请求限制
- 启用数据库缓存减少重复查询
- 调整分段查询间隔优化性能

---

## � API 限制和注意事项

### Etherscan API 限制
- **免费版**: 每秒5次请求，每天100,000次请求
- **建议**: 生产环境使用付费 API 密钥

### 网络要求
- **稳定连接**: 确保网络连接稳定，避免请求超时
- **RPC 节点**: 使用可靠的 RPC 节点服务

### 数据准确性
- **延迟性**: 监控结果基于 Etherscan 数据，可能存在轻微延迟
- **实时性**: 大额转账监控建议结合多个数据源

### 安全考虑
1. **私钥安全**: 永远不要将私钥提交到公共代码仓库
2. **网络验证**: 确认连接到正确的网络
3. **交易确认**: 在主网操作前务必在测试网验证
4. **法律合规**: 使用本工具请遵守相关法律法规

---

## 🔧 故障排除

### 常见问题

#### 1. API 相关错误
```bash
# 错误：API错误 NOTOK
# 解决：检查 ETHERSCAN_API_KEY 是否正确设置
export ETHERSCAN_API_KEY="你的真实API密钥"
```

#### 2. 网络连接问题
```bash
# 错误：Web3连接失败
# 解决：检查 RPC URL 或使用不同的 RPC 提供商
export WEB3_RPC_URL="https://eth.llamarpc.com"
```

#### 3. 依赖安装问题
```bash
# 安装所有依赖
pip install -r requirements.txt

# 或手动安装核心依赖
pip install web3 requests python-dotenv eth-account
```

#### 4. 权限问题
```bash
# 确保有文件写入权限
chmod 755 temp/
```

### 调试建议
1. 使用 `-v` 或 `--verbose` 参数查看详细日志
2. 检查 `.env` 文件配置
3. 先使用演示版本确认功能正常
4. 查看控制台输出的详细错误信息

---

## 🎯 使用场景

### 1. DeFi 研究
- 监控大额资金流动
- 分析协议交互模式
- 发现新兴的 DeFi 项目

### 2. 市场分析
- 识别巨鲸动向
- 监控交易所资金流
- 分析市场情绪指标

### 3. 安全审计
- 检查合约部署活动
- 分析资金流向异常
- 监控可疑地址活动

### 4. 投资决策
- 跟踪聪明钱流向
- 发现潜在投资机会
- 风险管理和预警

---

## 📈 扩展功能

### 计划中的功能
- [ ] 支持更多区块链网络（BSC、Polygon、Arbitrum）
- [ ] 实时 WebSocket 监控
- [ ] 机器学习驱动的异常检测
- [ ] 图形化界面和仪表板
- [ ] 移动端应用
- [ ] API 服务接口

### 贡献指南
欢迎提交 Issue 和 Pull Request 来改进这个项目：

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/新功能`)
3. 提交更改 (`git commit -am '添加新功能'`)
4. 推送到分支 (`git push origin feature/新功能`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 👥 致谢

感谢以下项目和服务：
- [Etherscan](https://etherscan.io/) - 提供可靠的区块链数据 API
- [Web3.py](https://web3py.readthedocs.io/) - 以太坊 Python 库
- [OpenZeppelin](https://openzeppelin.com/) - 智能合约标准
- 所有贡献者和用户的反馈

---

**📞 技术支持**  
如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 查看项目 Wiki 文档
- 参与社区讨论

**⚠️ 免责声明**  
本工具仅供学习和研究使用。使用前请充分了解相关风险，作者不对使用本工具造成的任何损失负责。在生产环境中使用前，请务必进行充分的测试和验证。

---

*最后更新: 2025年10月25日*  
*版本: 2.0.0*  
*作者: GitHub Copilot*

## 文件说明

- `monitor_launcher.py` - 🚀 **统一启动器**，交互式菜单访问所有功能
- `mainnet_monitor.py` - 完整的 USDT 监控系统，支持定时任务和数据库存储
- `usdt_quick_check.py` - 多功能监控工具，支持大额转账查询和余额激增监控
- `balance_surge_monitor.py` - 专门的余额激增监控工具 + 地址交互分析
- `analyze_concrete_stable.py` - 🆕 **Concrete_STABLE专项分析工具**
- `balance_surge_demo.py` - 余额激增监控演示和策略指南
- `demo.py` - 功能演示脚本
- `monitor.py` - 基础监控框架
- `base.py` - 基础工具函数（数据库连接、通知等）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Etherscan API 密钥

访问 [https://etherscan.io/apis](https://etherscan.io/apis) 注册并获取免费的 API 密钥。

### 3. 配置环境变量

复制并修改环境变量模板：

```bash
cp .env.template .env
```

编辑 `.env` 文件，填入您的 API 密钥：

```env
ETHERSCAN_API_KEY=你的_etherscan_api_密钥
```

### 4. 使用监控工具

**最简单的方式 - 使用启动器：**

```bash
python monitor_launcher.py
```

这会打开一个交互式菜单，包含所有监控功能。

**直接使用具体工具：**

**大额转账查询：**

```bash
python usdt_quick_check.py
```

然后选择功能 1，或者直接通过命令行：

```bash
python usdt_quick_check.py 1000000 24
```

**余额激增监控：**

```bash
python usdt_quick_check.py
```

然后选择功能 2，或者使用专门的余额监控工具：

```bash
python balance_surge_monitor.py 5000000 100000
```

**地址交互分析：**

```bash
# 分析任意地址的交互
python balance_surge_monitor.py
# 然后选择功能 2

# 专门分析 Concrete_STABLE 地址
python analyze_concrete_stable.py 30
```

**快速分析 Concrete_STABLE：**

```bash
python analyze_concrete_stable.py 7  # 分析最近7天
```

参数说明：
- 大额转账查询：`最小金额阈值(USDT) 查询小时数`
- 余额激增监控：`最小增长金额(USDT) 48小时前最大余额(USDT)`
- 地址交互分析：`天数` (分析最近多少天的数据)

## 详细功能

### 1. USDT 大额转账监控

监控功能可以：
- 自定义金额阈值（默认 100万 USDT）
- 指定监控时间范围
- 统计发送方和接收方地址
- 计算转账总金额和笔数
- 生成详细的分析报告

### 2. 余额激增监控 🆕

这是一个特殊的监控功能，用于发现可能的：
- 大额资金流入
- 新的大户地址
- 异常资金聚集

**监控条件：**
- 最近24小时USDT余额新增 ≥ 5,000,000 USDT（可自定义）
- 48小时前余额 < 100,000 USDT（可自定义）

**用途：**
- 发现新的大户地址
- 监控资金异常流动
- 识别可能的市场操作

### 3. 地址交互分析 🆕

全新的地址交互分析功能，可以：
- 分析指定地址的所有 USDT 转账记录
- 识别主要的资金来源和去向
- 统计交互频率和金额
- 生成详细的交互报告

**特色功能：**
- 🎯 专门的 Concrete_STABLE 地址分析
- 📊 交互模式分析（双向、单向交互）
- 💰 大额交互地址识别
- ⏰ 时间模式分析
- 📝 自动生成地址列表文件

**用途：**
- 追踪特定地址的资金流向
- 分析交易所或大户的交互模式
- 识别可能的关联地址
- 研究资金聚集和分散模式

### 使用示例

**查询最近1小时超过500万USDT的转账：**

```bash
python usdt_quick_check.py 5000000 1
```

**监控余额激增地址（24小时新增≥1000万，48小时前<50万）：**

```bash
python balance_surge_monitor.py 10000000 500000
```

**分析 Concrete_STABLE 地址的交互：**

```bash
python analyze_concrete_stable.py 30  # 分析最近30天
```

```
### 输出示例

**大额转账监控输出：**

```
🔍 USDT 大额转账分析报告
================================================================================
📊 分析时间段: 最近 1 小时
🧱 区块范围: 18500000 - 18500240
📈 总转账数: 1,234
💰 大额转账数: 5
💵 大额转账总金额: 25,500,000.00 USDT
📤 唯一发送地址: 4
📥 唯一接收地址: 5
🎯 最小金额阈值: 5,000,000 USDT

💎 前10笔最大转账:
================================================================================

1. 10,000,000.00 USDT
   📤 发送方: 0x1234...5678
   📥 接收方: 0xabcd...efgh
   🕐 时间: 2024-10-24 14:30:25
   🔗 交易哈希: 0x9876...4321
   ⛽ Gas 费用: 0.002500 ETH
```

**余额激增监控输出：**

```
🎉 发现 3 个符合条件的地址!
================================================================================
📊 总计余额增长: 18,500,000.00 USDT
📊 平均增长倍数: 25,600.3%

🏆 #1 地址: 0x1234567890abcdef1234567890abcdef12345678
   📊 48小时前余额: 50,000.00 USDT
   📊 当前余额: 8,050,000.00 USDT
   📈 余额增长: 8,000,000.00 USDT
   📥 24小时接收: 8,100,000.00 USDT
   📊 增长倍数: 16,000.0%
   🔗 查看详情: https://etherscan.io/address/0x1234567890abcdef1234567890abcdef12345678
```
```

## 高级配置

### 数据库集成

如需将监控数据保存到数据库，请在 `.env` 文件中配置数据库连接：

```env
db_url=postgresql://user:password@localhost:5432/database
```

### 通知设置

支持通过 IFTTT Webhook 发送通知：

```env
IFTTT_KEY=你的_ifttt_webhook_密钥
```

### 自定义监控参数

在 `mainnet_monitor.py` 中可以调整：
- 监控金额阈值
- 监控频率
- 区块范围估算
- 通知条件

## API 限制

Etherscan 免费 API 有以下限制：
- 每秒最多 5 次请求
- 每天最多 100,000 次请求

建议在生产环境中：
- 使用付费 API 密钥
- 添加请求频率控制
- 实现错误重试机制

## 注意事项

1. **API 密钥安全**: 请勿将 API 密钥提交到公共代码仓库
2. **网络稳定性**: 确保网络连接稳定，避免请求超时
3. **数据准确性**: 监控结果基于 Etherscan 数据，可能存在轻微延迟
4. **法律合规**: 使用本工具请遵守相关法律法规

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

MIT License