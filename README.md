# chain_monitor

一个以 Python 脚本为主的链上分析与监控仓库，覆盖以下几类能力：

- 多链代币地址与协议地址管理
- UTC 时间到区块号的映射
- 大额代币转账、协议交互、历史余额分析
- 地址标签缓存与外部 API 回填
- 合约交互、取款脚本、专项排查脚本

当前仓库更像“脚本工具箱”，而不是标准的 Python package。本文档重点解决 4 件事：

- 说明项目结构和脚本职责
- 提供 `conda` 下 `py31evm` 环境的统一安装方式
- 说明运行前需要的环境变量
- 列出当前最需要修复的结构性问题

## 1. 仓库结构

```text
chain_monitor/
├── src/
│   ├── core/                 # 公共配置、链配置、地址标签、时间换块、ABI、音频等基础模块
│   ├── analysis/             # 分析与监控实现
│   ├── execution/            # 真实链上交互、执行与排障实现
│   └── *.py                  # 兼容历史调用路径的 wrapper 入口
├── tests/                    # 测试脚本
├── examples/                 # 示例和演示脚本
├── debug/                    # 手工调试和排障脚本
├── abi/                      # ABI JSON 与专题说明文档
├── hardhat/                  # 本地 Hardhat 模拟链与 fork 启动脚本
├── logs/                     # 运行日志产物
├── monitor_output/           # 监控报告输出
├── resource/                 # 资源文件，如告警音频
├── results/                  # 查询结果输出
├── temp/                     # 临时分析产物
├── address_labels.db         # 本地地址标签缓存 SQLite
├── .env.example              # 环境变量示例
└── requirements.txt          # pip 依赖
```

## 2. 脚本清单

### 2.1 基础配置与公共模块

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/core/address_constant.py` | 维护多链代币地址、精度、已知协议和合约映射 | 多数分析脚本都会依赖 |
| `src/core/block_time_converter.py` | 通过 Etherscan v2 API 将 UTC 时间转换为区块号 | 多链分析的时间入口 |
| `src/core/chain_config.py` | 统一维护网络、API 和 RPC 配置 | 目录治理后新增 |
| `src/core/logging_utils.py` | 统一维护日志初始化逻辑 | 目录治理后新增 |
| `src/core/moralis_api_client.py` | Moralis 地址信息与 DeFi 协议识别封装 | 给地址标签系统补充外部信息 |
| `src/core/sqlite_address_querier.py` | 地址标签查询与缓存层，查询顺序为本地常量 -> SQLite -> Moralis/Etherscan | 地址标签核心模块 |
| `src/core/abi_fetcher.py` | ABI 拉取、代理识别、结果落盘 | `abi/` 目录的生产工具 |
| `src/core/audio_player.py` | 跨平台系统音频播放封装 | 供告警/提醒使用 |
| `src/execution/play_alert.py` | 播放告警音频的极简入口 | 依赖 `resource/alert.mp3` |

### 2.2 分析核心

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/analysis/token_deposit_analyzer.py` | 仓库主分析内核；负责多链配置、区块范围、转账抓取、大额筛选、地址/协议识别 | 当前最核心的底座文件 |
| `src/analysis/historical_token_balance_checker.py` | 查询指定历史时刻的代币余额，支持单地址和批量模式 | 复用时间换块和多链配置 |
| `src/analysis/contract_interaction_analyzer.py` | 继承 `TokenDepositAnalyzer`，聚焦某个目标合约的交互地址和统计 | 面向“某合约被谁交互过” |
| `src/analysis/configurable_protocol_monitor.py` | 定时分析最近时间窗口内的协议交互活跃度并输出报告 | 面向持续监控 |

