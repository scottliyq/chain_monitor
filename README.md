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

### 2.5 Robinhood Chain NVDA3L mint 监控

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `src/analysis/nvda3l_mint_monitor.py` | 读取 NVDA3L 代理 token 状态，模拟 `requestMint(uint256,address)`，记录 `cap_raw` / `cap_increased`，并在可 mint 或 cap 增加时告警 | 使用 Robinhood Chain RPC，不广播交易 |
| `src/nvda3l_mint_monitor.py` | 兼容历史调用方式的根目录入口 | 实现位于 `src/analysis/` |
| `tests/test_nvda3l_mint_monitor.py` | 覆盖数量精度、状态变化去重和告警接口 | 不依赖真实链上请求 |

### 2.6 数据与运行产物

| 路径 | 作用 |
| --- | --- |
| `abi/` | ABI JSON 和相关说明文档 |
| `address_labels.db` | SQLite 地址标签缓存 |
| `logs/` | 日志输出 |
| `monitor_output/` | 监控结果 |
| `results/` | 查询结果 |
| `temp/` | 临时分析文件 |
| `resource/alert.mp3` | 告警音频 |

### 2.7 测试、演示与手工调试

目录现已拆分为三类，并通过 `_path_setup.py` 自动补齐 `src/` 到 `sys.path`：

- `tests/`：测试脚本，如 `tests/test_historical_token_balance_checker.py`
- `examples/`：演示脚本，如 `examples/balance_surge_demo.py`、`examples/example_usage.py`
- `debug/`：手工排查脚本，如 `debug/simple_debug.py`

### 2.8 当前推荐的 import / 运行方式

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
| `ROBINHOOD_RPC_URL` | Robinhood Chain RPC，默认回退官方公共 RPC | NVDA3L 监控可选 |
| `RH_RPC_URL` | Robinhood Chain RPC，v4 历史收费分析器优先读取 | v4 分析必需 |
| `NVDA3L_MONITOR_INTERVAL_SECONDS` | NVDA3L 监控间隔，默认 60 秒 | 可选 |
| `NVDA3L_MINT_PROBE_AMOUNT` | 每次模拟的 token 数量，默认 1 | 可选 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram 告警凭据 | 成对配置可选 |
| `PUSHOVER_APP_TOKEN` / `PUSHOVER_USER_KEY` | Pushover 告警凭据 | 成对配置可选 |

注意：

- 不要把真实 `.env` 提交进仓库。
- 取款和合约交互类脚本会依赖私钥，分析类脚本一般不需要。
- 若未配置网络专用 API Key，代码通常会回退到 `ETHERSCAN_API_KEY`。

## 4. 安装依赖说明

`requirements.txt` 已整理为可直接使用的 pip 依赖文件。当前代码实际用到的关键第三方依赖主要是：

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

Robinhood RWA 的 Supabase 写入使用 PostgREST HTTP API 和 `requests`，因此不需要额外安装 `supabase-py`。Worker 优先读取 `SUPABASE_SERVICE_ROLE_KEY`，也兼容新版 Supabase 的 `SUPABASE_SECRET_KEY`；不会使用前端 `SUPABASE_PUBLISHABLE_KEY`。`SUPABASE_URL` 可以填写项目根 URL，也可以填写带 `/rest/v1` 的 URL，程序会自动规范化。安装全部依赖：

```bash
python -m pip install -r requirements.txt
```

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

### 5.5 分析某个地址最近 3 天收到的 ETH 金额分布

```bash
conda activate py31evm
python src/eth_receive_distribution_analyzer.py \
  --address 0x0fca5194baa59a362a835031d9c4a25970effe68 \
  --days 3
```

如果你想排除 internal 交易，只看普通转入：

```bash
conda activate py31evm
python src/eth_receive_distribution_analyzer.py \
  --address 0x0fca5194baa59a362a835031d9c4a25970effe68 \
  --days 3 \
  --no-internal
```

结果会输出到 `results/` 目录，包含 JSON 明细和文本报告。

### 5.4 监控 NVDA3L 是否可以 mint

```bash
conda activate py31evm
python src/nvda3l_mint_monitor.py --once
```

