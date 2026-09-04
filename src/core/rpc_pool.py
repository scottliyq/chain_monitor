"""Robinhood Chain RPC 节点探测与轮询。"""

import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

import requests
from web3.providers import HTTPProvider


ROBINHOOD_CHAIN_ID = 4663
DEFAULT_ROBINHOOD_RPC = "https://rpc.mainnet.chain.robinhood.com"
RPC_ENV_NAMES = (
    "ROBINHOOD_RPC_URLS",
    "RH_RPC_URLS",
    "ALCHEMY_RPC_URL",
    "TATUM_RPC_URL",
    "ROBINHOOD_RPC_URL",
    "RH_RPC_URL",
)
RETRYABLE_ERROR_WORDS = (
    "429",
    "rate limit",
    "rate-limit",
    "too many",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "service unavailable",
    "gateway",
    "response too large",
    "logs matched",
)


@dataclass(frozen=True)
class RpcHealth:
    """一个 RPC 节点的探测结果。"""

    endpoint: str
    ok: bool
    chain_id: int | None
    latest_block: int | None
    latency_ms: float | None
    error: str | None
    checked_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> str:
    """返回 ISO-8601 UTC 时间。"""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def mask_rpc_url(url: str) -> str:
    """隐藏 URL 中的 API key/token，避免写入日志或报告。"""

    parts = urlsplit(url)
    path = re.sub(r"/(v2|v1)/[^/]+", r"/\1/***", parts.path)
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def parse_rpc_urls(explicit_url: str | None = None) -> tuple[str, ...]:
    """解析 CLI 或环境变量中的逗号/换行分隔 RPC 地址并去重。"""

    if explicit_url:
        values = [
            part.strip()
            for part in re.split(r"[,\n]", explicit_url)
            if part.strip()
        ]
        return tuple(dict.fromkeys(values))

    values: list[str] = []
    candidates = [os.getenv(name) for name in RPC_ENV_NAMES]
    for candidate in candidates:
        if not candidate:
            continue
        values.extend(part.strip() for part in re.split(r"[,\n]", candidate) if part.strip())
    values.append(DEFAULT_ROBINHOOD_RPC)
    return tuple(dict.fromkeys(values))


def _is_retryable_response(response: object) -> bool:
    """判断 JSON-RPC 错误是否适合切换节点。"""

    if not isinstance(response, Mapping):
        return False
    error = response.get("error")
    if not isinstance(error, Mapping):
        return False
    code = error.get("code")
    if code == 429 or code in (-32005, -32016):
        return True
    return any(word in str(error).lower() for word in RETRYABLE_ERROR_WORDS)


def _is_retryable_error(error: BaseException) -> bool:
    """判断 HTTP/解码异常是否适合切换节点。"""

    return any(word in str(error).lower() for word in RETRYABLE_ERROR_WORDS)


class RotatingHTTPProvider(HTTPProvider):
    """按请求轮询 RPC，遇到限流或临时故障时切换节点。"""

    def __init__(
        self,
        endpoints: Iterable[str],
        request_timeout_seconds: int = 30,
        cooldown_seconds: int = 30,
        max_attempts: int = 0,
    ) -> None:
        normalized = tuple(dict.fromkeys(endpoint.strip() for endpoint in endpoints if endpoint.strip()))
        if not normalized:
            raise ValueError("至少需要一个 RPC endpoint")
        if request_timeout_seconds <= 0 or cooldown_seconds < 0:
            raise ValueError("RPC timeout/cooldown 参数无效")
        super().__init__(
            endpoint_uri=normalized[0],
            request_kwargs={"timeout": request_timeout_seconds},
        )
        self.endpoints = normalized
        self.cooldown_seconds = cooldown_seconds
        self.max_attempts = max_attempts or len(normalized)
        self._next_index = 0
        self._cooldown_until: dict[str, float] = {}
        self._providers = tuple(
            HTTPProvider(
                endpoint_uri=endpoint,
                request_kwargs={"timeout": request_timeout_seconds},
            )
            for endpoint in normalized
        )

    @property
    def display_endpoints(self) -> tuple[str, ...]:
        """返回脱敏后的节点地址。"""

        return tuple(mask_rpc_url(endpoint) for endpoint in self.endpoints)

    def _candidate_indices(self) -> list[int]:
        now = time.monotonic()
        candidates = [
            (self._next_index + offset) % len(self.endpoints)
            for offset in range(len(self.endpoints))
            if self._cooldown_until.get(
                self.endpoints[(self._next_index + offset) % len(self.endpoints)], 0
            )
            <= now
        ]
        return candidates or [self._next_index]

    def make_request(self, method: Any, params: Any) -> Any:
        """轮询发起 JSON-RPC 请求；所有节点失败时返回最后一个响应/异常。"""

        last_error: BaseException | None = None
        last_response: Any = None
        attempted = 0
        for index in self._candidate_indices():
            if attempted >= self.max_attempts:
                break
            attempted += 1
            endpoint = self.endpoints[index]
            try:
                response = self._providers[index].make_request(method, params)
                if _is_retryable_response(response):
                    last_response = response
                    self._cooldown_until[endpoint] = time.monotonic() + self.cooldown_seconds
                    continue
                self._next_index = (index + 1) % len(self.endpoints)
                return response
            except requests.RequestException as error:
                last_error = error
                self._cooldown_until[endpoint] = time.monotonic() + self.cooldown_seconds
            except ValueError as error:
                if not _is_retryable_error(error):
                    raise
                last_error = error
                self._cooldown_until[endpoint] = time.monotonic() + self.cooldown_seconds
        if last_response is not None:
            return last_response
        if last_error is not None:
            raise last_error
        raise RuntimeError("没有可用的 RPC endpoint")


def _rpc_result(response: object, field: str) -> object:
    """提取 JSON-RPC 成功响应字段。"""

    if not isinstance(response, Mapping) or "error" in response or field not in response:
        raise ValueError("RPC 返回错误响应")
    return response[field]


def check_rpc_endpoints(
    endpoints: Iterable[str],
    request_timeout_seconds: int = 10,
) -> list[RpcHealth]:
    """探测 chain id 与 latest block，并返回脱敏节点结果。"""

    results: list[RpcHealth] = []
    for endpoint in dict.fromkeys(endpoints):
        started = time.perf_counter()
        chain_id: int | None = None
        latest_block: int | None = None
        error_message: str | None = None
        try:
            provider = HTTPProvider(
                endpoint_uri=endpoint,
                request_kwargs={"timeout": request_timeout_seconds},
            )
            chain_id_value = _rpc_result(provider.make_request("eth_chainId", []), "result")
            block_value = _rpc_result(provider.make_request("eth_blockNumber", []), "result")
            chain_id = int(str(chain_id_value), 16)
            latest_block = int(str(block_value), 16)
            if chain_id != ROBINHOOD_CHAIN_ID:
                raise ValueError(f"chain_id={chain_id}，不是 Robinhood Chain 4663")
        except (requests.RequestException, ValueError, TypeError):
            error_message = "RPC 请求失败或 chain_id 不匹配"
        results.append(
            RpcHealth(
                endpoint=mask_rpc_url(endpoint),
                ok=error_message is None,
                chain_id=chain_id,
                latest_block=latest_block,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                error=error_message,
                checked_at=_utc_now(),
            )
        )
    return results
