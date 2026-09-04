# Robinhood RWA 数据库字段说明

本文档对应 `supabase/migrations/20260904000000_create_rh_rwa_monitor.sql`，说明 Robinhood Chain（chain ID `4663`）RWA/Uniswap v4 监控数据库的表、字段、约束和访问方式。

## 1. 通用约定

- 所有表名和数据库函数名使用 `rh_` 前缀。
- 地址和 `pool_id` 统一保存为小写字符串。
- `timestamptz` 使用 UTC 时间。
- `numeric(78,0)` 保存原始整数金额；`numeric(38,18)` 保存 USD 或百分比小数。
- `pool_address` 与 `pool_id` 都是 Uniswap v4 的 bytes32 池标识，不是独立的池合约地址。
- 实际交互合约为 singleton PoolManager：`0x8366a39cc670b4001a1121b8f6a443a643e40951`。
- 前端展示字段建议直接查询 `rh_pool_dashboard`，不要从池元数据表手动拼接排名和小时统计。

## 2. `rh_rwa_assets`：官方 RWA 资产清单

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `chain_id` | integer | 否 | 链 ID；Robinhood Chain 为 `4663`。 |
| `token_address` | text | 否 | 股票/ETF Token 合约地址；主键组成部分。 |
| `token_symbol` | text | 否 | 官方 Token 符号，如 `GLXY`。 |
| `token_name` | text | 否 | 官方资产名称。 |
| `isin` | text | 是 | 证券 ISIN；官方未提供时为空。 |
| `token_decimals` | smallint | 否 | Token 精度，范围 `0-255`。 |
| `status` | text | 否 | 官方资产状态；active 资产通常为 `ASSET_STATUS_ACTIVE`。 |
| `active` | boolean | 否 | 是否仍在官方 active 清单中，默认 `true`。 |
| `registry_order` | integer | 否 | 官方接口返回顺序；用于选择 `latest20`。 |
| `first_seen_at` | timestamptz | 否 | 本地/数据库首次发现时间。 |
| `last_seen_at` | timestamptz | 否 | 最近一次官方清单同步时间。 |
| `updated_at` | timestamptz | 否 | 数据库记录最近更新时间。 |

主键：`(chain_id, token_address)`。

## 3. `rh_uniswap_v4_pools`：池元数据

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `chain_id` | integer | 否 | 链 ID。 |
| `pool_id` | text | 否 | Uniswap v4 `bytes32` 池标识；主键组成部分。 |
| `pool_address` | text | 否 | 与 `pool_id` 相同，供报告和前端统一展示。 |
| `pool_manager_address` | text | 否 | 实际 Uniswap v4 singleton PoolManager 合约地址。 |
| `currency0` / `currency1` | text | 否 | 池中排序后的 token0/token1 合约地址；原生币可用零地址。 |
| `token0_symbol` / `token1_symbol` | text | 否 | token0/token1 展示符号。 |
| `rwa_symbols` | text | 否 | 池内官方 RWA 符号，多个符号用 `+` 连接。 |
| `fee_pips` | integer | 否 | 固定初始化费率，按 pips 保存；动态初始化费率标志归一为 `0`。 |
| `tick_spacing` | integer | 否 | 池初始化时的 tick spacing。 |
| `hooks` | text | 否 | Uniswap v4 Hook 合约地址。 |
| `initialize_block` | bigint | 否 | 池 `Initialize` 事件所在区块。 |
| `initialize_timestamp` | timestamptz | 是 | 池初始化时间；当前 Worker 可暂不填充。 |
| `updated_at` | timestamptz | 否 | 元数据最近更新时间。 |

主键：`(chain_id, pool_id)`；唯一键：`(chain_id, pool_address)`。

## 4. `rh_uniswap_v4_swap_events`：原始 Swap 事件