### 2.3 专项分析与辅助脚本

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/analysis/balance_surge_monitor.py` | 监控 USDT 余额激增地址 | 早期专项脚本，偏以太坊主网 |
| `src/analysis/usdt_quick_check.py` | 快速检查大额 USDT 转账和余额变化 | 偏一次性排查 |
| `src/analysis/usdt_balance_query.py` | 查询指定地址的 USDT 余额 | 轻量手工工具 |
| `src/analysis/analyze_address_interactions.py` | 分析地址列表的交互对象和共同地址 | 更偏离线分析 |
| `src/analysis/address_intersection_analyzer.py` | 做地址集合交集分析 | 适合比对多个输出结果 |
| `src/analysis/batch_address_analyzer.py` | 批量地址交互分析入口 | 组织批量任务用 |
| `src/analysis/analyze_concrete_stable.py` | 针对 Concrete STABLE 的分析脚本 | 项目专项场景 |

### 2.4 链上执行与合约交互脚本

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/execution/lista_withdraw.py` | Lista 取款逻辑与循环执行 | 带真实链上交互 |
| `src/execution/concrete_stable_interaction_v2.py` | Concrete STABLE 交互，支持真实签名、mock、preprod | 文件较大，功能较重 |
| `src/execution/check_lista_contract.py` | Lista 合约状态检查 | 调试辅助 |
| `src/execution/check_withdraw_queue.py` | 检查取款队列 | 调试辅助 |
| `src/execution/diagnose_gas_estimation.py` | Gas 估算问题诊断 | 面向排障 |

### 2.5 数据与运行产物

| 路径 | 作用 |
| --- | --- |
| `abi/` | ABI JSON 和相关说明文档 |
| `address_labels.db` | SQLite 地址标签缓存 |
| `logs/` | 日志输出 |
| `monitor_output/` | 监控结果 |
| `results/` | 查询结果 |
| `temp/` | 临时分析文件 |
| `resource/alert.mp3` | 告警音频 |

### 2.6 测试、演示与手工调试

目录现已拆分为三类，并通过 `_path_setup.py` 自动补齐 `src/` 到 `sys.path`：

- `tests/`：测试脚本，如 `tests/test_historical_token_balance_checker.py`
- `examples/`：演示脚本，如 `examples/balance_surge_demo.py`、`examples/example_usage.py`
- `debug/`：手工排查脚本，如 `debug/simple_debug.py`

### 2.7 当前推荐的 import / 运行方式

- 新代码内部推荐直接使用分层路径，例如 `from core.chain_config import get_rpc_url`
- 对外 CLI 入口优先保留 `python src/token_deposit_analyzer.py`、`python src/historical_token_balance_checker.py` 这类兼容路径
- 如果是维护实现本体，优先编辑 `src/core/`、`src/analysis/`、`src/execution/` 下的文件，而不是 `src/` 根目录 wrapper

## 3. 环境准备

### 3.1 使用 conda 创建统一环境

按你的要求，环境名统一使用 `py31evm`。本仓库本轮验证通过的环境版本是 Python 3.10。

```bash
conda create -n py31evm python=3.10 -y
conda activate py31evm
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果你需要打开仓库里的 `test.ipynb`，再补一组可选依赖：

```bash
python -m pip install notebook ipykernel
python -m ipykernel install --user --name py31evm --display-name "py31evm"
```

### 3.2 环境变量

先复制示例配置：

```bash
cp .env.example .env
```

常用环境变量如下：

| 变量名 | 用途 | 是否必需 |
| --- | --- | --- |
| `ETHERSCAN_API_KEY` | 通用 Etherscan v2 API Key | 必需 |
| `ARBISCAN_API_KEY` | Arbitrum 专用 API Key | 可选 |
| `BASESCAN_API_KEY` | Base 专用 API Key | 可选 |
| `BSCSCAN_API_KEY` | BSC 专用 API Key | 可选 |
| `WEB3_RPC_URL` | Ethereum RPC | 常用 |
| `ARBITRUM_RPC_URL` | Arbitrum RPC | 多链场景常用 |
| `BASE_RPC_URL` | Base RPC | 多链场景常用 |
| `BSC_RPC_URL` | BSC RPC | 多链场景常用 |
| `MORALIS_API_KEY` | Moralis 地址标签查询 | 可选 |
| `WALLET_PRIVATE_KEY` | 真实签名模式下的私钥 | 仅链上执行脚本需要 |
| `MOCK_WEB3_RPC_URL` | mock / preprod 交互 RPC | 仅交互脚本需要 |
| `MOCK_WALLET_ADDRESS` | mock 模式钱包地址 | 可选 |

注意：

- 不要把真实 `.env` 提交进仓库。
- 取款和合约交互类脚本会依赖私钥，分析类脚本一般不需要。
- 若未配置网络专用 API Key，代码通常会回退到 `ETHERSCAN_API_KEY`。

## 4. 安装依赖说明

当前代码实际用到的关键第三方依赖主要是：

- `requests`
- `python-dotenv`
- `web3`
- `eth-account`
- `schedule`

仓库里还保留了以下依赖声明，但当前主流程代码并未明显使用：

- `pandas`
- `sqlalchemy`
- `apscheduler`

这几个我暂时没有删，原因是：

- 你希望统一管理所有依赖
- 仓库里存在历史脚本、Notebook、演进中的功能，直接删除有误伤风险

后续可以再做一次“依赖瘦身”清理。

## 5. 常用运行方式

### 5.1 做一次时间范围内的大额转账分析

```bash
conda activate py31evm
python src/token_deposit_analyzer.py \
  --network ethereum \
  --token USDT \
  --start-time "2025-10-25 00:00:00" \
  --end-time "2025-10-25 01:00:00" \
  --min-amount 1000
