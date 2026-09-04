#!/usr/bin/env python3
"""历史解析 Robinhood Chain 上 Uniswap v4 的 LP / 额外收费。

这个模块只读 RPC，不发送交易。它把 PoolManager 的 Swap 事件、交易回执中的
ERC-20 Transfer，以及可选的 debug trace 放在一起分析：

* ``Swap.fee`` 是该笔 swap 实际采用的 core swap fee（含协议费影响）；
* 发起地址的实际 token 流量与 Swap delta 的差额，只在单池、可识别收款人时
  记为 ``observed_residual``，不能在通用情况下直接断言为 Hook fee；
* 如果相关 Transfer 直接流向 hook 地址，会额外标记为 ``hook_transfer_observed``。

Hook 可以通过自定义 accounting 把资金转给任意 treasury，也可能把 swap 放在
多跳交易里。因此，精确的 LP fee / hook fee 拆分需要具体 Hook ABI 或 trace；
本分析器会保留低置信度样本，而不是把所有差额都算成 Hook fee。
"""

import argparse
import csv
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dotenv import load_dotenv
import requests
from web3 import Web3
from web3.providers import HTTPProvider
from web3.providers.base import BaseProvider


LOGGER = logging.getLogger(__name__)
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
PIPS_DENOMINATOR = 1_000_000
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()

POOL_MANAGER_ABI: list[dict[str, Any]] = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "id", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "int128", "name": "amount0", "type": "int128"},
            {"indexed": False, "internalType": "int128", "name": "amount1", "type": "int128"},
            {"indexed": False, "internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"indexed": False, "internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"indexed": False, "internalType": "int24", "name": "tick", "type": "int24"},
            {"indexed": False, "internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "Swap",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "id", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "currency0", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "currency1", "type": "address"},
            {"indexed": False, "internalType": "uint24", "name": "fee", "type": "uint24"},
            {"indexed": False, "internalType": "int24", "name": "tickSpacing", "type": "int24"},
            {"indexed": False, "internalType": "address", "name": "hooks", "type": "address"},
            {"indexed": False, "internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"indexed": False, "internalType": "int24", "name": "tick", "type": "int24"},
        ],
        "name": "Initialize",
        "type": "event",
    },
]


def _hex(value: Any) -> str:
    """把 HexBytes / bytes / 字符串统一成带 0x 的小写十六进制。"""

    if isinstance(value, str):
        result = value
    elif hasattr(value, "hex"):
        result = value.hex()
    else:
        result = str(value)
    return result if result.startswith("0x") else f"0x{result}"


def _checksum(value: Any) -> str:
    """将地址标准化；原生币的 address(0) 保持全小写。"""

    address = _hex(value)
    if address.lower() == ZERO_ADDRESS:
        return ZERO_ADDRESS
    return Web3.to_checksum_address(address)


def _topic_address(value: Any) -> str:
    """从 indexed address topic 的最后 20 bytes 中取出地址。"""

    return _checksum(f"0x{_hex(value)[-40:]}")


def _chunk_ranges(start_block: int, end_block: int, chunk_size: int) -> Iterable[tuple[int, int]]:
    """按 RPC 可接受的窗口切分区块范围。"""

    if start_block < 0 or end_block < start_block:
        raise ValueError("区块范围无效")
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    cursor = start_block
    while cursor <= end_block:
        upper = min(cursor + chunk_size - 1, end_block)
        yield cursor, upper
        cursor = upper + 1


@dataclass(frozen=True)
class AnalyzerConfig:
    """历史分析器配置。"""

    rpc_url: str
    pool_manager: str = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
    chunk_size: int = 5_000
    request_timeout_seconds: int = 30
    trace_hooks: bool = False


@dataclass(frozen=True)
class PoolMetadata:
    """由 Initialize 事件恢复的 PoolKey 关键字段。"""

    pool_id: str
    currency0: str
    currency1: str
    fee_pips: int
    tick_spacing: int
    hooks: str
    initialize_block: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SwapRecord:
    """一条 PoolManager Swap 事件。"""

    tx_hash: str
    block_number: int
    transaction_index: int
    log_index: int
    pool_id: str
    sender: str
    amount0: int
    amount1: int
    fee_pips: int
    sqrt_price_x96: int | None = None
    active_liquidity: int | None = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["core_fee_rate_percent"] = self.fee_pips / 10_000
        return result


