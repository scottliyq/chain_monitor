#!/usr/bin/env python3
"""监控 Robinhood Chain 上 NVDA3L 的可 mint 状态。"""

import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, Sequence

import requests
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError, Web3Exception

from core.chain_config import get_rpc_url
from core.logging_utils import setup_rotating_logger


logger = setup_rotating_logger(__name__, "nvda3l_mint_monitor.log", backup_count=7)
load_dotenv()

ROBINHOOD_EXPLORER_URL = "https://robinhoodchain.blockscout.com"
NVDA3L_TOKEN_ADDRESS = "0xF51fb54DE60f6e16252E852A5Ed0E60B8307606A"
NVDA3L_IMPLEMENTATION_ADDRESS = "0xcfB0f21f200045b3c2eF8a20fB36498e32395C88"
DEFAULT_SIMULATION_FROM = "0x0000000000000000000000000000000000000001"
DEFAULT_REQUEST_AMOUNT = Decimal("1")
DEFAULT_OUTPUT_PATH = Path("monitor_output/nvda3l_mint_status.json")
CAP_ERROR_SELECTOR = "12a216f4"
CAP_PROBE_AMOUNT_RAW = 10**36

TOKEN_ABI = [
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "admin",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "paused",
        "outputs": [{"type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "recipient", "type": "address"},
        ],
        "name": "requestMint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


class Notifier(Protocol):
    """告警发送器接口。"""

    def send(self, message: str) -> None:
        """发送一条告警消息。"""


class TelegramNotifier:
    """可选 Telegram Bot 告警实现。"""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.session = session or requests.Session()

    def send(self, message: str) -> None:
        """发送 Telegram 消息；未配置凭据时跳过。"""
        if not _is_configured(self.bot_token) or not _is_configured(self.chat_id):
            return

        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            response = self.session.post(
                endpoint,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Telegram 告警发送失败")


class PushoverNotifier:
    """可选 Pushover 告警实现。"""

    endpoint = "https://api.pushover.net/1/messages.json"

    def __init__(
        self,
        app_token: str | None = None,
        user_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.app_token = app_token or os.getenv("PUSHOVER_APP_TOKEN")
        self.user_key = user_key or os.getenv("PUSHOVER_USER_KEY")
        self.session = session or requests.Session()

    def send(self, message: str) -> None:
        """发送 Pushover 消息；未配置凭据时跳过。"""
        if not _is_configured(self.app_token) or not _is_configured(self.user_key):
            return

        try:
            response = self.session.post(
                self.endpoint,
                data={
                    "token": self.app_token,
                    "user": self.user_key,
                    "message": message,
                    "title": "NVDA3L mint 可用",
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Pushover 告警发送失败")


class NotificationDispatcher:
    """向所有已配置的告警通道广播消息。"""

    def __init__(self, notifiers: Sequence[Notifier] | None = None) -> None:
        self.notifiers = tuple(notifiers or (TelegramNotifier(), PushoverNotifier()))

    def send(self, message: str) -> None:
        """广播消息；单个通道失败不会阻断监控。"""
        for notifier in self.notifiers:
            notifier.send(message)


def _is_configured(value: str | None) -> bool:
    """判断环境变量是否是实际配置，而不是示例占位符。"""
    return bool(value and not value.lower().startswith("your"))


@dataclass(frozen=True)
class MintCheckResult:
    """一次 NVDA3L mint 可用性检查结果。"""

    checked_at: str
    block_number: int
    can_mint: bool
    reason: str
    token_address: str
    implementation_address: str
    simulation_from: str
    request_amount: str
    request_amount_raw: int
    token_name: str | None
    token_symbol: str | None
    token_decimals: int | None
    total_supply: str | None
    admin: str | None
    paused: bool | None
    explorer_url: str
    cap_raw: int | None = None
    cap_increased: bool | None = None


class Nvda3lMintMonitor:
    """通过 RPC 模拟 token 的 requestMint 交易并在可用时告警。"""

    def __init__(
        self,
        rpc_url: str | None = None,
        token_address: str = NVDA3L_TOKEN_ADDRESS,
        implementation_address: str = NVDA3L_IMPLEMENTATION_ADDRESS,
        simulation_from: str = DEFAULT_SIMULATION_FROM,
        request_amount: Decimal = DEFAULT_REQUEST_AMOUNT,
        output_path: Path = DEFAULT_OUTPUT_PATH,
        notifier: Notifier | None = None,
        web3: Web3 | None = None,
    ) -> None:
        if request_amount <= 0:
            raise ValueError("request_amount 必须大于 0")

        self.rpc_url = rpc_url or get_rpc_url(
            "robinhood",
            use_generic_fallback=False,
        )
        self.token_address = Web3.to_checksum_address(token_address)
        self.implementation_address = Web3.to_checksum_address(implementation_address)
        self.simulation_from = Web3.to_checksum_address(simulation_from)
        self.request_amount = request_amount
        self.output_path = output_path
        self.notifier = notifier or NotificationDispatcher()
        self.web3 = web3 or Web3(
            Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 20})
        )
        self.token_contract = self.web3.eth.contract(
            address=self.token_address,
            abi=TOKEN_ABI,
        )
        self.previous_can_mint: bool | None = None
        self.previous_cap_raw = self._load_previous_cap()

    def check_mint_availability(self) -> MintCheckResult:
        """读取链上状态并模拟 requestMint。"""
        block_number = self.web3.eth.block_number
        token_name, token_symbol, token_decimals, total_supply, admin, paused = (
            self._read_token_state()
        )
        request_amount_raw = self._to_raw_amount(token_decimals)
        can_mint, reason, observed_cap_raw = self._simulate_request_mint(
            request_amount_raw
        )
        if observed_cap_raw is None:
            _, _, observed_cap_raw = self._simulate_request_mint(
                CAP_PROBE_AMOUNT_RAW
            )
        cap_raw = (
            observed_cap_raw
            if observed_cap_raw is not None
            else self.previous_cap_raw
        )
        cap_increased = None
        if observed_cap_raw is not None and self.previous_cap_raw is not None:
            cap_increased = observed_cap_raw > self.previous_cap_raw

        return MintCheckResult(
            checked_at=datetime.now(timezone.utc).isoformat(),
            block_number=block_number,
            can_mint=can_mint,
            reason=reason,
            token_address=self.token_address,
            implementation_address=self.implementation_address,
            simulation_from=self.simulation_from,
            request_amount=str(self.request_amount),
            request_amount_raw=request_amount_raw,
            token_name=token_name,
            token_symbol=token_symbol,
            token_decimals=token_decimals,
            total_supply=str(total_supply) if total_supply is not None else None,
            admin=admin,
            paused=paused,
            explorer_url=f"{ROBINHOOD_EXPLORER_URL}/token/{self.token_address}",
            cap_raw=cap_raw,
            cap_increased=cap_increased,
        )

    def run_once(self) -> MintCheckResult:
        """执行一次检查、保存结果，并在状态变为可 mint 时告警。"""
        result = self.check_mint_availability()
        previous_cap_raw = self.previous_cap_raw
        self._save_result(result)

        if result.cap_increased:
            self.notifier.send(self._format_cap_alert(result, previous_cap_raw))
        if result.can_mint and self.previous_can_mint is not True:
            self.notifier.send(self._format_alert(result))
        self.previous_can_mint = result.can_mint
        if result.cap_raw is not None:
            self.previous_cap_raw = result.cap_raw
        logger.info(
            "NVDA3L mint 状态: %s; reason=%s; cap_raw=%s; cap_increased=%s; block=%s",
            "可用" if result.can_mint else "不可用",
            result.reason,
            result.cap_raw,
            result.cap_increased,
            result.block_number,
        )
        return result

    def start_monitoring(self, interval_seconds: int = 60, once: bool = False) -> None:
        """启动监控循环；默认立即检查后按间隔继续检查。"""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")

        while True:
            try:
                self.run_once()
            except (ContractLogicError, ValueError, Web3Exception):
                logger.exception("NVDA3L mint 检查失败")

            if once:
                return
            time.sleep(interval_seconds)

    def _read_token_state(
        self,
    ) -> tuple[str | None, str | None, int | None, int | None, str | None, bool | None]:
        """读取不会改变状态的 token 元数据。"""
        try:
            name = str(self.token_contract.functions.name().call())
            symbol = str(self.token_contract.functions.symbol().call())
            decimals = int(self.token_contract.functions.decimals().call())
            total_supply = int(self.token_contract.functions.totalSupply().call())
            admin = str(self.token_contract.functions.admin().call())
            paused = bool(self.token_contract.functions.paused().call())
            return name, symbol, decimals, total_supply, admin, paused
        except (ContractLogicError, ValueError, Web3Exception):
            logger.exception("读取 NVDA3L token 状态失败")
            return None, None, None, None, None, None

    def _to_raw_amount(self, decimals: int | None) -> int:
        """按 token decimals 将可读数量转为合约参数。"""
        token_decimals = decimals if decimals is not None else 18
        return int(self.request_amount * (Decimal(10) ** token_decimals))

    def _simulate_request_mint(
        self,
        amount_raw: int,
    ) -> tuple[bool, str, int | None]:
        """用 eth_call 模拟 requestMint，不广播交易。"""
        try:
            self.token_contract.functions.requestMint(
                amount_raw,
                self.simulation_from,
            ).call({"from": self.simulation_from})
            return True, "requestMint(uint256,address) eth_call 成功", None
        except (ContractLogicError, ValueError, Web3Exception) as exc:
            return False, self._format_rpc_error(exc), self._extract_cap_raw(exc)

    def _load_previous_cap(self) -> int | None:
        """从上一次状态文件恢复 cap，支持监控进程重启后继续比较。"""
        try:
            payload = json.loads(self.output_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

        value = payload.get("cap_raw") if isinstance(payload, dict) else None
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value >= 0:
            return value
        return None

    def _save_result(self, result: MintCheckResult) -> None:
        """把最新状态保存为可复核 JSON。"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _format_alert(self, result: MintCheckResult) -> str:
        """格式化状态变化告警。"""
        return (
            "🚨 NVDA3L 当前可以 mint\n"
            f"区块: {result.block_number}\n"
            f"模拟数量: {result.request_amount} {result.token_symbol or 'NVDA3L'}\n"
            f"模拟地址: {result.simulation_from}\n"
            f"合约: {result.token_address}\n"
            f"Blockscout: {result.explorer_url}"
        )

    @staticmethod
    def _format_cap_alert(
        result: MintCheckResult,
        previous_cap_raw: int | None,
    ) -> str:
        """格式化 cap 增加告警。"""
        return (
            "📈 NVDA3L mint cap 增加\n"
            f"旧 cap_raw: {previous_cap_raw}\n"
            f"新 cap_raw: {result.cap_raw}\n"
            f"区块: {result.block_number}\n"
            f"合约: {result.token_address}\n"
            f"Blockscout: {result.explorer_url}"
        )

    @staticmethod
    def _extract_cap_raw(
        exc: ContractLogicError | ValueError | Web3Exception,
    ) -> int | None:
        """从 cap 超限自定义错误中提取第二个 uint256 参数。"""
        match = re.search(
            rf"0x{CAP_ERROR_SELECTOR}([0-9a-fA-F]{{128}})",
            str(exc),
        )
        if match is None:
            return None
        return int(match.group(1)[64:128], 16)

    @staticmethod
    def _format_rpc_error(exc: ContractLogicError | ValueError | Web3Exception) -> str:
        """提取短错误原因，避免把完整 RPC 响应刷入日志。"""
        message = str(exc).strip().replace("\n", " ")
        lowered = message.lower()
        if lowered.startswith(f"0x{CAP_ERROR_SELECTOR}"):
            return "requestMint 被 cap 限制（custom error 0x12a216f4）"
        if lowered.startswith("0x13be252b"):
            return "requestMint 被合约拒绝（custom error 0x13be252b）"
        return message[:300] if message else type(exc).__name__


def _parse_decimal(value: str) -> Decimal:
    """解析 CLI 数量参数。"""
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("数量必须是合法数字") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("数量必须大于 0")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="监控 Robinhood Chain NVDA3L 是否可以 mint")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=int(os.getenv("NVDA3L_MONITOR_INTERVAL_SECONDS", "60")),
        help="检查间隔，默认 60 秒",
    )
    parser.add_argument(
        "--request-amount",
        type=_parse_decimal,
        default=_parse_decimal(os.getenv("NVDA3L_MINT_PROBE_AMOUNT", "1")),
        help="模拟 mint 的 token 数量，默认 1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("NVDA3L_MINT_STATUS_FILE", str(DEFAULT_OUTPUT_PATH))),
        help="最新状态 JSON 路径",
    )
    parser.add_argument("--once", action="store_true", help="只检查一次后退出")
    args = parser.parse_args(argv)

    monitor = Nvda3lMintMonitor(
        request_amount=args.request_amount,
        output_path=args.output,
    )
    monitor.start_monitoring(
        interval_seconds=args.interval_seconds,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
