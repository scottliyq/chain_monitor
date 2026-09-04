#!/usr/bin/env python3
"""
ETH 主网地址近期开入金额分布分析器。

复用仓库现有的 Etherscan v2 API 配置和 BlockTimeConverter，
统计指定时间窗口内目标地址收到的原生 ETH 分布。
"""

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import requests
from dotenv import load_dotenv
from web3 import Web3

from core.block_time_converter import BlockTimeConverter
from core.chain_config import get_api_config, get_network_config
from core.logging_utils import setup_rotating_logger

load_dotenv()

logger = setup_rotating_logger(
    __name__,
    "eth_receive_distribution_analyzer.log",
    backup_count=7,
    propagate=False,
)

ETH_DECIMALS = Decimal("1000000000000000000")
DEFAULT_PAGE_SIZE = 1000
MAX_RESULT_WINDOW = 10000
DEFAULT_TARGET_ADDRESS = "0x0fca5194baa59a362a835031d9c4a25970effe68"


@dataclass(frozen=True)
class AmountBucket:
    """金额分桶配置。"""

    label: str
    min_amount: Decimal
    max_amount: Decimal | None = None


@dataclass(frozen=True)
class ReceivedTransfer:
    """单笔收到的原生 ETH 记录。"""

    tx_hash: str
    trace_id: str | None
    block_number: int
    timestamp: int
    datetime_utc: str
    from_address: str
    to_address: str
    amount_eth: Decimal
    value_wei: int
    source: str


class ResultWindowTooLargeError(RuntimeError):
    """Etherscan 返回结果窗口过大。"""


DEFAULT_BUCKETS: tuple[AmountBucket, ...] = (
    AmountBucket("0 - 0.01 ETH", Decimal("0"), Decimal("0.01")),
    AmountBucket("0.01 - 0.1 ETH", Decimal("0.01"), Decimal("0.1")),
    AmountBucket("0.1 - 1 ETH", Decimal("0.1"), Decimal("1")),
    AmountBucket("1 - 5 ETH", Decimal("1"), Decimal("5")),
    AmountBucket("5 - 10 ETH", Decimal("5"), Decimal("10")),
    AmountBucket("10 - 50 ETH", Decimal("10"), Decimal("50")),
    AmountBucket("50 - 100 ETH", Decimal("50"), Decimal("100")),
    AmountBucket(">= 100 ETH", Decimal("100"), None),
)


def _normalize_address(address: str) -> str:
    """规范化地址为 checksum 格式。"""
    if not Web3.is_address(address):
        raise ValueError(f"无效地址: {address}")
    return Web3.to_checksum_address(address)


def _bucket_contains(bucket: AmountBucket, amount: Decimal) -> bool:
    """判断金额是否落入分桶。"""
    if amount < bucket.min_amount:
        return False
    if bucket.max_amount is None:
        return True
    return amount < bucket.max_amount


def build_amount_distribution(
    transfers: Sequence[ReceivedTransfer],
    buckets: Sequence[AmountBucket] = DEFAULT_BUCKETS,
) -> list[dict[str, Any]]:
    """按金额分桶构建统计结果。"""
    total_count = len(transfers)
    total_amount = sum((transfer.amount_eth for transfer in transfers), Decimal("0"))
    distribution: list[dict[str, Any]] = []

    for bucket in buckets:
        bucket_transfers = [
            transfer for transfer in transfers if _bucket_contains(bucket, transfer.amount_eth)
        ]
        bucket_total = sum(
            (transfer.amount_eth for transfer in bucket_transfers),
            Decimal("0"),
        )
        distribution.append(
            {
                "label": bucket.label,
                "min_amount_eth": str(bucket.min_amount),
                "max_amount_eth": str(bucket.max_amount) if bucket.max_amount is not None else None,
                "transaction_count": len(bucket_transfers),
                "total_amount_eth": str(bucket_total),
                "average_amount_eth": (
                    str(bucket_total / len(bucket_transfers))
                    if bucket_transfers
                    else "0"
                ),
                "transaction_share_pct": (
                    str((Decimal(len(bucket_transfers)) / Decimal(total_count)) * Decimal("100"))
                    if total_count
                    else "0"
                ),
                "amount_share_pct": (
                    str((bucket_total / total_amount) * Decimal("100"))
                    if total_amount > 0
                    else "0"
                ),
            }
        )

    return distribution