@dataclass(frozen=True)
class TokenFlow:
    """某交易中，发起地址对某 token 的转入/转出。"""

    incoming_raw: int = 0
    outgoing_raw: int = 0


@dataclass(frozen=True)
class FeeObservation:
    """将 core fee 与实际地址流量并列保存的观察结果。"""

    tx_hash: str
    pool_id: str
    initiator: str
    input_currency: str | None
    output_currency: str | None
    core_input_raw: int
    core_output_raw: int
    core_fee_pips: int
    core_fee_rate_percent: float
    core_fee_estimate_raw: int | None
    actual_input_raw: int | None
    actual_output_raw: int | None
    input_residual_raw: int | None
    output_shortfall_raw: int | None
    observed_residual_rate_percent: float | None
    observed_all_in_fee_rate_percent: float | None
    hook_transfer_raw: int
    hook_transfer_observed: bool
    transaction_swap_count: int
    transaction_pool_count: int
    confidence: str
    caveat: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PoolRanking:
    """按实际事件观察结果聚合的池子排名。"""

    pool_id: str
    swap_count: int
    unique_transaction_count: int
    max_core_fee_rate_percent: float
    average_core_fee_rate_percent: float
    observed_residual_count: int
    average_observed_residual_rate_percent: float | None
    hook_transfer_observed_count: int
    high_confidence_count: int
    low_confidence_count: int
    ranking_reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisResult:
    """完整报告。"""

    from_block: int
    to_block: int
    pools: list[PoolMetadata]
    swaps: list[SwapRecord]
    observations: list[FeeObservation]
    rankings: list[PoolRanking]

    def to_dict(self) -> dict[str, object]:
        return {
            "from_block": self.from_block,
            "to_block": self.to_block,
            "pools": [item.to_dict() for item in self.pools],
            "swaps": [item.to_dict() for item in self.swaps],
            "observations": [item.to_dict() for item in self.observations],
            "rankings": [item.to_dict() for item in self.rankings],
        }


def infer_swap_assets(
    amount0: int,
    amount1: int,
    currency0: str | None,
    currency1: str | None,
) -> tuple[str | None, str | None, int, int]:
    """根据 v4 BalanceDelta 符号判断输入/输出资产及数量。"""

    if amount0 > 0 and amount1 < 0:
        return currency0, currency1, amount0, abs(amount1)
    if amount1 > 0 and amount0 < 0:
        return currency1, currency0, amount1, abs(amount0)
    raise ValueError("Swap delta 不是标准的一进一出交易")


def estimate_core_fee_raw(core_input_raw: int, fee_pips: int) -> int:
    """用 v4 fee pips 对 gross input 做近似，供排序和交叉检查使用。

    精确值受每个 tick step 的舍入影响；因此字段名明确使用 estimate，不能替代
    LP position 的 feeGrowth 结算。
    """

    if core_input_raw < 0 or fee_pips < 0 or fee_pips >= PIPS_DENOMINATOR:
        raise ValueError("fee 或 input 无效")
    return (core_input_raw * fee_pips) // (PIPS_DENOMINATOR + fee_pips)


def calculate_observed_residual(
    core_input_raw: int,
    core_output_raw: int,
    actual_input_raw: int | None,
    actual_output_raw: int | None,
) -> tuple[int | None, int | None, float | None]:
    """比较 initiator 的实际 token 流量与 PoolManager Swap delta。

    返回 input residual、output shortfall，以及可观察残差率。两边都存在时取两者
    的较大值，避免把同一笔价格/路由差异重复相加。
    """

    input_residual = None
    output_shortfall = None
    rates: list[float] = []
    if actual_input_raw is not None:
        input_residual = max(actual_input_raw - core_input_raw, 0)
        if core_input_raw > 0:
            rates.append(input_residual / core_input_raw)
    if actual_output_raw is not None:
        output_shortfall = max(core_output_raw - actual_output_raw, 0)
        if core_output_raw > 0:
            rates.append(output_shortfall / core_output_raw)
    if not rates:
        return input_residual, output_shortfall, None
    return input_residual, output_shortfall, max(rates) * 100