默认行为是立即检查一次，然后每 60 秒重复检查；`--once` 适合手工确认。监控只执行 `eth_call` 模拟，不会签名或广播交易。最新结果保存到 `monitor_output/nvda3l_mint_status.json`。

目标 token 为 `0xF51fb54DE60f6e16252E852A5Ed0E60B8307606A`，其实现合约为 `0xcfB0f21f200045b3c2eF8a20fB36498e32395C88`，监控模拟的是实际暴露的 `requestMint(uint256,address)`，而不是猜测标准 ERC-20 `mint`。合约没有公开标准 `cap()` getter，因此 `cap_raw` 从 cap 超限自定义错误的第二个 `uint256` 中解析；如果正常 mint 探测成功，监控会额外执行一次大额只读 cap 探针，避免漏掉 cap 增长。监控会从旧状态文件恢复上一次 cap，比较后写入 `cap_increased`。配置 Telegram 或 Pushover 的成对环境变量后，状态从不可 mint 变为可 mint，或 cap 增加时会发送告警。

### 5.6 历史分析 Robinhood Chain Uniswap v4 实际收费

新增的 `src/uniswap_v4_fee_analyzer.py` 只读 `RH_RPC_URL`（也兼容
`ROBINHOOD_RPC_URL`），扫描 PoolManager 的 `Initialize` / `Swap` 事件，并读取
交易 receipt 中 `Swap.sender` 的 ERC-20 Transfer。报告同时输出：

- `core_fee_rate_percent`：v4 `Swap.fee` 实际采用的 core swap fee；协议费开启时，这是 core 总费率，不能仅凭事件拆出 LP 与 protocol 分成。
- `actual_input_raw` / `actual_output_raw`：Swap.sender 实际转出/收到的数量。
- `input_residual_raw` / `output_shortfall_raw`：相对 PoolManager Swap delta 的可观察额外扣费候选，单池单跳且两侧都能匹配时才是高置信度。
- `hook_transfer_observed`：是否看到资金直接流向 hook，或使用 `--trace-hooks` 时 trace 经过 hook；这不是完整 Hook fee 的自动拆分。

先用 DEX 聚合器或历史日志得到候选 `poolId`，再做交易级回放：

```bash
conda activate py31evm
python src/uniswap_v4_fee_analyzer.py \
  --start-block 52730780 \
  --end-block 52740779 \
  --pool-id 0xd1809377deaae78d6f1740ae8ec091ab4eb7f1bffa89ceae630855fe5a631982 \
  --output results/uniswap_v4_fee_report.json \
  --csv-output results/uniswap_v4_fee_rankings.csv
```

扫描很长历史时可先跳过 receipt，只按 Swap/Initialize 事件筛选候选池，再对候选
池去掉 `--skip-receipts` 做实际流量核验：

```bash
python src/uniswap_v4_fee_analyzer.py \
  --start-block 50207947 \
  --end-block 52771942 \
  --skip-receipts \
  --output results/uniswap_v4_fee_candidates.json
```

如果只需要第一阶段的 Swap 费率排名，可再加 `--skip-initialize`，减少历史注册表
查询；但此时报告不会有 currency0/currency1/hooks，不能判断 Stock/LT 报价或 Hook。

如果池子的 `Initialize` 早于交易窗口，必须把注册表扫描起点设得更早：

```bash
python src/uniswap_v4_fee_analyzer.py \
  --start-block 52730780 \
  --end-block 52740779 \
  --registry-start-block 50000000 \
  --pool-id 0xd1809377deaae78d6f1740ae8ec091ab4eb7f1bffa89ceae630855fe5a631982
```

排名优先看 `max_core_fee_rate_percent`、高置信度样本的
`average_observed_residual_rate_percent` 和交易数量。公共 RPC 的
`eth_getLogs` 窗口限制可能因返回体大小动态缩小，程序会按 RPC 错误建议重试；
`--trace-hooks` 需要支持 `debug_traceTransaction` 的 archive/debug RPC，且会显著变慢。

注意：`Swap.fee` 不是“LP 最终赚到的金额”；精确 LP 结算仍需按 position 的
feeGrowth 和持仓区间计算。Hook 也可能通过自定义 accounting 把费用转入任意
treasury，所以没有 Hook ABI / 明确 treasury 地址时，只能报告“可观察额外扣费”，
不能把所有 residual 当作 Hook fee。