```

### 5.2 查询某个地址的历史余额

```bash
conda activate py31evm
python src/historical_token_balance_checker.py \
  --network ethereum \
  --token USDT \
  --target-time "2025-10-25 12:00:00" \
  --address 0x1234567890abcdef1234567890abcdef12345678
```

### 5.3 跑协议监控

```bash
conda activate py31evm
python src/configurable_protocol_monitor.py \
  --network ethereum \
  --token USDT \
  --min-amount 1000 \
  --time-window-minutes 10 \
  --monitor-interval-minutes 10
```

### 5.4 运行一个测试/演示脚本

```bash
conda activate py31evm
python tests/test_historical_token_balance_checker.py
python examples/example_usage.py
```

## 6. 当前需要优先修复的结构性问题

### P0 - 依赖与环境不一致

- `requirements.txt` 原先没有覆盖 `web3`、`eth-account`、`schedule` 等实际依赖。
- 文档缺失导致新机器无法稳定复现运行环境。

### P0 - 兼容入口与实现目录并存

- 当前已经拆成 `src/core/`、`src/analysis/`、`src/execution/`，但为了兼容旧调用方式，`src/` 根目录还保留了一批 wrapper。
- 这有助于平滑迁移，但也意味着短期内会同时存在“两套路径”，需要在后续统一。

### P0 - 核心逻辑仍需继续收敛

- 网络配置、RPC 读取、API Key 读取、日志初始化已经开始收敛，但还没有覆盖到所有执行脚本和历史脚本。
- 后续应该继续把剩余重复逻辑向 `src/core/` 收口，否则局部改动仍可能不一致。

### P1 - 核心文件体积过大

- `token_deposit_analyzer.py` 约 1500 行。
- `concrete_stable_interaction_v2.py` 约 1200 行。
- `sqlite_address_querier.py` 约 850 行。

这些文件同时混合了：

- 配置
- 业务逻辑
- CLI
- 输出格式化
- 文件落盘

后续维护成本会越来越高。

### P1 - 测试目录已拆分，但自动化边界仍不清晰

- 目录已经拆成 `tests/`、`examples/`、`debug/`，但脚本风格和自动化程度仍不一致。
- 自动化测试、演示脚本、依赖真实链上环境的 smoke test 还没有形成清晰分层，难以直接挂 CI。

### P1 - 文档分散

- 主 README 原来为空。
- 说明仍散落在 `abi/`、`tests/`、`debug/` 和专题 Markdown 中，信息入口还可以继续收敛。

### P1 - wrapper 与实现命名需要统一策略

- 现在同时存在 `src/token_deposit_analyzer.py` 和 `src/analysis/token_deposit_analyzer.py` 这类“兼容入口 + 实现文件”双路径。
- 后续需要明确哪些文件长期保留为公共入口，哪些只作为内部实现，避免文档和调用方式再次分叉。

### P2 - 运行产物与工程代码仍然混放

- 虽然源码层已经分层，但 `logs/`、`monitor_output/`、`results/`、`temp/`、`address_labels.db` 仍在仓库根目录。
- 如果后续继续积累，仓库会同时承担“源码目录”和“工作目录”两个角色，长期可维护性一般。

## 7. 建议的下一步整理顺序

建议按这个顺序治理：

1. 继续把剩余公共逻辑收敛到 `src/core/`
2. 明确并冻结需要长期保留的 `src/` 根目录兼容入口
3. 拆分 `token_deposit_analyzer.py`、`concrete_stable_interaction_v2.py` 这类超大文件
4. 细化 `tests/`、`examples/`、`debug/` 的自动化边界
5. 把运行产物目录从源码结构里隔离
6. 最后再考虑 package 化和统一 CLI