class UniswapV4FeeAnalyzer:
    """使用历史 RPC 日志分析 Uniswap v4 收费的只读分析器。"""

    def __init__(self, config: AnalyzerConfig, provider: BaseProvider | None = None) -> None:
        self.config = config
        self.web3 = Web3(
            provider
            or HTTPProvider(
                config.rpc_url,
                request_kwargs={"timeout": config.request_timeout_seconds},
            )
        )
        self.pool_manager = Web3.to_checksum_address(config.pool_manager)
        self.pool_manager_contract = self.web3.eth.contract(
            address=self.pool_manager,
            abi=POOL_MANAGER_ABI,
        )

    def get_latest_block(self) -> int:
        """读取 RPC 当前最新区块。"""

        return int(self.web3.eth.block_number)

    def _get_logs(
        self,
        event_topic: str,
        start_block: int,
        end_block: int,
        pool_ids: Sequence[str] | None = None,
    ) -> list[Mapping[str, Any]]:
        logs: list[Mapping[str, Any]] = []
        pending = list(_chunk_ranges(start_block, end_block, self.config.chunk_size))
        topics: list[Any] = [event_topic]
        if pool_ids:
            topics.append([_hex(pool_id).lower() for pool_id in pool_ids])
        while pending:
            lower, upper = pending.pop(0)
            filter_params = {
                "address": self.pool_manager,
                "fromBlock": lower,
                "toBlock": upper,
                "topics": topics,
            }
            try:
                for attempt in range(5):
                    try:
                        chunk = self.web3.eth.get_logs(filter_params)
                        break
                    except requests.HTTPError as error:
                        if error.response is None or error.response.status_code != 429 or attempt == 4:
                            raise
                        delay_seconds = min(30, 2 ** attempt)
                        LOGGER.warning("RPC 返回 429，%s 秒后重试 eth_getLogs", delay_seconds)
                        time.sleep(delay_seconds)
                else:
                    raise RuntimeError("eth_getLogs 重试失败")
            except ValueError as error:
                details = error.args[0] if error.args and isinstance(error.args[0], Mapping) else {}
                data = details.get("data", {}) if isinstance(details, Mapping) else {}
                suggested_size = 0
                if isinstance(data, Mapping):
                    suggested_size = int(data.get("suggested_max_blocks") or data.get("try_blocks") or 0)
                message = str(error).lower()
                can_split_by_match_count = "logs matched" in message or "response too large" in message
                if suggested_size <= 0 and can_split_by_match_count:
                    suggested_size = max(1, (upper - lower + 1) // 2)
                if suggested_size <= 0 or lower >= upper:
                    raise
                pending[0:0] = list(_chunk_ranges(lower, upper, suggested_size))
                LOGGER.debug("RPC 要求缩小 eth_getLogs 窗口为 %s blocks", suggested_size)
                continue
            logs.extend(chunk)
        return logs

    def discover_pools(
        self,
        start_block: int,
        end_block: int,
        pool_ids: Sequence[str] | None = None,
    ) -> dict[str, PoolMetadata]:
        """从 Initialize 事件恢复区间内出现过的池子。"""

        pools: dict[str, PoolMetadata] = {}
        initialize_topic = _hex(Web3.keccak(text="Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)"))
        for log in self._get_logs(initialize_topic, start_block, end_block, pool_ids):
            decoded = self.pool_manager_contract.events.Initialize().process_log(log)
            args = decoded["args"]
            pool_id = _hex(args["id"]).lower()
            pools[pool_id] = PoolMetadata(
                pool_id=pool_id,
                currency0=_checksum(args["currency0"]),
                currency1=_checksum(args["currency1"]),
                fee_pips=int(args["fee"]),
                tick_spacing=int(args["tickSpacing"]),
                hooks=_checksum(args["hooks"]),
                initialize_block=int(log["blockNumber"]),
            )
        return pools

    def scan_swaps(
        self,
        start_block: int,
        end_block: int,
        pool_ids: Sequence[str] | None = None,
    ) -> list[SwapRecord]:
        """扫描 PoolManager 的 Swap 事件。"""

        swap_topic = _hex(Web3.keccak(text="Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"))
        records: list[SwapRecord] = []
        seen: set[tuple[str, int]] = set()
        for log in self._get_logs(swap_topic, start_block, end_block, pool_ids):
            tx_hash = _hex(log["transactionHash"])
            log_index = int(log["logIndex"])
            if (tx_hash, log_index) in seen:
                continue
            seen.add((tx_hash, log_index))
            decoded = self.pool_manager_contract.events.Swap().process_log(log)
            args = decoded["args"]
            records.append(
                SwapRecord(
                    tx_hash=tx_hash,
                    block_number=int(log["blockNumber"]),
                    transaction_index=int(log["transactionIndex"]),
                    log_index=log_index,
                    pool_id=_hex(args["id"]).lower(),
                    sender=_checksum(args["sender"]),
                    amount0=int(args["amount0"]),
                    amount1=int(args["amount1"]),
                    fee_pips=int(args["fee"]),
                    sqrt_price_x96=int(args["sqrtPriceX96"]),
                    active_liquidity=int(args["liquidity"]),
                )
            )
        return records

    def _read_initiator_flows(
        self,
        receipt: Mapping[str, Any],
        initiator: str,
        currencies: set[str],
    ) -> dict[str, TokenFlow]:
        flows: dict[str, TokenFlow] = defaultdict(TokenFlow)
        for log in receipt["logs"]:
            topics = log.get("topics", [])
            if len(topics) < 3 or _hex(topics[0]).lower() != TRANSFER_TOPIC.lower():
                continue
            token = _checksum(log["address"])
            if token.lower() not in {item.lower() for item in currencies}:
                continue
            from_address = _topic_address(topics[1])
            to_address = _topic_address(topics[2])
            amount = int(_hex(log["data"]), 16)
            previous = flows[token]
            incoming = previous.incoming_raw + (amount if to_address.lower() == initiator.lower() else 0)
            outgoing = previous.outgoing_raw + (amount if from_address.lower() == initiator.lower() else 0)
            flows[token] = TokenFlow(incoming_raw=incoming, outgoing_raw=outgoing)
        return dict(flows)

    def _trace_mentions_hook(self, tx_hash: str, hook: str) -> bool:
        """可选地检查 callTracer 中是否出现 hook 地址。"""

        if not self.config.trace_hooks or hook == ZERO_ADDRESS:
            return False
        response = self.web3.provider.make_request(
            "debug_traceTransaction",
            [tx_hash, {"tracer": "callTracer"}],
        )
        result = response.get("result")
        if not isinstance(result, Mapping):
            return False

        def walk(node: Mapping[str, Any]) -> bool:
            for key in ("from", "to"):
                value = node.get(key)
                if isinstance(value, str) and value.lower() == hook.lower():
                    return True
            children = node.get("calls", [])
            return isinstance(children, Sequence) and any(
                isinstance(child, Mapping) and walk(child) for child in children
            )

        return walk(result)

    def _make_observation(
        self,
        swap: SwapRecord,
        pool: PoolMetadata | None,
        receipt_cache: dict[str, Mapping[str, Any]],
        transaction_swap_count: int,
        transaction_pool_count: int,
    ) -> FeeObservation:
        if swap.tx_hash not in receipt_cache:
            receipt_cache[swap.tx_hash] = self.web3.eth.get_transaction_receipt(swap.tx_hash)
        receipt = receipt_cache[swap.tx_hash]
        # Swap.sender 是 PoolManager 的实际调用方和 callback 接收方；在 router
        # 多跳场景它通常是 router，而不是最外层 EOA，因此会降低置信度。
        initiator = swap.sender
        currency0 = pool.currency0 if pool else None
        currency1 = pool.currency1 if pool else None
        try:
            input_currency, output_currency, core_input, core_output = infer_swap_assets(
                swap.amount0,
                swap.amount1,
                currency0,
                currency1,
            )
        except ValueError:
            input_currency = None
            output_currency = None
            core_input = max(swap.amount0, swap.amount1, 0)
            core_output = max(abs(min(swap.amount0, swap.amount1)), 0)

        currencies = {item for item in (input_currency, output_currency) if item is not None}
        flows = self._read_initiator_flows(receipt, initiator, currencies) if currencies else {}
        input_flow = flows.get(input_currency) if input_currency else None
        output_flow = flows.get(output_currency) if output_currency else None
        actual_input = input_flow.outgoing_raw if input_flow and input_flow.outgoing_raw > 0 else None
        actual_output = output_flow.incoming_raw if output_flow and output_flow.incoming_raw > 0 else None
        input_residual, output_shortfall, residual_rate = calculate_observed_residual(
            core_input,
            core_output,
            actual_input,
            actual_output,
        )

        hook_transfer_raw = 0
        if pool and pool.hooks != ZERO_ADDRESS:
            for log in receipt["logs"]:
                topics = log.get("topics", [])
                if len(topics) < 3 or _hex(topics[0]).lower() != TRANSFER_TOPIC.lower():
                    continue
                if _topic_address(topics[2]).lower() == pool.hooks.lower():
                    token = _checksum(log["address"])
                    if token.lower() in {item.lower() for item in currencies}:
                        hook_transfer_raw += int(_hex(log["data"]), 16)
        hook_transfer_observed = hook_transfer_raw > 0 or (
            pool is not None and self._trace_mentions_hook(swap.tx_hash, pool.hooks)
        )

        confidence = (
            "high"
            if pool and actual_input is not None and actual_output is not None
            and transaction_swap_count == 1 and transaction_pool_count == 1
            else "low"
        )
        caveat = "池内单跳且 Swap.sender 的实际流量可核对；残差仅是可观察额外扣费候选"
        if transaction_swap_count != 1 or transaction_pool_count != 1:
            caveat = "同一交易包含多条/多个池的 swap；实际流量不能唯一归因到本池"
        elif confidence == "low":
            caveat = "缺少池币种或 Swap.sender 的直接收款/付款流量；不能把残差归因到本池 Hook"
        if hook_transfer_observed:
            caveat += "；检测到 Hook 地址参与资金流/调用，但不等于已得到完整 Hook fee"

        return FeeObservation(
            tx_hash=swap.tx_hash,
            pool_id=swap.pool_id,
            initiator=initiator,
            input_currency=input_currency,
            output_currency=output_currency,
            core_input_raw=core_input,
            core_output_raw=core_output,
            core_fee_pips=swap.fee_pips,
            core_fee_rate_percent=swap.fee_pips / 10_000,
            core_fee_estimate_raw=estimate_core_fee_raw(core_input, swap.fee_pips),
            actual_input_raw=actual_input,
            actual_output_raw=actual_output,
            input_residual_raw=input_residual,
            output_shortfall_raw=output_shortfall,
            observed_residual_rate_percent=residual_rate,
            observed_all_in_fee_rate_percent=(
                swap.fee_pips / 10_000 + residual_rate
                if residual_rate is not None
                else None
            ),
            hook_transfer_raw=hook_transfer_raw,
            hook_transfer_observed=hook_transfer_observed,
            transaction_swap_count=transaction_swap_count,
            transaction_pool_count=transaction_pool_count,
            confidence=confidence,
            caveat=caveat,
        )

    @staticmethod
    def _rank_pools(swaps: list[SwapRecord], observations: list[FeeObservation]) -> list[PoolRanking]:
        by_pool_swaps: dict[str, list[SwapRecord]] = defaultdict(list)
        by_pool_observations: dict[str, list[FeeObservation]] = defaultdict(list)
        for swap in swaps:
            by_pool_swaps[swap.pool_id].append(swap)
        for observation in observations:
            by_pool_observations[observation.pool_id].append(observation)

        rankings: list[PoolRanking] = []
        for pool_id, pool_swaps in by_pool_swaps.items():
            pool_observations = by_pool_observations[pool_id]
            residuals = [
                item.observed_residual_rate_percent
                for item in pool_observations
                if item.observed_residual_rate_percent is not None and item.confidence == "high"
            ]
            core_rates = [item.fee_pips / 10_000 for item in pool_swaps]
            hook_count = sum(item.hook_transfer_observed for item in pool_observations)
            high_count = sum(item.confidence == "high" for item in pool_observations)
            low_count = sum(item.confidence == "low" for item in pool_observations)
            reason = "优先按 core swap fee 排序；有实际残差时再用 residual 和 Hook 证据复核"
            rankings.append(
                PoolRanking(
                    pool_id=pool_id,
                    swap_count=len(pool_swaps),
                    unique_transaction_count=len({item.tx_hash for item in pool_swaps}),
                    max_core_fee_rate_percent=max(core_rates),
                    average_core_fee_rate_percent=sum(core_rates) / len(core_rates),
                    observed_residual_count=len(residuals),
                    average_observed_residual_rate_percent=(sum(residuals) / len(residuals) if residuals else None),
                    hook_transfer_observed_count=hook_count,
                    high_confidence_count=high_count,
                    low_confidence_count=low_count,
                    ranking_reason=reason,
                )
            )
        return sorted(
            rankings,
            key=lambda item: (
                item.max_core_fee_rate_percent,
                item.average_observed_residual_rate_percent or -1,
                item.swap_count,
            ),
            reverse=True,
        )

    def analyze(
        self,
        start_block: int,
        end_block: int,
        pool_ids: Sequence[str] | None = None,
        registry_start_block: int | None = None,
        observe_receipts: bool = True,
        discover_pool_metadata: bool = True,
    ) -> AnalysisResult:
        """扫描并生成池子排名。"""

        pool_registry_start = start_block if registry_start_block is None else registry_start_block
        pools_by_id = (
            self.discover_pools(pool_registry_start, end_block, pool_ids)
            if discover_pool_metadata
            else {}
        )
        swaps = self.scan_swaps(start_block, end_block, pool_ids)
        receipt_cache: dict[str, Mapping[str, Any]] = {}
        swaps_by_tx: dict[str, list[SwapRecord]] = defaultdict(list)
        for swap in swaps:
            swaps_by_tx[swap.tx_hash].append(swap)
        observations = []
        if observe_receipts:
            observations = [
                self._make_observation(
                    swap,
                    pools_by_id.get(swap.pool_id),
                    receipt_cache,
                    len(swaps_by_tx[swap.tx_hash]),
                    len({item.pool_id for item in swaps_by_tx[swap.tx_hash]}),
                )
                for swap in swaps
            ]
        return AnalysisResult(
            from_block=start_block,
            to_block=end_block,
            pools=list(pools_by_id.values()),
            swaps=swaps,
            observations=observations,
            rankings=self._rank_pools(swaps, observations),
        )

    @staticmethod
    def write_json(result: AnalysisResult, output_path: Path) -> None:
        """写入 JSON 报告。"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def write_rankings_csv(result: AnalysisResult, output_path: Path) -> None:
        """单独写入便于排序的池子排名 CSV。"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [item.to_dict() for item in result.rankings]
        with output_path.open("w", newline="", encoding="utf-8") as file:
            if not rows:
                return
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="历史分析 Robinhood Chain Uniswap v4 实际收费")
    parser.add_argument("--start-block", type=int, required=True)
    parser.add_argument("--end-block", type=int)
    parser.add_argument(
        "--registry-start-block",
        type=int,
        help="池 Initialize 注册表的起始区块；默认等于 start-block，历史池通常应设得更早",
    )
    parser.add_argument("--output", type=Path, default=Path("results/uniswap_v4_fee_report.json"))
    parser.add_argument("--csv-output", type=Path, default=Path("results/uniswap_v4_fee_rankings.csv"))
    parser.add_argument("--chunk-size", type=int, default=5_000)
    parser.add_argument(
        "--pool-id",
        action="append",
        dest="pool_ids",
        help="只扫描指定 poolId；可重复传入，适合先用 DEX 聚合器发现候选池",
    )
    parser.add_argument(
        "--skip-receipts",
        action="store_true",
        help="只扫描 Swap/Initialize 事件，不读取 receipt；适合先筛选 3 天候选池",
    )
    parser.add_argument(
        "--skip-initialize",
        action="store_true",
        help="只扫描 Swap，不查询 Initialize；适合先对超长历史做费率初筛",
    )
    parser.add_argument("--trace-hooks", action="store_true", help="调用 debug_traceTransaction，速度慢且依赖 debug RPC")
    return parser.parse_args()


def main() -> int:
    """CLI 入口。"""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    rpc_url = os.getenv("RH_RPC_URL") or os.getenv("ROBINHOOD_RPC_URL")
    if not rpc_url:
        LOGGER.error("未配置 RH_RPC_URL 或 ROBINHOOD_RPC_URL")
        return 2
    args = _parse_args()
    analyzer = UniswapV4FeeAnalyzer(
        AnalyzerConfig(
            rpc_url=rpc_url,
            chunk_size=args.chunk_size,
            trace_hooks=args.trace_hooks,
        )
    )
    end_block = args.end_block if args.end_block is not None else analyzer.get_latest_block()
    LOGGER.info("开始扫描 Robinhood Chain blocks %s-%s", args.start_block, end_block)
    result = analyzer.analyze(
        args.start_block,
        end_block,
        args.pool_ids,
        args.registry_start_block,
        not args.skip_receipts,
        not args.skip_initialize,
    )
    analyzer.write_json(result, args.output)
    analyzer.write_rankings_csv(result, args.csv_output)
    LOGGER.info("完成：%s swaps，%s pools，报告写入 %s", len(result.swaps), len(result.rankings), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