### 5.7 维护官方 RWA 清单并按收益率分析 Uniswap v4 池

`src/robinhood_rwa_uniswap_monitor.py` 会从 Robinhood 官方 `/rhj/assets` 同步
Chain ID 4663 的 active Stock Token / ETF 清单，保存到
`monitor_output/robinhood_rwa_assets.json`，并增量维护 Uniswap v4
`Initialize` 池注册表。随后扫描含官方 RWA 币种的池，按 2 小时、4 小时和 24 小时
统计 Swap fee，读取 StateView 的 active liquidity，并输出手续费、池规模 proxy、
 窗口收益率和线性年化收益率，CSV 在每个窗口内按年化收益率降序排列。
为避免对数万空池逐一读取 StateView，排名默认只输出最近 24 小时内发生过 Swap
的 active 池；当前候选池数量记录在 JSON 的 `rwa_pool_count`，近期有交易的数量记录在
`active_rwa_pool_count`。如需把 RWA 与任意 token 的池全部纳入，增加
`--all-rwa-pairs`。

```bash
conda activate py31evm
python src/robinhood_rwa_uniswap_monitor.py \
  --output monitor_output/robinhood_rwa_uniswap_rankings.json \
  --csv-output monitor_output/robinhood_rwa_uniswap_rankings.csv
```

默认读取 `RH_RPC_URL` 或 `ROBINHOOD_RPC_URL`；未配置时使用
`src/core/chain_config.py` 中的 Robinhood Chain 公共 RPC。第一次运行从区块 0
扫描池初始化事件，后续运行从 `robinhood_uniswap_pools.json` 的
`last_scanned_block + 1` 增量更新。可使用 `--interval-minutes 10` 持续更新，或交给
cron/systemd 定时执行。

每轮都会重新获取官方 `/rhj/assets` 的全量 active 股票列表并保存到资产快照；
池初始化事件也始终按全量 active 股票筛选，不再限制前 20 个资产。

启用 `--interval-minutes` 的常驻 worker 遇到临时 HTTP/RPC、Web3、Supabase 或报告写入
异常时，会记录 traceback，等待下一次间隔后自动重试，不会因为单轮失败退出；不带该参数的
一次性执行仍会以失败状态返回，便于脚本或 cron 判断本次任务失败。

Robinhood Chain 官方文档列出的主网 RPC 包括官方公共 RPC，以及需要账号/密钥的
Alchemy、QuickNode、Blockdaemon、dRPC、Validation Cloud、Chainstack 和 GlobalStake。大批量历史扫描建议把
已申请的节点放在 `ROBINHOOD_RPC_URLS` 中，用逗号分隔；程序会按请求轮询，并在
429、超时、临时服务错误或 `BlockNotFound` 时切换节点。为避免不同节点链头
不同导致区块读取失败，每一轮 `run_once()` 会固定使用一个 RPC；只有当前节点
发生可重试故障时才切换到下一个节点。API key/token 不会写入日志或报告。
也可以分别设置 `ALCHEMY_RPC_URL`、`TATUM_RPC_URL`、`QUICKNODE_RPC_URL`、
`BLOCKDAEMON_RPC_URL`、`DRPC_RPC_URL`、`VALIDATION_CLOUD_RPC_URL`、
`CHAINSTACK_RPC_URL`、`GLOBALSTAKE_RPC_URL`、`ROBINHOOD_RPC_URL`；未传
`--rpc-url` 时程序会收集所有已配置的这些变量并去重轮询。QuickNode、Blockdaemon、
dRPC、Validation Cloud、Chainstack 和 GlobalStake 的 endpoint 需要先在对应供应商
控制台手动注册 Robinhood Chain 主网后取得，真实地址和 API Key 只放在 `.env`，不要写入
YAML 或提交到仓库。官方文档确认 QuickNode 的地址格式为
`https://{ENDPOINT}.robinhood-mainnet.quiknode.pro/{TOKEN}`，其他供应商的地址以其
控制台生成结果为准。

`.env` 配置示例（仅示意，需替换为你注册后获得的真实地址）：

