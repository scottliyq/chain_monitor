#!/usr/bin/env python3
"""维护 Robinhood Chain 官方 RWA 清单并分析 Uniswap v4 池收益。

该模块只读官方资产 API 和 Robinhood Chain RPC：

* ``monitor_output/robinhood_rwa_assets.json`` 保存当前及历史同步记录；
* 通过 Uniswap v4 PoolManager 的 Initialize / Swap 事件发现相关池；
* 按 2 小时、4 小时、24 小时统计估算 swap fee、active liquidity 和收益率；
* 输出 JSON 明细与按窗口、收益率降序排列的 CSV。

v4 是 singleton PoolManager，无法用单个 ERC-20 balance 直接得到某个池的精确
TVL。本分析器因此报告基于 StateView ``getLiquidity`` 和当前价格的
``active_liquidity_usd_proxy``，并在报告中明确标注为 proxy。
"""

import argparse
import csv
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import requests
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import Web3Exception

from analysis.uniswap_v4_fee_analyzer import (
    AnalyzerConfig,
    PoolMetadata,
    SwapRecord,
    UniswapV4FeeAnalyzer,
    ZERO_ADDRESS,
    _checksum,
    _chunk_ranges,
    _hex,
    estimate_core_fee_raw,
    infer_swap_assets,
)
from core.logging_utils import setup_rotating_logger
from core.rpc_pool import RotatingHTTPProvider, check_rpc_endpoints, mask_rpc_url, parse_rpc_urls
from core.supabase_repository import (
    SupabaseRepository,
    SupabaseRepositoryError,
    load_supabase_config,
)


logger = setup_rotating_logger(__name__, "robinhood_rwa_uniswap_monitor.log", backup_count=7)

ROBINHOOD_CHAIN_ID = 4663
ROBINHOOD_ASSETS_URL = "https://api.robinhood.com/rhj/assets"
ROBINHOOD_PRICES_URL = "https://api.robinhood.com/rhj/prices"
POOL_MANAGER_ADDRESS = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
STATE_VIEW_ADDRESS = "0xf3334192d15450cdd385c8b70e03f9a6bd9e673b"
USDG_ADDRESS = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
WETH_ADDRESS = "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73"
WINDOW_HOURS = (2, 4, 24)
Q96 = 2**96
INITIALIZE_TOPIC = _hex(Web3.keccak(text="Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)"))
SWAP_TOPIC = _hex(Web3.keccak(text="Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"))
SWAP_POOL_BATCH_SIZE = 250
SWAP_REORG_OVERLAP_BLOCKS = 128
ROBINHOOD_BLOCK_TIME_SECONDS = 0.1
SUPABASE_SYNC_NAME = "rwa_uniswap_v4"
DEFAULT_ASSETS_PATH = Path("monitor_output/robinhood_rwa_assets.json")
DEFAULT_POOL_CACHE_PATH = Path("monitor_output/robinhood_uniswap_pools.json")
DEFAULT_OUTPUT_PATH = Path("monitor_output/robinhood_rwa_uniswap_rankings.json")
DEFAULT_CSV_PATH = Path("monitor_output/robinhood_rwa_uniswap_rankings.csv")
DEFAULT_RPC_HEALTH_PATH = Path("monitor_output/robinhood_rpc_health.json")

