#!/usr/bin/env python3
"""ETH 收款金额分布分析器单测。"""

from decimal import Decimal

try:
    from tests._path_setup import ensure_src_path
except ImportError:
    from _path_setup import ensure_src_path

ensure_src_path()

from analysis.eth_receive_distribution_analyzer import (  # noqa: E402
    ReceivedTransfer,
    build_amount_distribution,
    summarize_received_transfers,
)


def _build_transfer(
    amount_eth: str,
    timestamp: int,
    source: str = "normal",
    sender: str = "0x1111111111111111111111111111111111111111",
) -> ReceivedTransfer:
    value_wei = int(Decimal(amount_eth) * Decimal("1000000000000000000"))
    return ReceivedTransfer(
        tx_hash=f"0x{timestamp:064x}",
        trace_id=None,
        block_number=timestamp,
        timestamp=timestamp,
        datetime_utc="2026-04-25T00:00:00+00:00",
        from_address=sender,
        to_address="0x0FcA5194BAA59a362A835031D9C4a25970EFfe68",
        amount_eth=Decimal(amount_eth),
        value_wei=value_wei,
        source=source,
    )


def test_build_amount_distribution_groups_expected_buckets() -> None:
    transfers = [
        _build_transfer("0.005", 1),
        _build_transfer("0.05", 2),
        _build_transfer("0.5", 3),
        _build_transfer("3", 4),
        _build_transfer("12", 5),
    ]

    distribution = build_amount_distribution(transfers)
    bucket_counts = {
        bucket["label"]: bucket["transaction_count"] for bucket in distribution
    }

    assert bucket_counts["0 - 0.01 ETH"] == 1
    assert bucket_counts["0.01 - 0.1 ETH"] == 1
    assert bucket_counts["0.1 - 1 ETH"] == 1
    assert bucket_counts["1 - 5 ETH"] == 1
    assert bucket_counts["10 - 50 ETH"] == 1


def test_summarize_received_transfers_tracks_totals_and_sources() -> None:
    transfers = [
        _build_transfer("0.5", 1714000000, source="normal"),
        _build_transfer(
            "1.5",
            1714003600,
            source="internal",
            sender="0x2222222222222222222222222222222222222222",
        ),
    ]

    summary = summarize_received_transfers(transfers)

    assert summary["received_transaction_count"] == 2
    assert summary["total_received_eth"] == "2.0"
    assert summary["largest_received_eth"] == "1.5"
    assert summary["unique_sender_count"] == 2
    assert summary["source_breakdown"] == {"normal": 1, "internal": 1}