```dotenv
ROBINHOOD_RPC_URLS=https://rpc.mainnet.chain.robinhood.com
ALCHEMY_RPC_URL=https://robinhood-mainnet.g.alchemy.com/v2/<API_KEY>
TATUM_RPC_URL=https://robinhood-mainnet.gateway.tatum.io
QUICKNODE_RPC_URL=https://<ENDPOINT>.robinhood-mainnet.quiknode.pro/<TOKEN>
BLOCKDAEMON_RPC_URL=
DRPC_RPC_URL=
VALIDATION_CLOUD_RPC_URL=
CHAINSTACK_RPC_URL=
GLOBALSTAKE_RPC_URL=
```

空变量会自动跳过。填写完成后可用 `--rpc-check-only` 检查每个 endpoint 的 Chain ID
和最新区块；只有返回 Chain ID `4663` 的节点才应保留在轮询列表中。

官方 RWA 价格接口遇到超时、连接错误、408、429 或 5xx 临时错误时，会按 1 秒、
2 秒退避，最多尝试 3 次；非临时 HTTP 错误不会重复请求。三次都失败时，该资产
的 USD 指标保持 `NULL`，并在日志中标记原因。

```bash
ROBINHOOD_RPC_URLS=https://rpc.mainnet.chain.robinhood.com,https://robinhood-mainnet.g.alchemy.com/v2/<API_KEY>,https://<ENDPOINT>.robinhood-mainnet.quiknode.pro/<TOKEN> \
python src/robinhood_rwa_uniswap_monitor.py --rpc-check-only
```

节点探测结果保存到 `monitor_output/robinhood_rpc_health.json`；也可只传入逗号分隔
的 `--rpc-url`。报告会记录脱敏后的 `rpc_endpoints` 和
`rpc_strategy=round_robin_with_failover_on_rate_limit_or_temporary_error`。

报告口径：`fee_income_usd` 是按 Swap 输入量和 Swap.fee 估算的 core fee；
`active_liquidity_usd_proxy` 是当前 active liquidity 结合 sqrtPrice 计算的虚拟双边
储备 USD proxy，不是精确 LP TVL；`window_yield_percent` 为窗口手续费除以该 proxy，
`annualized_yield_percent` 为线性年化值。缺少 token USD 价格或非 RWA 报价币种时，
相关 USD 收益率会标记为 `partial`，不会伪造为 0。
收益排名的 `pool_address` 列与 `pool_id` 相同，表示 Uniswap v4 的 bytes32 池标识；
v4 池没有独立池合约地址，实际交互合约是 PoolManager。

资产首次出现在本地快照时记录 `first_seen_at`；首次发现后的 24 小时内，资产会标记
`is_new_issue=true`。这表示 Worker 首次观察到该资产的时间，不等同于官方证券发行时间。
报告中的 `assets` 保存全量 active 股票及其标记，`new_issue_symbols` 提供本轮新发行股票。

### 5.8 Supabase 小时级存储与前端直查

Supabase migration 位于 `supabase/migrations/20260904000000_create_rh_rwa_monitor.sql`，
所有 Robinhood 相关数据库对象使用 `rh_` 前缀：

- `rh_rwa_assets`：官方 RWA 全量资产清单，包含 `first_seen_at` 和 `is_new_issue`。
- `rh_uniswap_v4_pools`：Uniswap v4 池元数据。
- `rh_uniswap_v4_swap_events`：最近 7 天去重后的 Swap 事件。
- `rh_pool_hourly_metrics`：按池和 UTC 小时保存手续费、Swap 数量和池规模 proxy。
- `rh_pool_window_rankings`：预计算的 2h、4h、24h 当前窗口收益排名。
- `rh_sync_checkpoints`：Initialize/Swap 增量扫描进度。
- `rh_pool_dashboard`：面向前端展示的兼容视图，提供 `tvl_usd`、`volume_24h_usd`、`fee_apr`、`apr_2h`、`rank_2h`、`metric_time`、`sync_time`、`is_new_issue` 和 `new_issue_discovered_at`。

启用 Supabase 发布前，在 `.env` 中设置 `SUPABASE_URL` 和
`SUPABASE_SERVICE_ROLE_KEY`（或新版项目的 `SUPABASE_SECRET_KEY`），然后在 Supabase SQL Editor 执行 migration。Worker
只增量扫描 checkpoint 之后的区块，默认保留少量重叠区块用于容错；数据库按唯一交易
哈希和日志索引去重，前端不再需要 RPC。

