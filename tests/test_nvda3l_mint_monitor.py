#!/usr/bin/env python3
"""NVDA3L mint 监控器的离线单元测试。"""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from _path_setup import ensure_src_path

ensure_src_path()

from analysis.nvda3l_mint_monitor import (  # noqa: E402
    MintCheckResult,
    NotificationDispatcher,
    Nvda3lMintMonitor,
    PushoverNotifier,
    TelegramNotifier,
)


def test_amount_is_scaled_by_token_decimals() -> None:
    monitor = Nvda3lMintMonitor(
        request_amount=Decimal("1.25"),
        web3=Mock(),
    )

    assert monitor._to_raw_amount(18) == 1_250_000_000_000_000_000


def test_alert_is_sent_only_on_transition(tmp_path: Path) -> None:
    web3 = Mock()
    web3.eth.block_number = 123
    notifier = Mock()
    monitor = Nvda3lMintMonitor(
        output_path=tmp_path / "status.json",
        notifier=notifier,
        web3=web3,
    )
    monitor.check_mint_availability = Mock(
        side_effect=[
            MintCheckResult(
                checked_at="2026-09-02T00:00:00+00:00",
                block_number=123,
                can_mint=True,
                reason="ok",
                token_address="0x1",
                implementation_address="0x2",
                simulation_from="0x3",
                request_amount="1",
                request_amount_raw=10**18,
                token_name="NVDA 3x Long",
                token_symbol="NVDAx3L",
                token_decimals=18,
                total_supply="1",
                admin="0x4",
                paused=False,
                explorer_url="https://example.test/token/0x1",
            ),
            MintCheckResult(
                checked_at="2026-09-02T00:01:00+00:00",
                block_number=124,
                can_mint=True,
                reason="ok",
                token_address="0x1",
                implementation_address="0x2",
                simulation_from="0x3",
                request_amount="1",
                request_amount_raw=10**18,
                token_name="NVDA 3x Long",
                token_symbol="NVDAx3L",
                token_decimals=18,
                total_supply="1",
                admin="0x4",
                paused=False,
                explorer_url="https://example.test/token/0x1",
            ),
        ]
    )

    monitor.run_once()
    monitor.run_once()

    notifier.send.assert_called_once()


def test_cap_is_extracted_from_cap_error() -> None:
    monitor = Nvda3lMintMonitor(web3=Mock())
    cap_raw = 550_000_000_000
    error_data = (
        "0x12a216f4"
        + f"{550_000_984_226:064x}"
        + f"{cap_raw:064x}"
    )

    monitor.token_contract.functions.requestMint.return_value.call.side_effect = (
        ValueError(error_data)
    )

    can_mint, reason, observed_cap_raw = monitor._simulate_request_mint(10**18)

    assert can_mint is False
    assert "cap 限制" in reason
    assert observed_cap_raw == cap_raw


def test_cap_increase_is_persisted_and_alerted(tmp_path: Path) -> None:
    notifier = Mock()
    monitor = Nvda3lMintMonitor(
        output_path=tmp_path / "status.json",
        notifier=notifier,
        web3=Mock(),
    )
    monitor.check_mint_availability = Mock(
        side_effect=[
            MintCheckResult(
                checked_at="2026-09-02T00:00:00+00:00",
                block_number=123,
                can_mint=False,
                reason="cap",
                token_address="0x1",
                implementation_address="0x2",
                simulation_from="0x3",
                request_amount="1",
                request_amount_raw=10**18,
                token_name="NVDA 3x Long",
                token_symbol="NVDAx3L",
                token_decimals=18,
                total_supply="1",
                admin="0x4",
                paused=False,
                explorer_url="https://example.test/token/0x1",
                cap_raw=550_000_000_000,
                cap_increased=None,
            ),
            MintCheckResult(
                checked_at="2026-09-02T00:01:00+00:00",
                block_number=124,
                can_mint=False,
                reason="cap",
                token_address="0x1",
                implementation_address="0x2",
                simulation_from="0x3",
                request_amount="1",
                request_amount_raw=10**18,
                token_name="NVDA 3x Long",
                token_symbol="NVDAx3L",
                token_decimals=18,
                total_supply="1",
                admin="0x4",
                paused=False,
                explorer_url="https://example.test/token/0x1",
                cap_raw=551_000_000_000,
                cap_increased=True,
            ),
        ]
    )

    monitor.run_once()
    monitor.run_once()

    payload = (tmp_path / "status.json").read_text(encoding="utf-8")
    assert '"cap_raw": 551000000000' in payload
    assert '"cap_increased": true' in payload
    assert any("mint cap 增加" in call.args[0] for call in notifier.send.call_args_list)


def test_cap_increased_is_computed_from_saved_state(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({"cap_raw": 550_000_000_000}), encoding="utf-8")
    web3 = Mock()
    web3.eth.block_number = 125
    monitor = Nvda3lMintMonitor(output_path=status_path, web3=web3, notifier=Mock())
    monitor._read_token_state = Mock(
        return_value=("NVDA 3x Long", "NVDAx3L", 18, 1, "0x4", False)
    )
    monitor._simulate_request_mint = Mock(
        return_value=(False, "cap", 551_000_000_000)
    )

    result = monitor.check_mint_availability()

    assert result.cap_raw == 551_000_000_000
    assert result.cap_increased is True


def test_cap_probe_keeps_tracking_cap_when_mint_probe_succeeds(tmp_path: Path) -> None:
    web3 = Mock()
    web3.eth.block_number = 126
    monitor = Nvda3lMintMonitor(
        output_path=tmp_path / "status.json",
        web3=web3,
        notifier=Mock(),
    )
    monitor._read_token_state = Mock(
        return_value=("NVDA 3x Long", "NVDAx3L", 18, 1, "0x4", False)
    )
    monitor._simulate_request_mint = Mock(
        side_effect=[
            (True, "ok", None),
            (False, "cap", 552_000_000_000),
        ]
    )

    result = monitor.check_mint_availability()

    assert result.can_mint is True
    assert result.cap_raw == 552_000_000_000
    assert result.cap_increased is None


def test_notifiers_skip_when_unconfigured() -> None:
    session = Mock()

    TelegramNotifier(bot_token="YourTelegramBotToken", chat_id="YourTelegramChatId", session=session).send("test")
    PushoverNotifier(app_token="YourPushoverAppToken", user_key="YourPushoverUserKey", session=session).send("test")

    session.post.assert_not_called()


def test_dispatcher_broadcasts() -> None:
    first = Mock()
    second = Mock()
    dispatcher = NotificationDispatcher([first, second])

    dispatcher.send("test")

    first.send.assert_called_once_with("test")
    second.send.assert_called_once_with("test")