def summarize_received_transfers(
    transfers: Sequence[ReceivedTransfer],
) -> dict[str, Any]:
    """汇总收到的 ETH 交易。"""
    sorted_transfers = sorted(
        transfers,
        key=lambda item: (item.amount_eth, item.timestamp, item.tx_hash),
        reverse=True,
    )
    total_amount = sum((transfer.amount_eth for transfer in transfers), Decimal("0"))
    unique_senders = len({transfer.from_address.lower() for transfer in transfers})
    sources: dict[str, int] = {}
    daily_breakdown: dict[str, dict[str, Any]] = {}

    for transfer in transfers:
        sources[transfer.source] = sources.get(transfer.source, 0) + 1
        day_key = datetime.fromtimestamp(
            transfer.timestamp,
            tz=timezone.utc,
        ).strftime("%Y-%m-%d")
        if day_key not in daily_breakdown:
            daily_breakdown[day_key] = {
                "transaction_count": 0,
                "total_amount_eth": Decimal("0"),
            }
        daily_breakdown[day_key]["transaction_count"] += 1
        daily_breakdown[day_key]["total_amount_eth"] += transfer.amount_eth

    return {
        "received_transaction_count": len(transfers),
        "total_received_eth": str(total_amount),
        "average_received_eth": (
            str(total_amount / len(transfers)) if transfers else "0"
        ),
        "median_proxy_eth": (
            str(sorted_transfers[len(sorted_transfers) // 2].amount_eth)
            if sorted_transfers
            else "0"
        ),
        "largest_received_eth": (
            str(sorted_transfers[0].amount_eth) if sorted_transfers else "0"
        ),
        "smallest_received_eth": (
            str(sorted(transfers, key=lambda item: item.amount_eth)[0].amount_eth)
            if transfers
            else "0"
        ),
        "unique_sender_count": unique_senders,
        "source_breakdown": sources,
        "daily_breakdown": {
            day: {
                "transaction_count": data["transaction_count"],
                "total_amount_eth": str(data["total_amount_eth"]),
            }
            for day, data in sorted(daily_breakdown.items())
        },
    }


class EthReceiveDistributionAnalyzer:
    """目标地址收到 ETH 金额分布分析器。"""

    def __init__(
        self,
        address: str,
        start_time: str | None = None,
        end_time: str | None = None,
        days: int = 3,
        include_internal: bool = True,
    ) -> None:
        if days <= 0:
            raise ValueError("days 必须大于 0")

        self.logger = logging.getLogger(__name__)
        self.network = "ethereum"
        self.network_config = get_network_config(self.network)
        self.api_config = get_api_config(self.network)
        self.address = _normalize_address(address)
        self.include_internal = include_internal
        self.days = days

        self.start_datetime, self.end_datetime = self._resolve_time_window(
            start_time,
            end_time,
            days,
        )
        self.start_time_str = self.start_datetime.strftime("%Y-%m-%d %H:%M:%S")
        self.end_time_str = self.end_datetime.strftime("%Y-%m-%d %H:%M:%S")

        self.block_converter = BlockTimeConverter(self.api_config)
        self.start_timestamp = self.block_converter.datetime_to_timestamp(self.start_time_str)
        self.end_timestamp = self.block_converter.datetime_to_timestamp(self.end_time_str)

        start_block = self.block_converter.get_block_by_timestamp(
            self.start_timestamp,
            "before",
        )
        time.sleep(0.2)
        end_block = self.block_converter.get_block_by_timestamp(
            self.end_timestamp,
            "before",
        )
        if start_block is None or end_block is None:
            raise RuntimeError("无法解析时间范围对应的区块号")

        self.start_block = start_block
        self.end_block = end_block

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Codex/1.0"
                )
            }
        )

        self.logger.info("🚀 初始化 ETH 收款金额分布分析器")
        self.logger.info("   目标地址: %s", self.address)
        self.logger.info("   网络: %s", self.network_config["name"])
        self.logger.info("   时间范围: %s UTC -> %s UTC", self.start_time_str, self.end_time_str)
        self.logger.info("   区块范围: %s -> %s", self.start_block, self.end_block)
        self.logger.info("   包含 internal 交易: %s", "是" if self.include_internal else "否")

    def _resolve_time_window(
        self,
        start_time: str | None,
        end_time: str | None,
        days: int,
    ) -> tuple[datetime, datetime]:
        """解析分析时间窗口。"""
        if start_time and not end_time:
            raise ValueError("传入 start_time 时必须同时传入 end_time")
        if end_time and not start_time:
            raise ValueError("传入 end_time 时必须同时传入 start_time")

        if start_time and end_time:
            start_timestamp = self._parse_utc_timestamp(start_time)
            end_timestamp = self._parse_utc_timestamp(end_time)
            if start_timestamp >= end_timestamp:
                raise ValueError("start_time 必须早于 end_time")
            return (
                datetime.fromtimestamp(start_timestamp, tz=timezone.utc),
                datetime.fromtimestamp(end_timestamp, tz=timezone.utc),
            )

        end_datetime = datetime.now(timezone.utc)
        start_datetime = end_datetime - timedelta(days=days)
        return start_datetime, end_datetime

    def _parse_utc_timestamp(self, time_text: str) -> int:
        """借助 BlockTimeConverter 统一解析时间字符串。"""
        converter = BlockTimeConverter(self.api_config)
        return converter.datetime_to_timestamp(time_text)

    def _request_account_transactions(
        self,
        action: str,
        page: int,
        start_block: int,
        end_block: int,
        offset: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """请求 Etherscan account API。"""
        params = {
            "chainid": self.api_config["chain_id"],
            "module": "account",
            "action": action,
            "address": self.address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": "asc",
            "apikey": self.api_config["api_key"],
        }

        response = self.session.get(
            self.api_config["base_url"],
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", [])
        message = str(payload.get("message", ""))

        if "Result window is too large" in message:
            raise ResultWindowTooLargeError(message)

        if isinstance(result, list):
            if payload.get("status") == "0" and "No transactions found" in message:
                return []
            return result

        raise RuntimeError(f"Etherscan 返回异常: {payload}")

    def _fetch_transactions_by_block_range(
        self,
        action: str,
        start_block: int,
        end_block: int,
    ) -> list[dict[str, Any]]:
        """按区块范围递归拉取交易，避开 Etherscan 10000 结果窗口限制。"""
        if start_block > end_block:
            return []

        try:
            range_items = self._request_account_transactions(
                action=action,
                page=1,
                start_block=start_block,
                end_block=end_block,
                offset=MAX_RESULT_WINDOW,
            )
        except ResultWindowTooLargeError:
            if start_block == end_block:
                raise RuntimeError(
                    f"单区块 {start_block} 的 {action} 结果仍超过窗口限制，无法继续拆分"
                )
            mid_block = (start_block + end_block) // 2
            self.logger.info(
                "   action=%s 区块范围 %s-%s 超出窗口限制，拆分为 %s-%s 和 %s-%s",
                action,
                start_block,
                end_block,
                start_block,
                mid_block,
                mid_block + 1,
                end_block,
            )
            left_items = self._fetch_transactions_by_block_range(
                action,
                start_block,
                mid_block,
            )
            time.sleep(0.2)
            right_items = self._fetch_transactions_by_block_range(
                action,
                mid_block + 1,
                end_block,
            )
            return left_items + right_items

        self.logger.info(
            "   action=%s 区块范围 %s-%s 拉取 %s 笔",
            action,
            start_block,
            end_block,
            len(range_items),
        )

        if len(range_items) < MAX_RESULT_WINDOW or start_block == end_block:
            return range_items

        mid_block = (start_block + end_block) // 2
        self.logger.info(
            "   action=%s 区块范围 %s-%s 已触达 %s 条上限，继续拆分",
            action,
            start_block,
            end_block,
            MAX_RESULT_WINDOW,
        )
        left_items = self._fetch_transactions_by_block_range(
            action,
            start_block,
            mid_block,
        )
        time.sleep(0.2)
        right_items = self._fetch_transactions_by_block_range(
            action,
            mid_block + 1,
            end_block,
        )
        return left_items + right_items

    def _fetch_all_transactions(self, action: str) -> list[dict[str, Any]]:
        """拉取指定 action 的全量交易。"""
        return self._fetch_transactions_by_block_range(
            action,
            self.start_block,
            self.end_block,
        )

    def _parse_received_transfer(
        self,
        raw_tx: dict[str, Any],
        source: str,
    ) -> ReceivedTransfer | None:
        """解析收到的 ETH 记录。"""
        to_address = str(raw_tx.get("to", "")).strip()
        if not to_address or to_address.lower() != self.address.lower():
            return None

        if str(raw_tx.get("isError", "0")) == "1":
            return None

        txreceipt_status = str(raw_tx.get("txreceipt_status", "")).strip()
        if txreceipt_status and txreceipt_status != "1":
            return None

        value_text = str(raw_tx.get("value", "0")).strip()
        if not value_text or value_text == "0":
            return None

        timestamp = int(str(raw_tx.get("timeStamp", "0")))
        if timestamp < self.start_timestamp or timestamp > self.end_timestamp:
            return None

        value_wei = int(value_text)
        amount_eth = Decimal(value_wei) / ETH_DECIMALS
        if amount_eth <= 0:
            return None

        from_address = str(raw_tx.get("from", "")).strip()
        trace_id = str(raw_tx.get("traceId", "")).strip() or None

        return ReceivedTransfer(
            tx_hash=str(raw_tx.get("hash", "")).strip(),
            trace_id=trace_id,
            block_number=int(str(raw_tx.get("blockNumber", "0"))),
            timestamp=timestamp,
            datetime_utc=datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc,
            ).isoformat(),
            from_address=_normalize_address(from_address) if from_address else from_address,
            to_address=_normalize_address(to_address),
            amount_eth=amount_eth,
            value_wei=value_wei,
            source=source,
        )

    def collect_received_transfers(self) -> list[ReceivedTransfer]:
        """拉取并过滤目标地址收到的 ETH。"""
        self.logger.info("🔄 开始拉取 normal 交易...")
        normal_transactions = self._fetch_all_transactions("txlist")
        received_transfers = [
            transfer
            for raw_tx in normal_transactions
            if (transfer := self._parse_received_transfer(raw_tx, "normal")) is not None
        ]

        if self.include_internal:
            self.logger.info("🔄 开始拉取 internal 交易...")
            internal_transactions = self._fetch_all_transactions("txlistinternal")
            received_transfers.extend(
                transfer
                for raw_tx in internal_transactions
                if (transfer := self._parse_received_transfer(raw_tx, "internal")) is not None
            )

        unique_transfers: dict[str, ReceivedTransfer] = {}
        for transfer in received_transfers:
            unique_key = (
                f"{transfer.source}:{transfer.tx_hash}:{transfer.trace_id or 'root'}:"
                f"{transfer.from_address}:{transfer.to_address}:{transfer.value_wei}"
            )
            unique_transfers[unique_key] = transfer

        sorted_transfers = sorted(
            unique_transfers.values(),
            key=lambda item: (item.timestamp, item.block_number, item.tx_hash, item.source),
        )

        self.logger.info("✅ 收到 ETH 记录过滤完成，共 %s 笔", len(sorted_transfers))
        return sorted_transfers

    def save_result(
        self,
        result: dict[str, Any],
        output_dir: str = "results",
    ) -> tuple[Path, Path]:
        """保存分析结果到文件。"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        address_short = self.address[:10].lower()

        json_path = output_path / (
            f"eth_receive_distribution_{address_short}_{timestamp}.json"
        )
        txt_path = output_path / (
            f"eth_receive_distribution_{address_short}_{timestamp}.txt"
        )

        with json_path.open("w", encoding="utf-8") as json_file:
            json.dump(result, json_file, indent=2, ensure_ascii=False, default=str)

        with txt_path.open("w", encoding="utf-8") as text_file:
            text_file.write("ETH 收款金额分布分析报告\n")
            text_file.write("=" * 60 + "\n")
            text_file.write(f"生成时间: {datetime.now(timezone.utc).isoformat()}\n")
            text_file.write(f"目标地址: {self.address}\n")
            text_file.write(f"时间范围: {self.start_time_str} UTC -> {self.end_time_str} UTC\n")
            text_file.write(f"区块范围: {self.start_block} -> {self.end_block}\n")
            text_file.write(f"包含 internal: {'是' if self.include_internal else '否'}\n\n")

            summary = result["summary"]
            text_file.write("汇总\n")
            text_file.write("-" * 60 + "\n")
            text_file.write(f"收到交易数: {summary['received_transaction_count']}\n")
            text_file.write(f"总收到 ETH: {summary['total_received_eth']}\n")
            text_file.write(f"平均每笔 ETH: {summary['average_received_eth']}\n")
            text_file.write(f"最大单笔 ETH: {summary['largest_received_eth']}\n")
            text_file.write(f"最小单笔 ETH: {summary['smallest_received_eth']}\n")
            text_file.write(f"唯一发送方数量: {summary['unique_sender_count']}\n\n")

            text_file.write("金额分布\n")
            text_file.write("-" * 60 + "\n")
            for bucket in result["distribution"]:
                text_file.write(
                    f"{bucket['label']}: "
                    f"{bucket['transaction_count']} 笔, "
                    f"{bucket['total_amount_eth']} ETH, "
                    f"笔数占比 {bucket['transaction_share_pct']}%\n"
                )

        self.logger.info("💾 分析结果已保存到 %s 和 %s", json_path, txt_path)
        return json_path, txt_path

    def run(self, output_dir: str = "results") -> dict[str, Any]:
        """执行完整分析。"""
        transfers = self.collect_received_transfers()
        distribution = build_amount_distribution(transfers)
        summary = summarize_received_transfers(transfers)

        top_transfers = sorted(
            transfers,
            key=lambda item: (item.amount_eth, item.timestamp, item.tx_hash),
            reverse=True,
        )[:10]

        result: dict[str, Any] = {
            "analysis_info": {
                "address": self.address,
                "network": self.network,
                "network_name": self.network_config["name"],
                "start_time_utc": self.start_time_str,
                "end_time_utc": self.end_time_str,
                "start_timestamp": self.start_timestamp,
                "end_timestamp": self.end_timestamp,
                "start_block": self.start_block,
                "end_block": self.end_block,
                "days": self.days,
                "include_internal": self.include_internal,
                "query_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "api_base_url": self.api_config["base_url"],
            },
            "summary": summary,
            "distribution": distribution,
            "top_received_transactions": [
                {
                    **asdict(transfer),
                    "amount_eth": str(transfer.amount_eth),
                }
                for transfer in top_transfers
            ],
            "received_transactions": [
                {
                    **asdict(transfer),
                    "amount_eth": str(transfer.amount_eth),
                }
                for transfer in transfers
            ],
        }

        json_path, txt_path = self.save_result(result, output_dir=output_dir)
        result["output_files"] = {
            "json": str(json_path),
            "txt": str(txt_path),
        }
        return result


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="分析指定 ETH 主网地址最近一段时间收到的 ETH 金额分布",
    )
    parser.add_argument(
        "--address",
        default=DEFAULT_TARGET_ADDRESS,
        help=f"目标地址，默认 {DEFAULT_TARGET_ADDRESS}",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="分析最近多少天，默认 3",
    )
    parser.add_argument(
        "--start-time",
        help='自定义开始时间（UTC），格式如 "2026-04-22 00:00:00"',
    )
    parser.add_argument(
        "--end-time",
        help='自定义结束时间（UTC），格式如 "2026-04-25 00:00:00"',
    )
    parser.add_argument(
        "--no-internal",
        action="store_true",
        help="不包含 internal 交易",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="结果输出目录，默认 results",
    )
    args = parser.parse_args()

    try:
        analyzer = EthReceiveDistributionAnalyzer(
            address=args.address,
            start_time=args.start_time,
            end_time=args.end_time,
            days=args.days,
            include_internal=not args.no_internal,
        )
        result = analyzer.run(output_dir=args.output_dir)
        logger.info("🎯 分析完成，结果文件: %s", result["output_files"])
    except (
        ValueError,
        RuntimeError,
        requests.RequestException,
        OSError,
    ):
        logger.exception("❌ ETH 收款金额分布分析失败")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