该表保留最近 7 天的事件，用于重建小时统计。

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `chain_id` | integer | 否 | 链 ID。 |
| `tx_hash` | text | 否 | 交易哈希；幂等键组成部分。 |
| `log_index` | integer | 否 | 交易内日志索引；幂等键组成部分。 |
| `pool_id` | text | 否 | 关联的 v4 池标识。 |
| `block_number` | bigint | 否 | Swap 所在区块。 |
| `block_timestamp` | timestamptz | 否 | Swap 区块时间。 |
| `transaction_index` | integer | 否 | 区块内交易索引。 |
| `amount0` / `amount1` | numeric(78,0) | 否 | v4 Swap 的 token0/token1 signed delta 原始值。 |
| `fee_pips` | integer | 否 | Swap 事件中的实际 core fee pips。 |
| `fee_income_token0_raw` / `fee_income_token1_raw` | numeric(78,0) | 否 | 按输入方向估算的 token0/token1 手续费原始数量。 |
| `fee_income_usd` | numeric(38,18) | 是 | 结合价格估算的手续费 USD；缺价格时为空。 |
| `sqrt_price_x96` | numeric(78,0) | 是 | Swap 后 sqrt price。 |
| `active_liquidity` | numeric(78,0) | 是 | Swap 事件携带或 StateView 读取的 active liquidity。 |
| `pool_size_usd_proxy` | numeric(38,18) | 是 | 根据 active liquidity 和价格计算的 USD proxy，不是精确 LP TVL。 |
| `inserted_at` | timestamptz | 否 | 事件写入数据库时间。 |

主键：`(chain_id, tx_hash, log_index)`。重复 Swap 不会重复计数；`pool_id` 外键关联池元数据，池删除时级联删除事件。

## 5. `rh_pool_hourly_metrics`：池级小时汇总

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `chain_id` | integer | 否 | 链 ID。 |
| `asset_scope` | text | 否 | 分析范围，如 `latest20` 或 `all_active`。 |
| `pool_id` | text | 否 | 池标识。 |
| `bucket_start` | timestamptz | 否 | UTC 小时起点，必须经过 `date_trunc('hour', ...)`。 |
| `swap_count` | integer | 否 | 该小时 Swap 数量，默认 `0`。 |
| `fee_income_token0_raw` / `fee_income_token1_raw` | numeric(78,0) | 否 | 该小时 token0/token1 手续费原始数量合计。 |
| `fee_income_usd` | numeric(38,18) | 是 | 该小时 USD 手续费合计；任一事件缺价格时可为空。 |
| `active_liquidity` | numeric(78,0) | 是 | 小时内可观察的 active liquidity。 |
| `sqrt_price_x96` | numeric(78,0) | 是 | 小时内最近可观察的 sqrt price。 |
| `pool_size_usd_proxy` | numeric(38,18) | 是 | 小时结束附近的池规模 USD proxy。 |
| `latest_swap_block` | bigint | 是 | 该小时最新 Swap 区块。 |
| `bucket_complete` | boolean | 否 | 小时是否已完成；当前小时通常为 `false`。 |
| `data_quality` | text | 否 | `high` 表示费用和规模均可计算；`partial` 表示存在缺失数据。 |
| `updated_at` | timestamptz | 否 | 小时汇总最近更新时间。 |

主键：`(chain_id, asset_scope, pool_id, bucket_start)`。窗口排名包含当前小时，合计最近 `2`、`4`、`24` 个小时。

## 6. `rh_pool_window_rankings`：预计算窗口排名

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `chain_id` | integer | 否 | 链 ID。 |
| `asset_scope` | text | 否 | 分析范围；前端 `latest20` 查询应与 Worker 一致。 |
| `pool_id` | text | 否 | 池标识。 |
| `window_hours` | smallint | 否 | 当前仅允许 `2`、`4`、`24`。 |
| `pool_pair` | text | 否 | 展示交易对，如 `GLXY/USDG`。 |
| `pool_address` | text | 否 | v4 bytes32 `pool_id` 的报告字段。 |
| `token0_symbol` / `token1_symbol` | text | 否 | token0/token1 符号。 |
| `token0_address` / `token1_address` | text | 否 | token0/token1 合约地址。 |
| `rwa_symbols` | text | 否 | 池内 RWA 符号。 |
| `fee_pips` | integer | 否 | 池固定初始化费率；动态费率池为 `0`。 |
| `initialize_block` | bigint | 否 | 池初始化区块。 |
| `swap_count` | integer | 否 | 窗口内 Swap 数量。 |
| `fee_income_usd` | numeric(38,18) | 是 | 窗口小时手续费 USD 合计。 |
| `pool_size_usd_proxy` | numeric(38,18) | 是 | 窗口结束时最近 active liquidity 的 USD proxy。 |
| `window_yield_percent` | numeric(38,18) | 是 | `fee_income_usd / pool_size_usd_proxy * 100`。 |
| `annualized_yield_percent` | numeric(38,18) | 是 | 线性年化：窗口收益率 × `365 × 24 / window_hours`。 |
| `window_start` / `window_end` | timestamptz | 否 | 本次窗口的 UTC 起止时间。 |
| `data_quality` | text | 否 | `high` 或 `partial`；缺价格/池规模时收益率可为空。 |
| `is_public` | boolean | 否 | 是否允许前端通过 RLS 读取；默认 `true`。 |
| `computed_at` | timestamptz | 否 | 排名计算时间。 |