启用 `--supabase-publish` 后，每轮会将官方 active 资产、候选池元数据和扫描到的
Swap 事件写入对应的 `rh_` 表，并调用 `rh_ingest_hourly_batch` 刷新 2h、4h、24h
小时指标和窗口排名。日志中的 `Supabase 写入完成` 会显示本轮实际提交的资产、池和
Swap 数量；本地 JSON/CSV 只是备份和比对输出，不是数据库写入的替代品。

```bash
conda activate py31evm
python src/robinhood_rwa_uniswap_monitor.py \
  --supabase-publish \
  --interval-minutes 10 \
  --output monitor_output/robinhood_rwa_uniswap_rankings.json \
  --csv-output monitor_output/robinhood_rwa_uniswap_rankings.csv
```

前端直接读取 `rh_pool_window_rankings`，将 `window_hours` 设置为 `2`、`4` 或 `24`：

```typescript
const { data, error } = await supabase
  .from("rh_pool_window_rankings")
  .select("window_hours,pool_pair,pool_address,swap_count,fee_income_usd,pool_size_usd_proxy,window_yield_percent,annualized_yield_percent,data_quality,computed_at")
  .eq("chain_id", 4663)
  .eq("asset_scope", "all_active")
  .eq("window_hours", 24)
  .order("annualized_yield_percent", { ascending: false })
  .limit(10);
```

`pool_address` 是 Uniswap v4 的 bytes32 `pool_id`；实际交互合约地址保存在
`pool_manager_address`。Service role key 只允许 Worker 使用，前端使用 anon key，
数据库 RLS 仅向前端开放 `rh_pool_window_rankings` 的只读访问。

如果前端页面需要全量池元数据、2h/24h 排名和新发行标记，可直接读取后续 migration 创建的
`rh_pool_dashboard`，再由前端按 `is_new_issue`、股票名称、排序和分页过滤：

```typescript
const { data, error } = await supabase
  .from("rh_pool_dashboard")
  .select("token,pool_address,pool,tvl_usd,volume_24h_usd,fee_apr,current_apr,apr_2h,rank_2h,rank_24h,is_new_issue,new_issue_discovered_at,metric_time,sync_time")
  .eq("chain_id", 4663)
  .eq("asset_scope", "all_active")
  .order("rank_24h", { ascending: true });
```

`rh_pool_dashboard` 的首次 migration 为
`supabase/migrations/20260904000001_create_rh_pool_dashboard_view.sql`；如果该文件已经执行，需继续执行
`supabase/migrations/20260904000002_fix_rh_pool_dashboard_division.sql` 修复零费率 Swap 的除零问题，
已有数据库还需执行 `supabase/migrations/20260904000003_add_new_issue_tracking.sql` 增加新发行字段，
以及 `supabase/migrations/20260904000004_dashboard_all_pools.sql` 让 dashboard 包含全部已发现池。其中
`fee_apr` 是 24h 线性年化收益率，`apr_2h` 是 2h 线性年化收益率，
`volume_24h_usd` 根据最近 24h Swap 的手续费和实际 fee pips 反推输入量 USD；缺少价格或费率时返回 `null`，不伪造为 0。

#### 5.8.1 数据库字段说明

完整字段、键约束、函数、索引和 RLS 说明见独立文档：[RH_DATABASE_FIELD_REFERENCE.md](RH_DATABASE_FIELD_REFERENCE.md)。

该文档与 `supabase/migrations/20260904000000_create_rh_rwa_monitor.sql` 对照维护；`pool_address` 仍表示 Uniswap v4 的 bytes32 `pool_id`。

## 6. 本次更新记录

### 2026-04-25

- 新增 `src/analysis/eth_receive_distribution_analyzer.py`，用于分析目标地址在给定时间窗口内收到的原生 ETH 金额分布。
- 新增 `src/eth_receive_distribution_analyzer.py` 兼容入口，保持仓库现有 `src/` 根目录脚本调用习惯。
- 新增 `tests/test_eth_receive_distribution_analyzer.py`，覆盖金额分桶和汇总统计逻辑。