STATE_VIEW_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"internalType": "bytes32", "name": "poolId", "type": "bytes32"}],
        "name": "getLiquidity",
        "outputs": [{"internalType": "uint128", "name": "liquidity", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "poolId", "type": "bytes32"}],
        "name": "getSlot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint24", "name": "protocolFee", "type": "uint24"},
            {"internalType": "uint24", "name": "lpFee", "type": "uint24"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(frozen=True)
class RwaAsset:
    """Robinhood 官方资产登记记录。"""

    token_symbol: str
    token_name: str
    contract_address: str
    isin: str | None
    token_decimals: int
    status: str
    first_seen_at: str
    last_seen_at: str
    active: bool
    registry_order: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TokenInfo:
    """池中一个币种的显示、精度和价格信息。"""

    symbol: str
    address: str
    decimals: int
    price_usd: Decimal | None


@dataclass(frozen=True)
class PoolState:
    """StateView 返回的当前池状态。"""

    active_liquidity: int
    sqrt_price_x96: int
    current_tick: int
    current_lp_fee_pips: int


@dataclass(frozen=True)
class WindowRanking:
    """一个池在一个时间窗口内的收益统计。"""

    window_hours: int
    pool_id: str
    pool_address: str
    token0_symbol: str
    token0_address: str
    token1_symbol: str
    token1_address: str
    rwa_symbols: str
    fee_pips: int
    initialize_block: int
    swap_count: int
    fee_income_token0_raw: int
    fee_income_token1_raw: int
    fee_income_usd: float | None
    active_liquidity: int | None
    active_liquidity_usd_proxy: float | None
    window_yield_percent: float | None
    annualized_yield_percent: float | None
    data_quality: str
    caveat: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> str:
    """返回 ISO-8601 UTC 时间。"""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_decimal(value: object) -> Decimal | None:
    """安全解析 API 返回的价格。"""

    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed > 0 else None


def calculate_yield_percent(fee_income_usd: Decimal | None, pool_size_usd: Decimal | None) -> float | None:
    """计算窗口收益率：手续费收入 / 当前 active liquidity proxy。"""

    if fee_income_usd is None or pool_size_usd is None or pool_size_usd <= 0:
        return None
    return float(fee_income_usd / pool_size_usd * Decimal("100"))


def annualize_yield_percent(window_yield_percent: float | None, window_hours: int) -> float | None:
    """将窗口收益率线性年化，供不同窗口内排序比较。"""

    if window_yield_percent is None or window_hours <= 0:
        return None
    return window_yield_percent * 365 * 24 / window_hours


def calculate_virtual_reserves(active_liquidity: int, sqrt_price_x96: int) -> tuple[int, int]:
    """用当前 active liquidity 和价格计算 v4 的虚拟 token reserves。"""

    if active_liquidity < 0 or sqrt_price_x96 <= 0:
        raise ValueError("active liquidity 和 sqrt price 必须有效")
    amount0 = active_liquidity * Q96 // sqrt_price_x96
    amount1 = active_liquidity * sqrt_price_x96 // Q96
    return amount0, amount1


def _decode_signed_word(value: str, bits: int) -> int:
    """解码 ABI 固定宽度有符号整数。"""

    parsed = int(value, 16) & ((1 << bits) - 1)
    sign_bit = 1 << (bits - 1)
    return parsed - (1 << bits) if parsed & sign_bit else parsed


def _decode_swap_log(log: Mapping[str, Any]) -> SwapRecord:
    """快速解码 PoolManager Swap 日志，避免逐条 web3 ABI 递归转换。"""

    topics = log.get("topics")
    if not isinstance(topics, Sequence) or len(topics) < 3:
        raise ValueError("Swap 日志 topics 不完整")
    data = _hex(log.get("data"))[2:]
    if len(data) < 6 * 64:
        raise ValueError("Swap 日志 data 不完整")
    words = [data[index : index + 64] for index in range(0, 6 * 64, 64)]
    tx_hash = _hex(log["transactionHash"])
    log_index = int(log["logIndex"])
    sender = _checksum(f"0x{_hex(topics[2])[-40:]}")
    return SwapRecord(
        tx_hash=tx_hash,
        block_number=int(log["blockNumber"]),
        transaction_index=int(log["transactionIndex"]),
        log_index=log_index,
        pool_id=_hex(topics[1]).lower(),
        sender=sender,
        amount0=_decode_signed_word(words[0], 128),
        amount1=_decode_signed_word(words[1], 128),
        fee_pips=int(words[5], 16),
        sqrt_price_x96=int(words[2], 16),
        active_liquidity=int(words[3], 16),
    )


def _load_json(path: Path, default: Mapping[str, object]) -> dict[str, Any]:
    """读取 JSON；文件不存在或格式不正确时返回默认值。"""

    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("本地 JSON 无法读取，将重新生成: %s", path)
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def select_latest_assets(assets: Sequence[RwaAsset], limit: int | None) -> list[RwaAsset]:
    """按官方资产 API 返回顺序选取前 N 个 active 资产。"""

    if limit is None:
        return list(assets)
    if limit <= 0:
        raise ValueError("latest asset limit 必须大于 0")
    return list(assets[:limit])


class RwaAssetRegistry:
    """同步并持久化 Robinhood 官方 RWA 清单。"""

    def __init__(
        self,
        output_path: Path = DEFAULT_ASSETS_PATH,
        session: requests.Session | None = None,
        assets_url: str = ROBINHOOD_ASSETS_URL,
    ) -> None:
        self.output_path = output_path
        self.session = session or requests.Session()
        self.assets_url = assets_url

    def sync(self) -> list[RwaAsset]:
        """拉取官方 active 资产并更新本地快照，返回当前可分析资产。"""

        response = self.session.get(self.assets_url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        raw_assets = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(raw_assets, list):
            raise ValueError("Robinhood assets API 返回缺少 assets 列表")

        previous = _load_json(self.output_path, {"assets": []}).get("assets", [])
        previous_by_address = {
            str(item.get("contract_address", "")).lower(): item
            for item in previous
            if isinstance(item, dict) and item.get("contract_address")
        }
        now = _utc_now()
        current: list[RwaAsset] = []
        seen_addresses: set[str] = set()
        for registry_order, item in enumerate(raw_assets):
            if not isinstance(item, dict) or item.get("status") != "ASSET_STATUS_ACTIVE":
                continue
            deployments = item.get("deployments", [])
            deployment = next(
                (
                    entry
                    for entry in deployments
                    if isinstance(entry, dict) and entry.get("chainId") == ROBINHOOD_CHAIN_ID
                ),
                None,
            )
            if not isinstance(deployment, dict) or not deployment.get("contractAddress"):
                continue
            address = Web3.to_checksum_address(str(deployment["contractAddress"]))
            key = address.lower()
            old = previous_by_address.get(key, {})
            try:
                decimals = int(item.get("tokenDecimals", 18))
            except (TypeError, ValueError):
                decimals = 18
            asset = RwaAsset(
                token_symbol=str(item.get("tokenSymbol", "")),
                token_name=str(item.get("tokenName", "")),
                contract_address=address,
                isin=str(item["isin"]) if item.get("isin") else None,
                token_decimals=decimals,
                status=str(item.get("status", "")),
                first_seen_at=str(old.get("first_seen_at", now)),
                last_seen_at=now,
                active=True,
                registry_order=registry_order,
            )
            current.append(asset)
            seen_addresses.add(key)

        historical: list[dict[str, object]] = []
        for old in previous:
            if not isinstance(old, dict):
                continue
            address = str(old.get("contract_address", "")).lower()
            if address and address not in seen_addresses:
                old_copy = dict(old)
                old_copy["active"] = False
                old_copy["status"] = "NOT_IN_CURRENT_REGISTRY"
                historical.append(old_copy)

        records = [asset.to_dict() for asset in current] + historical
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(
                {
                    "updated_at": now,
                    "chain_id": ROBINHOOD_CHAIN_ID,
                    "source": self.assets_url,
                    "active_asset_count": len(current),
                    "assets": records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return sorted(current, key=lambda asset: asset.registry_order)

    def fetch_prices(self, symbols: Iterable[str]) -> dict[str, Decimal]:
        """读取指定 RWA 的官方中间价；单个价格失败不阻断全量扫描。"""

        prices: dict[str, Decimal] = {}
        for symbol in sorted(set(symbols)):
            try:
                response = self.session.get(
                    f"{ROBINHOOD_PRICES_URL}/{symbol}",
                    timeout=20,
                )
                response.raise_for_status()
                payload = response.json()
                quotes = payload.get("quotes", []) if isinstance(payload, dict) else []
                quote = quotes[0] if isinstance(quotes, list) and quotes else {}
                if not isinstance(quote, dict):
                    continue
                bid = _parse_decimal(quote.get("bid"))
                ask = _parse_decimal(quote.get("ask"))
                price = (bid + ask) / 2 if bid is not None and ask is not None else bid or ask
                if price is not None:
                    prices[symbol] = price
            except (requests.RequestException, ValueError, KeyError):
                logger.warning("无法读取 RWA 价格，相关 USD 指标将缺失: %s", symbol)
        return prices


class RobinhoodRwaUniswapMonitor:
    """Robinhood Chain RWA 与 Uniswap v4 池收益监控器。"""

    def __init__(
        self,
        rpc_url: str | None = None,
        assets_path: Path = DEFAULT_ASSETS_PATH,
        pool_cache_path: Path = DEFAULT_POOL_CACHE_PATH,
        chunk_size: int = 1_000_000,
        pool_start_block: int = 0,
        state_view_address: str = STATE_VIEW_ADDRESS,
        native_price_usd: Decimal | None = None,
        all_rwa_pairs: bool = False,
        latest_assets_count: int | None = None,
        session: requests.Session | None = None,
        supabase_repository: SupabaseRepository | None = None,
    ) -> None:
        if chunk_size <= 0 or pool_start_block < 0:
            raise ValueError("chunk_size 必须大于 0，pool_start_block 不能为负")
        if latest_assets_count is not None and latest_assets_count <= 0:
            raise ValueError("latest_assets_count 必须大于 0")
        self.rpc_urls = parse_rpc_urls(rpc_url)
        self.rpc_url = self.rpc_urls[0]
        self.rpc_provider = RotatingHTTPProvider(self.rpc_urls, request_timeout_seconds=30)
        self.assets_path = assets_path
        self.pool_cache_path = pool_cache_path
        self.pool_start_block = pool_start_block
        self.native_price_usd = native_price_usd
        self.all_rwa_pairs = all_rwa_pairs
        self.latest_assets_count = latest_assets_count
        self.asset_scope = f"latest{latest_assets_count}" if latest_assets_count is not None else "all_active"
        self.supabase = supabase_repository
        self.registry = RwaAssetRegistry(assets_path, session=session)
        self.session = self.registry.session
        self.analyzer = UniswapV4FeeAnalyzer(
            AnalyzerConfig(
                rpc_url=self.rpc_url,
                pool_manager=POOL_MANAGER_ADDRESS,
                chunk_size=chunk_size,
                request_timeout_seconds=30,
            ),
            provider=self.rpc_provider,
        )
        self.state_view = self.analyzer.web3.eth.contract(
            address=Web3.to_checksum_address(state_view_address),
            abi=STATE_VIEW_ABI,
        )

    def _load_pool_cache(self) -> tuple[int, dict[str, PoolMetadata], set[str]]:
        """读取本地池注册表和上次扫描区块。"""

        payload = _load_json(self.pool_cache_path, {"last_scanned_block": -1, "pools": []})
        last_scanned = int(payload.get("last_scanned_block", -1))
        pools: dict[str, PoolMetadata] = {}
        raw_pools = payload.get("pools", [])
        if isinstance(raw_pools, list):
            for item in raw_pools:
                if not isinstance(item, dict) or not item.get("pool_id"):
                    continue
                pool = PoolMetadata(
                    pool_id=str(item["pool_id"]).lower(),
                    currency0=str(item["currency0"]),
                    currency1=str(item["currency1"]),
                    fee_pips=int(item["fee_pips"]),
                    tick_spacing=int(item["tick_spacing"]),
                    hooks=str(item["hooks"]),
                    initialize_block=int(item["initialize_block"]),
                )
                pools[pool.pool_id] = pool
        raw_addresses = payload.get("asset_addresses", [])
        if not isinstance(raw_addresses, list):
            raw_addresses = []
        asset_addresses = {
            str(address).lower()
            for address in raw_addresses
            if isinstance(address, str)
        }
        return last_scanned, pools, asset_addresses

    def _save_pool_cache(
        self,
        last_scanned_block: int,
        pools: Mapping[str, PoolMetadata],
        asset_addresses: set[str],
    ) -> None:
        """写入可增量更新的本地池注册表。"""

        self.pool_cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now(),
            "chain_id": ROBINHOOD_CHAIN_ID,
            "pool_manager": POOL_MANAGER_ADDRESS,
            "last_scanned_block": last_scanned_block,
            "asset_addresses": sorted(asset_addresses),
            "pools": [pool.to_dict() for pool in sorted(pools.values(), key=lambda item: item.pool_id)],
        }
        self.pool_cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_initialize_logs(
        self,
        start_block: int,
        end_block: int,
        asset_addresses: set[str],
    ) -> list[Mapping[str, Any]]:
        """按 Initialize 的 indexed currency0/currency1 过滤 RWA 池。"""

        address_topics = [f"0x{'0' * 24}{address[2:].lower()}" for address in asset_addresses]
        logs_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
        for currency_index in (2, 3):
            pending = list(_chunk_ranges(start_block, end_block, self.analyzer.config.chunk_size))
            while pending:
                lower, upper = pending.pop(0)
                topics: list[Any] = [INITIALIZE_TOPIC, None, None, None]
                topics[currency_index] = address_topics
                try:
                    logs = self.analyzer.web3.eth.get_logs(
                        {
                            "address": self.analyzer.pool_manager,
                            "fromBlock": lower,
                            "toBlock": upper,
                            "topics": topics,
                        }
                    )
                except requests.HTTPError as error:
                    status_code = error.response.status_code if error.response is not None else 0
                    if lower >= upper or status_code not in (400, 413, 429, 500, 502, 503, 504):
                        raise
                    middle = (lower + upper) // 2
                    pending[0:0] = [(lower, middle), (middle + 1, upper)]
                    continue
                except ValueError as error:
                    if lower >= upper:
                        raise
                    middle = (lower + upper) // 2
                    pending[0:0] = [(lower, middle), (middle + 1, upper)]
                    continue
                for log in logs:
                    key = (_hex(log["transactionHash"]), int(log["logIndex"]))
                    logs_by_key[key] = log
        return list(logs_by_key.values())

    def _discover_rwa_pools(
        self,
        start_block: int,
        end_block: int,
        asset_addresses: set[str],
    ) -> dict[str, PoolMetadata]:
        """从过滤后的 Initialize 日志恢复含 RWA 币种的池。"""

        pools: dict[str, PoolMetadata] = {}
        contract = self.analyzer.pool_manager_contract
        for log in self._get_initialize_logs(start_block, end_block, asset_addresses):
            decoded = contract.events.Initialize().process_log(log)
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

    def sync_pools(
        self,
        assets: Sequence[RwaAsset],
        latest_block: int,
        target_assets: Sequence[RwaAsset] | None = None,
    ) -> dict[str, PoolMetadata]:
        """增量扫描 Initialize，并保留含 RWA 币种的池。"""

        current_addresses = {asset.contract_address.lower() for asset in assets}
        last_scanned, pools, cached_addresses = self._load_pool_cache()
        target_addresses = {
            asset.contract_address.lower()
            for asset in (target_assets if target_assets is not None else assets)
        }
        new_addresses = current_addresses - cached_addresses
        if last_scanned < 0:
            if self.pool_start_block <= latest_block:
                discovered = self._discover_rwa_pools(
                    self.pool_start_block,
                    latest_block,
                    target_addresses,
                )
                pools.update(discovered)
            self._save_pool_cache(latest_block, pools, current_addresses)
        else:
            if new_addresses:
                historical_targets = target_addresses & new_addresses
                if historical_targets and self.pool_start_block <= last_scanned:
                    pools.update(
                        self._discover_rwa_pools(
                            self.pool_start_block,
                            last_scanned,
                            historical_targets,
                        )
                    )
            scan_start = last_scanned + 1
            if scan_start <= latest_block:
                pools.update(
                    self._discover_rwa_pools(
                        scan_start,
                        latest_block,
                        target_addresses,
                    )
                )
            self._save_pool_cache(latest_block, pools, current_addresses)
        quote_addresses = {USDG_ADDRESS.lower(), WETH_ADDRESS.lower(), ZERO_ADDRESS.lower()}

        def is_candidate(pool: PoolMetadata) -> bool:
            currency0_is_rwa = pool.currency0.lower() in target_addresses
            currency1_is_rwa = pool.currency1.lower() in target_addresses
            if self.all_rwa_pairs:
                return currency0_is_rwa or currency1_is_rwa
            return (
                (currency0_is_rwa and (pool.currency1.lower() in current_addresses or pool.currency1.lower() in quote_addresses))
                or (currency1_is_rwa and pool.currency0.lower() in quote_addresses)
            )

        return {
            pool_id: pool
            for pool_id, pool in pools.items()
            if is_candidate(pool)
        }

    def _block_timestamp(self, block_number: int) -> int:
        """读取区块时间戳。"""

        return int(self.analyzer.web3.eth.get_block(block_number, full_transactions=False)["timestamp"])

    def _first_block_at_or_after(self, target_timestamp: int, latest_block: int) -> int:
        """二分查找第一个不早于目标时间的区块。"""

        # 部分 Robinhood RPC 对 eth_getBlockByNumber(0x0) 返回 BlockNotFound；
        # 时间窗口只需定位近期区块，因此从区块 1 开始二分。
        low, high = 1, latest_block
        while low < high:
            middle = (low + high) // 2
            if self._block_timestamp(middle) < target_timestamp:
                low = middle + 1
            else:
                high = middle
        return low

    def _read_pool_state(self, pool_id: str) -> PoolState | None:
        """从 StateView 读取池当前 active liquidity 和价格。"""

        try:
            slot0 = self.state_view.functions.getSlot0(pool_id).call()
            liquidity = self.state_view.functions.getLiquidity(pool_id).call()
            return PoolState(
                active_liquidity=int(liquidity),
                sqrt_price_x96=int(slot0[0]),
                current_tick=int(slot0[1]),
                current_lp_fee_pips=int(slot0[3]),
            )
        except (Web3Exception, ValueError, IndexError):
            logger.warning("无法读取池状态: %s", pool_id)
            return None

    @staticmethod
    def _state_from_latest_swap(swaps: Sequence[SwapRecord]) -> PoolState | None:
        """用最近 Swap 事件携带的状态，减少逐池 StateView 请求。"""

        latest = max(
            swaps,
            key=lambda item: (item.block_number, item.transaction_index, item.log_index),
            default=None,
        )
        if latest is None or latest.sqrt_price_x96 is None or latest.active_liquidity is None:
            return None
        if latest.sqrt_price_x96 <= 0 or latest.active_liquidity < 0:
            return None
        return PoolState(
            active_liquidity=latest.active_liquidity,
            sqrt_price_x96=latest.sqrt_price_x96,
            current_tick=0,
            current_lp_fee_pips=latest.fee_pips,
        )

    def _scan_recent_swaps(
        self,
        start_block: int,
        end_block: int,
        pool_ids: Sequence[str],
    ) -> list[SwapRecord]:
        """按 poolId 分批扫描近期 Swap，避免返回无关池日志和超出 topics 限制。"""

        records: list[SwapRecord] = []
        seen: set[tuple[str, int]] = set()
        batches = [
            pool_ids[index : index + SWAP_POOL_BATCH_SIZE]
            for index in range(0, len(pool_ids), SWAP_POOL_BATCH_SIZE)
        ]
        for batch_index, batch in enumerate(batches, start=1):
            pool_topics = [_hex(pool_id).lower() for pool_id in batch]
            pending = list(_chunk_ranges(start_block, end_block, self.analyzer.config.chunk_size))
            while pending:
                lower, upper = pending.pop(0)
                for attempt in range(5):
                    try:
                        logs = self.analyzer.web3.eth.get_logs(
                            {
                                "address": self.analyzer.pool_manager,
                                "fromBlock": lower,
                                "toBlock": upper,
                                "topics": [SWAP_TOPIC, pool_topics],
                            }
                        )
                        break
                    except requests.HTTPError as error:
                        status_code = error.response.status_code if error.response is not None else 0
                        if status_code == 429 and attempt < 4:
                            time.sleep(min(30, 2**attempt))
                            continue
                        if lower < upper and status_code in (400, 413, 500, 502, 503, 504):
                            middle = (lower + upper) // 2
                            pending[0:0] = [(lower, middle), (middle + 1, upper)]
                            logs = None
                            break
                        if error.response is None or attempt == 4:
                            raise
                        raise
                    except ValueError as error:
                        details = error.args[0] if error.args and isinstance(error.args[0], Mapping) else {}
                        code = details.get("code") if isinstance(details, Mapping) else None
                        if code == 429 and attempt < 4:
                            time.sleep(min(30, 2**attempt))
                            continue
                        if lower >= upper:
                            raise
                        middle = (lower + upper) // 2
                        pending[0:0] = [(lower, middle), (middle + 1, upper)]
                        logs = None
                        break
                else:
                    raise RuntimeError("Swap 日志扫描重试失败")
                if logs is None:
                    continue
                for log in logs:
                    key = (_hex(log["transactionHash"]), int(log["logIndex"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    records.append(_decode_swap_log(log))
            if batch_index == 1 or batch_index == len(batches) or batch_index % 10 == 0:
                logger.info("Swap RWA 池扫描进度: %s/%s 批，已发现 %s 条 Swap", batch_index, len(batches), len(records))
        return records

    def _read_token_info(
        self,
        address: str,
        asset_by_address: Mapping[str, RwaAsset],
        prices: Mapping[str, Decimal],
    ) -> TokenInfo:
        """将 RWA、USDG、WETH/ETH 和未知池币种统一成 TokenInfo。"""

        checksum_address = _checksum(address)
        key = checksum_address.lower()
        asset = asset_by_address.get(key)
        if asset is not None:
            return TokenInfo(asset.token_symbol, checksum_address, asset.token_decimals, prices.get(asset.token_symbol))
        if key == USDG_ADDRESS.lower():
            return TokenInfo("USDG", checksum_address, 6, Decimal("1"))
        if key == WETH_ADDRESS.lower():
            return TokenInfo("WETH", checksum_address, 18, self.native_price_usd)
        if key == ZERO_ADDRESS.lower():
            return TokenInfo("ETH", ZERO_ADDRESS, 18, self.native_price_usd)
        if key == "0x0000000000000000000000000000000000000000":
            return TokenInfo("ETH", ZERO_ADDRESS, 18, self.native_price_usd)
        contract = self.analyzer.web3.eth.contract(
            address=checksum_address,
            abi=[
                {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
                {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
            ],
        )
        try:
            symbol = str(contract.functions.symbol().call())
        except (Web3Exception, ValueError):
            symbol = checksum_address[:8]
        try:
            decimals = int(contract.functions.decimals().call())
        except (Web3Exception, ValueError):
            decimals = 18
        return TokenInfo(symbol, checksum_address, decimals, None)

    @staticmethod
    def _usd_value(raw_amount: int, token: TokenInfo) -> Decimal | None:
        """按 token 精度与价格换算 USD。"""

        if token.price_usd is None:
            return None
        return Decimal(raw_amount) / (Decimal(10) ** token.decimals) * token.price_usd

    @staticmethod
    def _decimal_text(value: Decimal | None) -> str | None:
        """将 Decimal 转成可被 PostgREST/Postgres 精确解析的文本。"""

        return format(value, "f") if value is not None else None

    @staticmethod
    def _estimated_block_timestamp(
        block_number: int,
        latest_block: int,
        latest_timestamp: int,
    ) -> int:
        """用 Robinhood Chain 平均出块时间估算事件时间，避免逐事件 eth_call。"""

        delta_blocks = max(0, latest_block - block_number)
        return max(0, latest_timestamp - int(delta_blocks * ROBINHOOD_BLOCK_TIME_SECONDS))

    @staticmethod
    def _token_display_name(
        address: str,
        asset_by_address: Mapping[str, RwaAsset],
    ) -> str:
        """返回池元数据中稳定的 token 显示名称。"""

        key = address.lower()
        asset = asset_by_address.get(key)
        if asset is not None:
            return asset.token_symbol
        if key == USDG_ADDRESS.lower():
            return "USDG"
        if key in (WETH_ADDRESS.lower(), ZERO_ADDRESS.lower()):
            return "WETH" if key == WETH_ADDRESS.lower() else "ETH"
        return address[:10]

    @staticmethod
    def _pool_row(
        pool: PoolMetadata,
        asset_by_address: Mapping[str, RwaAsset],
    ) -> dict[str, object]:
        """将池元数据转换为 rh_uniswap_v4_pools 行。"""

        token0_symbol = RobinhoodRwaUniswapMonitor._token_display_name(pool.currency0, asset_by_address)
        token1_symbol = RobinhoodRwaUniswapMonitor._token_display_name(pool.currency1, asset_by_address)
        # Uniswap v4 动态费率会在 Initialize.fee 中携带 0x800000 标志，
        # 该值不是可直接展示的固定 fee pips；数据库旧约束仅接受普通费率。
        persisted_fee_pips = pool.fee_pips if 0 <= pool.fee_pips <= 1_000_000 else 0
        rwa_symbols = "+".join(
            asset_by_address[address.lower()].token_symbol
            for address in (pool.currency0, pool.currency1)
            if address.lower() in asset_by_address
        )
        return {
            "chain_id": ROBINHOOD_CHAIN_ID,
            "pool_id": pool.pool_id.lower(),
            "pool_address": pool.pool_id.lower(),
            "pool_manager_address": POOL_MANAGER_ADDRESS.lower(),
            "currency0": pool.currency0.lower(),
            "currency1": pool.currency1.lower(),
            "token0_symbol": token0_symbol,
            "token1_symbol": token1_symbol,
            "rwa_symbols": rwa_symbols,
            "fee_pips": persisted_fee_pips,
            "tick_spacing": pool.tick_spacing,
            "hooks": pool.hooks.lower(),
            "initialize_block": pool.initialize_block,
        }

    def _swap_row(
        self,
        pool: PoolMetadata,
        swap: SwapRecord,
        token0: TokenInfo,
        token1: TokenInfo,
        latest_block: int,
        latest_timestamp: int,
    ) -> dict[str, object]:
        """将 Swap 事件和估算手续费转换为 rh_uniswap_v4_swap_events 行。"""

        fee0_raw = 0
        fee1_raw = 0
        fee_income_usd: Decimal | None = Decimal("0")
        try:
            input_currency, _, core_input, _ = infer_swap_assets(
                swap.amount0,
                swap.amount1,
                pool.currency0,
                pool.currency1,
            )
            fee_raw = estimate_core_fee_raw(core_input, swap.fee_pips)
            if input_currency.lower() == token0.address.lower():
                fee0_raw = fee_raw
                fee_value = self._usd_value(fee_raw, token0)
            else:
                fee1_raw = fee_raw
                fee_value = self._usd_value(fee_raw, token1)
            if fee_value is None:
                fee_income_usd = None
            elif fee_income_usd is not None:
                fee_income_usd += fee_value
        except ValueError:
            fee_income_usd = None

        pool_size_usd_proxy: Decimal | None = None
        if swap.active_liquidity is not None and swap.sqrt_price_x96 is not None:
            if swap.active_liquidity > 0 and swap.sqrt_price_x96 > 0:
                virtual0, virtual1 = calculate_virtual_reserves(
                    swap.active_liquidity,
                    swap.sqrt_price_x96,
                )
                value0 = self._usd_value(virtual0, token0)
                value1 = self._usd_value(virtual1, token1)
                if value0 is not None and value1 is not None:
                    pool_size_usd_proxy = value0 + value1

        event_timestamp = self._estimated_block_timestamp(
            swap.block_number,
            latest_block,
            latest_timestamp,
        )
        return {
            "chain_id": ROBINHOOD_CHAIN_ID,
            "tx_hash": swap.tx_hash.lower(),
            "log_index": swap.log_index,
            "pool_id": pool.pool_id.lower(),
            "block_number": swap.block_number,
            "block_timestamp": datetime.fromtimestamp(event_timestamp, tz=timezone.utc).isoformat(),
            "transaction_index": swap.transaction_index,
            "amount0": swap.amount0,
            "amount1": swap.amount1,
            "fee_pips": swap.fee_pips,
            "fee_income_token0_raw": fee0_raw,
            "fee_income_token1_raw": fee1_raw,
            "fee_income_usd": self._decimal_text(fee_income_usd),
            "sqrt_price_x96": swap.sqrt_price_x96,
            "active_liquidity": swap.active_liquidity,
            "pool_size_usd_proxy": self._decimal_text(pool_size_usd_proxy),
        }

    def _publish_to_supabase(
        self,
        assets: Sequence[RwaAsset],
        pools: Mapping[str, PoolMetadata],
        swaps: Sequence[SwapRecord],
        latest_block: int,
        latest_timestamp: int,
        prices: Mapping[str, Decimal],
    ) -> list[dict[str, object]]:
        """发布元数据和增量事件，并读取数据库预计算的窗口排名。"""

        if self.supabase is None:
            return []
        asset_by_address = {asset.contract_address.lower(): asset for asset in assets}
        self.supabase.upsert_assets(
            {
                "chain_id": ROBINHOOD_CHAIN_ID,
                "token_address": asset.contract_address.lower(),
                "token_symbol": asset.token_symbol,
                "token_name": asset.token_name,
                "isin": asset.isin,
                "token_decimals": asset.token_decimals,
                "status": asset.status,
                "active": asset.active,
                "registry_order": asset.registry_order,
                "first_seen_at": asset.first_seen_at,
                "last_seen_at": asset.last_seen_at,
            }
            for asset in assets
        )
        self.supabase.upsert_pools(
            self._pool_row(pool, asset_by_address)
            for pool in pools.values()
        )

        token_cache: dict[str, tuple[TokenInfo, TokenInfo]] = {}
        event_rows: list[dict[str, object]] = []
        for swap in swaps:
            pool = pools.get(swap.pool_id)
            if pool is None:
                continue
            tokens = token_cache.get(pool.pool_id)
            if tokens is None:
                tokens = (
                    self._read_token_info(pool.currency0, asset_by_address, prices),
                    self._read_token_info(pool.currency1, asset_by_address, prices),
                )
                token_cache[pool.pool_id] = tokens
            event_rows.append(
                self._swap_row(
                    pool,
                    swap,
                    tokens[0],
                    tokens[1],
                    latest_block,
                    latest_timestamp,
                )
            )
        self.supabase.upsert_swap_events(event_rows)
        self.supabase.cleanup_expired_data()
        self.supabase.ingest_hourly_batch(
            ROBINHOOD_CHAIN_ID,
            self.asset_scope,
            sorted(pools),
            latest_block,
            latest_block,
        )
        rows: list[dict[str, object]] = []
        for window_hours in WINDOW_HOURS:
            rows.extend(
                self.supabase.fetch_window_rankings(
                    ROBINHOOD_CHAIN_ID,
                    self.asset_scope,
                    window_hours,
                    limit=10_000,
                )
            )
        return rows

    @staticmethod
    def _database_ranking_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
        """将 Supabase 当前窗口表转换为兼容 JSON/CSV 的排名行。"""

        result: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            result.append(
                {
                    "window_hours": int(row.get("window_hours", 0)),
                    "pool_id": str(row.get("pool_id", "")),
                    "pool_address": str(row.get("pool_address", row.get("pool_id", ""))),
                    "token0_symbol": str(row.get("token0_symbol", "")),
                    "token0_address": str(row.get("token0_address", "")),
                    "token1_symbol": str(row.get("token1_symbol", "")),
                    "token1_address": str(row.get("token1_address", "")),
                    "rwa_symbols": str(row.get("rwa_symbols", "")),
                    "fee_pips": int(row.get("fee_pips", 0)),
                    "initialize_block": int(row.get("initialize_block", 0)),
                    "swap_count": int(row.get("swap_count", 0)),
                    "fee_income_token0_raw": None,
                    "fee_income_token1_raw": None,
                    "fee_income_usd": row.get("fee_income_usd"),
                    "active_liquidity": None,
                    "active_liquidity_usd_proxy": row.get("pool_size_usd_proxy"),
                    "window_yield_percent": row.get("window_yield_percent"),
                    "annualized_yield_percent": row.get("annualized_yield_percent"),
                    "data_quality": row.get("data_quality", "partial"),
                    "caveat": "数据来自 Supabase 小时汇总；pool_address 为 Uniswap v4 bytes32 pool_id",
                }
            )
        return result

    def _build_ranking(
        self,
        pool: PoolMetadata,
        pool_swaps: Sequence[SwapRecord],
        window_hours: int,
        window_start_block: int,
        state: PoolState | None,
        token0: TokenInfo,
        token1: TokenInfo,
        rwa_symbols: str,
    ) -> WindowRanking:
        """聚合一个池在一个时间窗口中的费用和收益率。"""

        fee0_raw = 0
        fee1_raw = 0
        fee_income_usd: Decimal | None = Decimal("0")
        for swap in pool_swaps:
            try:
                input_currency, _, core_input, _ = infer_swap_assets(
                    swap.amount0,
                    swap.amount1,
                    pool.currency0,
                    pool.currency1,
                )
            except ValueError:
                continue
            fee_raw = estimate_core_fee_raw(core_input, swap.fee_pips)
            if input_currency.lower() == token0.address.lower():
                fee0_raw += fee_raw
                fee_value = self._usd_value(fee_raw, token0)
            else:
                fee1_raw += fee_raw
                fee_value = self._usd_value(fee_raw, token1)
            if fee_value is None:
                fee_income_usd = None
            elif fee_income_usd is not None:
                fee_income_usd += fee_value

        pool_size_usd: Decimal | None = None
        active_liquidity = state.active_liquidity if state else None
        if state and state.active_liquidity > 0 and state.sqrt_price_x96 > 0:
            virtual0, virtual1 = calculate_virtual_reserves(
                state.active_liquidity,
                state.sqrt_price_x96,
            )
            value0 = self._usd_value(virtual0, token0)
            value1 = self._usd_value(virtual1, token1)
            if value0 is not None and value1 is not None:
                pool_size_usd = value0 + value1

        window_yield = calculate_yield_percent(fee_income_usd, pool_size_usd)
        annualized = annualize_yield_percent(window_yield, window_hours)
        quality = "high" if fee_income_usd is not None and pool_size_usd is not None else "partial"
        caveat = (
            "手续费为 Swap.fee 按输入量估算；池规模优先使用窗口内最近 Swap 的 active liquidity/sqrtPrice 计算 USD proxy，不是精确 LP TVL"
        )
        if window_start_block > pool.initialize_block:
            caveat += "；窗口起点晚于池初始化区块"
        return WindowRanking(
            window_hours=window_hours,
            pool_id=pool.pool_id,
            pool_address=pool.pool_id,
            token0_symbol=token0.symbol,
            token0_address=token0.address,
            token1_symbol=token1.symbol,
            token1_address=token1.address,
            rwa_symbols=rwa_symbols,
            fee_pips=pool.fee_pips,
            initialize_block=pool.initialize_block,
            swap_count=len(pool_swaps),
            fee_income_token0_raw=fee0_raw,
            fee_income_token1_raw=fee1_raw,
            fee_income_usd=float(fee_income_usd) if fee_income_usd is not None else None,
            active_liquidity=active_liquidity,
            active_liquidity_usd_proxy=float(pool_size_usd) if pool_size_usd is not None else None,
            window_yield_percent=window_yield,
            annualized_yield_percent=annualized,
            data_quality=quality,
            caveat=caveat,
        )

    def run_once(self) -> dict[str, object]:
        """同步资产、扫描池和交易，并写入 JSON/CSV 报告。"""

        assets = self.registry.sync()
        selected_assets = select_latest_assets(assets, self.latest_assets_count)
        latest_block = self.analyzer.get_latest_block()
        latest_timestamp = self._block_timestamp(latest_block)
        pools = self.sync_pools(assets, latest_block, selected_assets)
        if not pools:
            return {
                "generated_at": _utc_now(),
                "chain_id": ROBINHOOD_CHAIN_ID,
                "latest_block": latest_block,
                "active_asset_count": len(assets),
                "selected_asset_count": len(selected_assets),
                "selected_asset_symbols": [asset.token_symbol for asset in selected_assets],
                "asset_selection_basis": "official /rhj/assets response order; API provides no publication timestamp",
                "rwa_pool_count": 0,
                "active_rwa_pool_count": 0,
                "rankings": [],
                "caveat": "未发现含官方 RWA 币种的 Uniswap v4 池",
            }

        window_blocks = {
            hours: self._first_block_at_or_after(
                latest_timestamp - hours * 3600,
                latest_block,
            )
            for hours in WINDOW_HOURS
        }
        earliest_block = min(window_blocks.values())
        scan_start = earliest_block
        if self.supabase is not None:
            checkpoint = self.supabase.get_checkpoint(SUPABASE_SYNC_NAME)
            if checkpoint is not None:
                try:
                    last_swap_block = int(checkpoint.get("last_swap_block", 0))
                except (TypeError, ValueError):
                    last_swap_block = 0
                if last_swap_block > 0:
                    scan_start = max(earliest_block, last_swap_block - SWAP_REORG_OVERLAP_BLOCKS)
        # RWA 池数量可能达到数万，RPC 对 topics 中的 poolId 数量有限制；
        # 无 Supabase 时保持历史报告口径；启用 Supabase 后只扫描 checkpoint 之后的增量区块。
        swaps = self._scan_recent_swaps(scan_start, latest_block, list(pools))
        active_pool_ids = {swap.pool_id for swap in swaps}
        asset_by_address = {asset.contract_address.lower(): asset for asset in assets}
        pool_rwa_symbols = {
            pool_id: "+".join(
                asset_by_address[address.lower()].token_symbol
                for address in (pool.currency0, pool.currency1)
                if address.lower() in asset_by_address
            )
            for pool_id, pool in pools.items()
        }
        symbols = {
            asset_by_address[address.lower()].token_symbol
            for pool in pools.values()
            for address in (pool.currency0, pool.currency1)
            if address.lower() in asset_by_address
        }
        prices = self.registry.fetch_prices(symbols)
        if self.supabase is not None:
            database_rows = self._publish_to_supabase(
                assets,
                pools,
                swaps,
                latest_block,
                latest_timestamp,
                prices,
            )
            database_rankings = self._database_ranking_rows(database_rows)
            active_database_rankings = [
                row for row in database_rankings if row.get("window_hours") == 24
            ]
            return {
                "generated_at": _utc_now(),
                "chain_id": ROBINHOOD_CHAIN_ID,
                "latest_block": latest_block,
                "latest_block_timestamp": datetime.fromtimestamp(latest_timestamp, tz=timezone.utc).isoformat(),
                "rpc_endpoints": [mask_rpc_url(url) for url in self.rpc_urls],
                "rpc_strategy": "round_robin_with_failover_on_rate_limit_or_temporary_error",
                "rpc_scan_start_block": scan_start,
                "active_asset_count": len(assets),
                "selected_asset_count": len(selected_assets),
                "selected_asset_symbols": [asset.token_symbol for asset in selected_assets],
                "asset_scope": self.asset_scope,
                "asset_selection_basis": "official /rhj/assets response order; API provides no publication timestamp",
                "rwa_pool_count": len(pools),
                "active_rwa_pool_count": len(active_database_rankings),
                "all_rwa_pairs": self.all_rwa_pairs,
                "swap_count": sum(int(row.get("swap_count", 0)) for row in active_database_rankings),
                "windows_hours": list(WINDOW_HOURS),
                "metric_definition": {
                    "fee_income_usd": "按 Swap.fee 与输入 token 官方中间价估算的 core swap fee",
                    "active_liquidity_usd_proxy": "Swap 状态按 sqrtPrice 的虚拟 reserves 换算的双边 USD 值",
                    "window_yield_percent": "窗口手续费 / 当前 active liquidity USD proxy",
                    "annualized_yield_percent": "window_yield_percent × 365 × 24 / window_hours",
                    "ranking": "数据库按每个窗口 annualized_yield_percent 降序预计算",
                },
                "rankings": database_rankings,
            }
        rankings: list[WindowRanking] = []
        swaps_by_pool: dict[str, list[SwapRecord]] = {pool_id: [] for pool_id in pools}
        for swap in swaps:
            if swap.pool_id in swaps_by_pool:
                swaps_by_pool[swap.pool_id].append(swap)

        # 没有最近 Swap 的池不会产生窗口手续费，也无法形成有意义的收益率排名；
        # 优先复用最近 Swap 携带的状态，只有旧格式缓存缺少状态时才访问 StateView。
        for pool_id in sorted(active_pool_ids):
            pool = pools[pool_id]
            token0 = self._read_token_info(pool.currency0, asset_by_address, prices)
            token1 = self._read_token_info(pool.currency1, asset_by_address, prices)
            pool_swaps = swaps_by_pool[pool_id]
            state = self._state_from_latest_swap(pool_swaps) or self._read_pool_state(pool_id)
            for hours in WINDOW_HOURS:
                start_block = window_blocks[hours]
                rankings.append(
                    self._build_ranking(
                        pool,
                        [swap for swap in swaps_by_pool[pool_id] if swap.block_number >= start_block],
                        hours,
                        start_block,
                        state,
                        token0,
                        token1,
                        pool_rwa_symbols[pool_id],
                    )
                )
        rankings.sort(
            key=lambda item: (
                item.window_hours,
                item.annualized_yield_percent if item.annualized_yield_percent is not None else -1,
            )
        )
        report: dict[str, object] = {
            "generated_at": _utc_now(),
            "chain_id": ROBINHOOD_CHAIN_ID,
            "latest_block": latest_block,
            "latest_block_timestamp": datetime.fromtimestamp(latest_timestamp, tz=timezone.utc).isoformat(),
            "rpc_endpoints": [mask_rpc_url(url) for url in self.rpc_urls],
            "rpc_strategy": "round_robin_with_failover_on_rate_limit_or_temporary_error",
            "active_asset_count": len(assets),
            "selected_asset_count": len(selected_assets),
            "selected_asset_symbols": [asset.token_symbol for asset in selected_assets],
            "asset_selection_basis": "official /rhj/assets response order; API provides no publication timestamp",
            "rwa_pool_count": len(pools),
            "active_rwa_pool_count": len(active_pool_ids),
            "all_rwa_pairs": self.all_rwa_pairs,
            "swap_count": len(swaps),
            "windows_hours": list(WINDOW_HOURS),
            "metric_definition": {
                "fee_income_usd": "按 Swap.fee 与输入 token 官方中间价估算的 core swap fee",
                "active_liquidity_usd_proxy": "StateView active liquidity 按当前 sqrtPrice 的虚拟 reserves 换算的双边 USD 值",
                "window_yield_percent": "窗口手续费 / 当前 active liquidity USD proxy",
                "annualized_yield_percent": "window_yield_percent × 365 × 24 / window_hours",
                "ranking": "每个窗口内按 annualized_yield_percent 降序；缺失 USD 数据排在最后",
            },
            "rankings": [item.to_dict() for item in rankings],
        }
        return report

    @staticmethod
    def write_report(report: Mapping[str, object], output_path: Path, csv_path: Path) -> None:
        """写入 JSON 和扁平化 CSV。"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_rows = report.get("rankings", [])
        rows = [row for row in raw_rows if isinstance(row, dict)] if isinstance(raw_rows, list) else []
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            if not rows:
                file.write("\n")
                return
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def _parse_args() -> argparse.Namespace:
    """解析 CLI 参数。"""

    parser = argparse.ArgumentParser(description="维护 Robinhood RWA 清单并分析 Uniswap v4 池收益")
    parser.add_argument("--rpc-url", help="Robinhood Chain RPC；默认读取 RH_RPC_URL/ROBINHOOD_RPC_URL")
    parser.add_argument("--rpc-check-only", action="store_true", help="只探测 RPC 节点，不扫描资产和池")
    parser.add_argument("--rpc-health-output", type=Path, default=DEFAULT_RPC_HEALTH_PATH)
    parser.add_argument("--assets-output", type=Path, default=DEFAULT_ASSETS_PATH)
    parser.add_argument("--pool-cache", type=Path, default=DEFAULT_POOL_CACHE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--pool-start-block", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--native-price-usd", type=Decimal, help="可选 ETH/USD 价格，用于 ETH/WETH 配对池")
    parser.add_argument("--all-rwa-pairs", action="store_true", help="纳入 RWA 与任意 token 的 v4 池，默认只分析主报价资产和 RWA-RWA 池")
    parser.add_argument("--latest-assets", type=int, help="只分析官方 /rhj/assets 返回顺序前 N 个 active 资产")
    parser.add_argument("--interval-minutes", type=int, default=0, help="大于 0 时按该间隔重复更新；默认只执行一次")
    parser.add_argument(
        "--supabase-publish",
        action="store_true",
        help="启用 Supabase 增量写入和数据库窗口排名；需要 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY 或 SUPABASE_SECRET_KEY",
    )
    return parser.parse_args()


def main() -> int:
    """CLI 入口。"""

    load_dotenv()
    args = _parse_args()
    if args.interval_minutes < 0:
        logger.error("--interval-minutes 不能为负数")
        return 2
    supabase_repository: SupabaseRepository | None = None
    if args.supabase_publish:
        try:
            config = load_supabase_config()
        except ValueError as error:
            logger.error("Supabase 配置无效: %s", error)
            return 2
        if config is None:
            logger.error(
                "启用 --supabase-publish 前必须设置 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY 或 SUPABASE_SECRET_KEY"
            )
            return 2
        supabase_repository = SupabaseRepository(config)
    rpc_urls = parse_rpc_urls(args.rpc_url)
    if args.rpc_check_only:
        health = check_rpc_endpoints(rpc_urls)
        health_payload = {
            "generated_at": _utc_now(),
            "chain_id": ROBINHOOD_CHAIN_ID,
            "endpoints": [item.to_dict() for item in health],
        }
        args.rpc_health_output.parent.mkdir(parents=True, exist_ok=True)
        args.rpc_health_output.write_text(
            json.dumps(health_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for item in health:
            logger.info(
                "RPC %s: ok=%s chain_id=%s block=%s latency_ms=%s",
                item.endpoint,
                item.ok,
                item.chain_id,
                item.latest_block,
                item.latency_ms,
            )
        return 0 if any(item.ok for item in health) else 1
    monitor = RobinhoodRwaUniswapMonitor(
        rpc_url=args.rpc_url,
        assets_path=args.assets_output,
        pool_cache_path=args.pool_cache,
        chunk_size=args.chunk_size,
        pool_start_block=args.pool_start_block,
        native_price_usd=args.native_price_usd,
        all_rwa_pairs=args.all_rwa_pairs,
        latest_assets_count=args.latest_assets,
        supabase_repository=supabase_repository,
    )
    while True:
        try:
            report = monitor.run_once()
            monitor.write_report(report, args.output, args.csv_output)
            logger.info(
                "完成 RWA/Uniswap 扫描：%s 个资产，%s 个池，报告写入 %s",
                report.get("active_asset_count", 0),
                report.get("rwa_pool_count", 0),
                args.output,
            )
        except (requests.RequestException, SupabaseRepositoryError, ValueError, Web3Exception, OSError) as error:
            logger.error("RWA/Uniswap 扫描失败 [%s]: %s", type(error).__name__, error.__class__.__name__)
            return 1
        if args.interval_minutes <= 0:
            return 0
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