主键：`(chain_id, asset_scope, pool_id, window_hours)`。前端应按 `annualized_yield_percent desc nulls last` 排序并限制前 10 条。

## 7. `rh_sync_checkpoints`：Worker 增量进度

| 字段 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `sync_name` | text | 否 | 同步任务名；当前为 `rwa_uniswap_v4`，主键。 |
| `chain_id` | integer | 否 | 链 ID。 |
| `asset_scope` | text | 否 | 当前 checkpoint 对应的分析范围。 |
| `last_initialize_block` | bigint | 否 | 最近成功处理的 Initialize 区块。 |
| `last_swap_block` | bigint | 否 | 最近成功处理的 Swap 区块。 |
| `last_asset_sync_at` | timestamptz | 是 | 最近一次资产同步时间。 |
| `last_success_at` | timestamptz | 是 | 最近一次完整成功写入时间。 |
| `last_error` | text | 是 | 最近一次错误摘要；成功后清空。 |
| `updated_at` | timestamptz | 否 | checkpoint 最近更新时间。 |

## 8. 数据库函数

| 函数 | 参数/用途 |
| --- | --- |
| `rh_ingest_hourly_batch` | 接收 `chain_id`、`asset_scope`、`pool_ids`、最近 Initialize/Swap 区块；重建受影响池的小时指标并刷新窗口排名。 |
| `rh_refresh_window_rankings` | 接收 `chain_id`、`asset_scope` 和可选 `pool_ids`；计算 2h/4h/24h 排名。 |
| `rh_cleanup_expired_data` | 清理 7 天前的 Swap 事件和小时指标，不删除资产及池元数据。 |

## 9. 索引与安全

索引：

- `rh_swap_events_pool_block_idx` / `rh_swap_events_timestamp_idx`：加速按池、区块和时间检索 Swap。
- `rh_hourly_pool_bucket_idx` / `rh_hourly_bucket_pool_idx`：加速小时汇总和窗口聚合。
- `rh_window_ranking_order_idx`：加速按窗口和年化收益率倒序读取排名。

安全边界：

- `rh_rwa_assets`、`rh_uniswap_v4_pools`、`rh_uniswap_v4_swap_events`、`rh_pool_hourly_metrics`、`rh_sync_checkpoints` 仅供 Worker service role 使用。
- `rh_pool_window_rankings` 仅向 `anon`/`authenticated` 开放满足 `is_public` 的只读数据。
- 前端不得使用 service role key；Worker 的 service role/secret key 不能写入日志或报告。

## 10. `rh_pool_dashboard`：前端展示兼容视图

视图由 `supabase/migrations/20260904000001_create_rh_pool_dashboard_view.sql` 创建，面向截图中的池列表页面，避免前端把不同窗口的记录错误关联后显示为 0 或空值。