修改原因：

- 需要基于仓库现有的 Etherscan v2 API、`chain_config` 和 `BlockTimeConverter`，快速复用现有架构实现“最近 3 天收到的 ETH 金额分布”分析，而不是再引入一套新依赖或新数据源。

### 2026-09-02

- 新增 `src/analysis/nvda3l_mint_monitor.py` 及 `src/nvda3l_mint_monitor.py`，监控 Robinhood Chain 上 NVDA3L 的 `requestMint(uint256,address)` 是否能通过 `eth_call` 模拟。
- 新增 Robinhood Chain 公共 RPC 配置，并在 `.env.example` 预留监控间隔、探测数量、Telegram 和 Pushover 配置。
- 新增 `tests/test_nvda3l_mint_monitor.py`，覆盖精度换算、cap 解析与探针、cap 增长报警、状态变化告警去重和可选告警通道。

修改原因：

- 用户需要在不广播交易的前提下持续判断 NVDA3L 是否恢复 mint 能力，并在能力恢复时收到报警。
- 复用现有 `src/core/chain_config.py`、`src/analysis/` 实现目录、根目录 wrapper、日志和 `requests`/`web3` 依赖，避免引入第二套配置或额外通知依赖。

- 增加 `cap_raw` 和 `cap_increased` 状态字段：从 `requestMint` cap 错误解析 cap，并在 cap 增加时复用 Telegram/Pushover 接口报警。

修改原因：

- 用户需要持续确认 NVDA3L 的 mint cap 是否提高，并在 cap 变化时获得通知；合约未提供标准 cap 查询函数，只能复用现有只读 mint 模拟结果提取 cap。

### 2026-09-04

- Worker 每轮保存官方 `/rhj/assets` 全量 active 股票列表，使用 `first_seen_at` 记录首次发现时间，并在 24 小时内输出 `is_new_issue=true`。
- Uniswap v4 池初始化扫描改为使用全量 active 股票，不再按前 20 个资产筛选；本地报告增加全量 `assets` 和新发行股票摘要。
- `rh_pool_dashboard` 增加 `is_new_issue` 和 `new_issue_discovered_at`，前端可直接筛选 24 小时内新发行股票对应的池。
- 新增 `supabase/migrations/20260904000003_add_new_issue_tracking.sql`，用于已有数据库升级。
- 新增 `supabase/migrations/20260904000004_dashboard_all_pools.sql`，使 dashboard 包含全量已发现股票池；无近期 Swap 的池仍保留，收益指标显示为 `null` 或 `partial`。

修改原因：

- 用户需要持续跟踪全量股票池，并在前端筛选最近 24 小时内首次发现的新发行股票。

### 2026-09-03

- 新增 `src/analysis/uniswap_v4_fee_analyzer.py` 及 `src/uniswap_v4_fee_analyzer.py`，按 Robinhood Chain Uniswap v4 的 `Swap`、`Initialize`、receipt Transfer 和可选 debug trace 生成历史收费报告。
- 新增 `tests/test_uniswap_v4_fee_analyzer.py`，覆盖区块切分、Swap 方向、core fee 估算和实际流量残差计算。
- 新增 `--pool-id` 和 `--registry-start-block`，支持先筛候选池、再用更早的 Initialize 注册表补齐 currency/hooks 元数据。
- 新增 `--skip-receipts`，支持先用长历史的 Swap/Initialize 事件筛选，再只对候选池读取 receipt。
- 新增 `--skip-initialize`，支持在限流 RPC 上先只做 Swap 费率初筛。
- 对 `eth_getLogs` 的 429 限流增加最多 5 次指数退避重试；持续限流时仍会退出并保留端点错误信息。