| 字段 | 来源/类型 | 说明 |
| --- | --- | --- |
| `chain_id` | integer | 链 ID。 |
| `asset_scope` | text | 分析范围，如 `latest20`。 |
| `pool_id` | text | v4 bytes32 池标识。 |
| `token` | text | 池内 RWA 符号，来自 `rwa_symbols`。 |
| `pool_address` | text | 与 `pool_id` 相同，供页面展示。 |
| `pool` | text | 交易对，如 `SPCX/USDG`。 |
| `tvl_usd` | numeric | 优先使用 24h 窗口池规模，缺失时回退 2h；实际含义为 USD proxy。 |
| `volume_24h_usd` | numeric | 最近 24h Swap 输入量 USD 估算；缺价格或存在 `fee_pips <= 0` 的事件时为 `null`，SQL 使用 `NULLIF(fee_pips, 0)` 防止除零。 |
| `fee_apr` | numeric | 24h `annualized_yield_percent`，线性年化；页面的“24h 年化收益率”使用此字段。 |
| `current_apr` | numeric | 当前 2h `annualized_yield_percent`；页面的“当前年化收益率”使用此字段。 |
| `apr_2h` | numeric | 与 `current_apr` 相同，为 2h `annualized_yield_percent`。 |
| `rank_2h` | integer | 在相同 `chain_id`、`asset_scope` 内按 2h 年化收益率降序生成的行号。 |
| `rank_24h` | integer | 在相同 `chain_id`、`asset_scope` 内按 24h 年化收益率降序生成的行号；页面的“24h rank”使用此字段。 |
| `metric_time` | timestamptz | 优先使用 24h 排名计算时间，缺失时回退 2h 排名计算时间。 |
| `sync_time` | timestamptz | `rh_sync_checkpoints.last_success_at`，表示 Worker 最近一次成功写入时间。 |
| `swap_count_2h` / `swap_count_24h` | integer | 两个窗口的 Swap 数量。 |
| `fee_income_2h_usd` / `fee_income_24h_usd` | numeric | 两个窗口的手续费 USD 合计。 |
| `yield_2h_percent` / `yield_24h_percent` | numeric | 两个窗口的未年化收益率。 |
| `data_quality_2h` / `data_quality_24h` | text | `high` 或 `partial`。 |
| `computed_at` | timestamptz | 24h 排名时间，缺失时回退 2h 排名时间。 |

推荐查询：

```typescript
const { data, error } = await supabase
  .from("rh_pool_dashboard")
  .select("token,pool_address,pool,tvl_usd,volume_24h_usd,fee_apr,current_apr,apr_2h,rank_2h,rank_24h,metric_time,sync_time")
  .eq("chain_id", 4663)
  .eq("asset_scope", "latest20")
  .order("rank_24h", { ascending: true })
  .limit(10);
```

若页面只需要官方排名原始字段，继续查询 `rh_pool_window_rankings`；若需要池列表页面的 TVL、24h 成交量、两个 APR 和同步时间，使用本视图。

## 11. 字段取值检查

检查时间：2026-09-04 05:02 UTC；链 ID：`4663`；范围：`latest20`。当前基础表检查结果如下：

| 页面字段 | 数据库取值/样例 | 状态 |
| --- | --- | --- |
| `token` | `GLXY` | 有值，来自 `rh_uniswap_v4_pools.rwa_symbols`。 |
| `pool_address` | `0x8c012916bcc62b3737cb47b6aa0dda921ee1663fce39007a7af2d0682e13c534` | 有值，bytes32 `pool_id`。 |
| `pool` | `GLXY/USDG` | 有值，来自 token0/token1 符号。 |
| `tvl_usd` | `9946.519327119408` | 有值；当前含义是池规模 USD proxy，不是精确 TVL。 |
| `volume_24h_usd` | `34333.199457509008` | 可由 24h Swap 的手续费和实际 fee pips 反推；缺价格或费率时为 `null`。 |
| `fee_apr` | `3521.064546205006%` | 有值，来自 24h `annualized_yield_percent`。 |
| `current_apr` / `apr_2h` | `null`（该池 2h 数据为 `partial`） | 不是数据库缺列；2h 事件存在价格缺失时应显示 `—`，不要默认显示为 0。 |
| `rank_24h` | `1` | 有值，按 24h 年化收益率降序计算。 |
| `metric_time` | `2026-09-04T05:02:41.548412+00:00` | 有值，来自排名计算时间。 |
| `sync_time` | `2026-09-04T05:02:41.548412+00:00` | 有值，来自 `rh_sync_checkpoints.last_success_at`。 |

结论：`$0` 或空白不应作为数据库无数据的判断。`null` 表示对应窗口缺少完整价格/费率/池规模，前端应显示 `—` 并结合 `data_quality_2h`、`data_quality_24h` 判断；实际有值的字段应直接使用 `rh_pool_dashboard` 的同名字段，避免从 `rh_uniswap_v4_pools` 手动左连接排名。

## 12. `22012 division by zero` 排障

如果执行 `rh_pool_dashboard` 查询时出现 `ERROR: 22012: division by zero`，说明数据库中存在 `fee_pips = 0` 的 Swap 事件。请执行增量 migration：

```text
supabase/migrations/20260904000002_fix_rh_pool_dashboard_division.sql
```

修复后，零费率事件不会中断整张视图；对应池的 `volume_24h_usd` 会返回 `null`，因为无法从零费率反推出交易量。手续费、池规模和收益率仍按窗口排名表原有口径返回。