- 新增 `src/analysis/robinhood_rwa_uniswap_monitor.py` 及根目录兼容入口，维护 Robinhood 官方 RWA 资产快照和 Uniswap v4 池注册表。
- 新增 2 小时、4 小时、24 小时窗口的手续费收入、active liquidity USD proxy、窗口收益率和年化收益率 CSV/JSON 排名。
- 新增 `tests/test_robinhood_rwa_uniswap_monitor.py`，覆盖收益率、年化和虚拟储备计算。
- 新增 `src/core/rpc_pool.py`，支持 Robinhood Chain RPC 健康检查、脱敏输出、按请求轮询和限流故障切换。
- RWA/Uniswap 监控器支持 `ROBINHOOD_RPC_URLS`/`RH_RPC_URLS`、`ALCHEMY_RPC_URL`、`TATUM_RPC_URL` 或逗号分隔的 `--rpc-url`，并新增 `--rpc-check-only`。
- 新增 RPC 地址解析与密钥脱敏测试，健康检查结果输出到 `monitor_output/robinhood_rpc_health.json`。
- 优化固定格式 Swap 日志的轻量解码，降低大批量 RWA 池历史扫描的 CPU 开销；新增对应解码测试。
- 优先使用最近 Swap 事件携带的 active liquidity/sqrtPrice，减少逐个活跃池调用 StateView 的 RPC 请求，并在报告中标注该数据来源。
- 多 RPC 扫描时将 Swap poolId 查询批量调整为 250 个，并保留响应过大时的自动拆分，减少历史扫描请求数量。
- 新增 `supabase/migrations/20260904000000_create_rh_rwa_monitor.sql`，创建统一使用 `rh_` 前缀的资产、池、Swap、小时指标、窗口排名和 checkpoint 表，并配置索引与 RLS。
- 新增 `src/core/supabase_repository.py`，通过 Supabase PostgREST 批量 upsert 和数据库函数发布小时统计，前端可直接读取 `rh_pool_window_rankings`。
- RWA 监控器新增 `--supabase-publish`，启用基于数据库 checkpoint 的 Swap 增量扫描、事件幂等去重和 2h/4h/24h 数据库预计算，减少重复 RPC 查询。
- 兼容 Uniswap v4 动态费率池的 `Initialize.fee` 标志：写入池元数据时将不可直接展示的动态初始化费率归一为 `0`，Swap 事件仍使用实际费率计算手续费。
- 在 README 增加 6 张 `rh_` 数据表的字段、键约束、窗口口径、数据库函数、索引和 RLS 说明。
- 新增 `rh_pool_dashboard` 兼容视图 migration，修复前端读取展示字段时 TVL、成交量、APR、排名和时间为空的问题。
- 新增 `20260904000002_fix_rh_pool_dashboard_division.sql`，使用 `NULLIF(fee_pips, 0)` 修复视图查询的 `22012 division by zero`。

修改原因：

- 用户需要将 Robinhood RWA 监控数据按小时保存到 Supabase，并让前端直接查询数据库，避免每次页面刷新重复访问 Robinhood Chain RPC。
- 用户要求 Robinhood 相关 Supabase 数据表、函数和查询对象统一使用 `rh_` 前缀，降低多链数据混淆风险。
- 首次 Supabase 初始化遇到动态费率池的 `fee_pips` 检查约束错误；保留数据库现有约束并在写入层做兼容归一化。
- 修正时间窗口二分查询的区块下界，兼容不返回区块 0 的 Robinhood RPC。
- 修正符号扩展的 int128 Swap delta 解码，避免把负数输入误判为超大正数而跳过手续费计算。

修改原因：

- 需要根据 v4 交易实际 swap 后 Swap.sender 的 token 流量，筛选高 core fee、存在可观察额外扣费或 Hook 资金流证据的池子。
- v4 Hook 可改变 accounting 或把费用转入任意 treasury，不能只看 `Swap.fee`，也不能在缺少上下文时把所有差额武断归因于 Hook；因此报告显式保留置信度和限制说明。

修改原因：

- 用户需要把官方 RWA 清单落地并持续更新，再以统一窗口比较 Robinhood Chain 上 Uniswap v4 池的手续费收益和资金深度。
- v4 使用 singleton PoolManager，不能把 PoolManager 总余额直接当成单池 TVL；因此实现使用官方 StateView 的 active liquidity，并明确命名为 USD proxy。

## 7. 当前需要优先修复的结构性问题

### P0 - 依赖与环境不一致

- `requirements.txt` 已覆盖 `web3`、`eth-account`、`schedule` 等实际依赖，并保留历史分析和调度依赖。
- 依赖安装命令已写入环境准备和安装依赖说明，便于新机器复现运行环境。

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
