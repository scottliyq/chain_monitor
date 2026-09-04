"""Supabase PostgREST repository for Robinhood RWA monitoring data."""

import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import requests


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_SECRET_KEY_ENV = "SUPABASE_SECRET_KEY"
DEFAULT_BATCH_SIZE = 500
SUPABASE_REST_PATH = "/rest/v1"


class SupabaseRepositoryError(RuntimeError):
    """Supabase 请求失败，消息不包含请求密钥或响应正文。"""


@dataclass(frozen=True)
class SupabaseConfig:
    """连接 Supabase REST API 所需的配置。"""

    url: str
    service_role_key: str
    timeout_seconds: int = 30


def load_supabase_config() -> SupabaseConfig | None:
    """从环境变量加载 Supabase 配置；未完整配置时返回 None。"""

    url = os.getenv(SUPABASE_URL_ENV, "").strip().rstrip("/")
    if url.endswith(SUPABASE_REST_PATH):
        url = url[: -len(SUPABASE_REST_PATH)].rstrip("/")
    key = os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV, "").strip()
    if not key:
        key = os.getenv(SUPABASE_SECRET_KEY_ENV, "").strip()
    if not url and not key:
        return None
    if not url or not key:
        raise ValueError(
            f"Supabase 配置必须同时设置 {SUPABASE_URL_ENV} 和 {SUPABASE_SERVICE_ROLE_KEY_ENV} 或 {SUPABASE_SECRET_KEY_ENV}"
        )
    return SupabaseConfig(url=url, service_role_key=key)


class SupabaseRepository:
    """通过批量 PostgREST 请求写入或读取 Robinhood 监控数据。"""

    def __init__(
        self,
        config: SupabaseConfig,
        session: requests.Session | None = None,
    ) -> None:
        if not config.url or not config.service_role_key:
            raise ValueError("Supabase URL 和 service role key 不能为空")
        if config.timeout_seconds <= 0:
            raise ValueError("Supabase timeout 必须大于 0")
        self.config = config
        self.session = session or requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: object | None = None,
        params: Mapping[str, str] | None = None,
        prefer: str | None = None,
    ) -> object:
        headers = {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.session.request(
                method,
                f"{self.config.url}/rest/v1/{path.lstrip('/')}",
                headers=headers,
                json=payload,
                params=params,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else "unknown"
            raise SupabaseRepositoryError(f"Supabase 请求失败: {method} {path}, HTTP {status}") from error
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise SupabaseRepositoryError(f"Supabase 返回不是有效 JSON: {method} {path}") from error

    def _upsert_rows(
        self,
        table: str,
        rows: Iterable[Mapping[str, object]],
        conflict_columns: Sequence[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("Supabase batch_size 必须大于 0")
        batch: list[dict[str, object]] = []
        for row in rows:
            batch.append(dict(row))
            if len(batch) >= batch_size:
                self._request(
                    "POST",
                    table,
                    payload=batch,
                    params={"on_conflict": ",".join(conflict_columns)},
                    prefer="resolution=merge-duplicates,return=minimal",
                )
                batch.clear()
        if batch:
            self._request(
                "POST",
                table,
                payload=batch,
                params={"on_conflict": ",".join(conflict_columns)},
                prefer="resolution=merge-duplicates,return=minimal",
            )

    def upsert_assets(self, rows: Iterable[Mapping[str, object]]) -> None:
        """批量更新官方 RWA 资产。"""

        self._upsert_rows("rh_rwa_assets", rows, ("chain_id", "token_address"))

    def upsert_pools(self, rows: Iterable[Mapping[str, object]]) -> None:
        """批量更新 Uniswap v4 池元数据。"""

        self._upsert_rows("rh_uniswap_v4_pools", rows, ("chain_id", "pool_id"))

    def upsert_swap_events(self, rows: Iterable[Mapping[str, object]]) -> None:
        """批量写入 Swap 事件，并按交易哈希和日志索引幂等去重。"""

        self._upsert_rows(
            "rh_uniswap_v4_swap_events",
            rows,
            ("chain_id", "tx_hash", "log_index"),
        )

    def upsert_hourly_metrics(self, rows: Iterable[Mapping[str, object]]) -> None:
        """批量更新池小时指标。"""

        self._upsert_rows(
            "rh_pool_hourly_metrics",
            rows,
            ("chain_id", "asset_scope", "pool_id", "bucket_start"),
        )

    def get_checkpoint(self, sync_name: str = "rwa_uniswap_v4") -> dict[str, object] | None:
        """读取增量扫描 checkpoint。"""

        result = self._request(
            "GET",
            "rh_sync_checkpoints",
            params={"sync_name": f"eq.{sync_name}", "limit": "1"},
        )
        if not isinstance(result, list) or not result:
            return None
        row = result[0]
        return dict(row) if isinstance(row, dict) else None

    def ingest_hourly_batch(
        self,
        chain_id: int,
        asset_scope: str,
        pool_ids: Sequence[str],
        last_initialize_block: int,
        last_swap_block: int,
    ) -> None:
        """刷新受影响窗口并在数据库中提交成功 checkpoint。"""

        self._request(
            "POST",
            "rpc/rh_ingest_hourly_batch",
            payload={
                "p_chain_id": chain_id,
                "p_asset_scope": asset_scope,
                "p_pool_ids": list(pool_ids),
                "p_last_initialize_block": last_initialize_block,
                "p_last_swap_block": last_swap_block,
            },
            prefer="return=minimal",
        )

    def fetch_window_rankings(
        self,
        chain_id: int,
        asset_scope: str,
        window_hours: int,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """读取前端同口径的窗口收益率排名。"""

        if window_hours not in (2, 4, 24):
            raise ValueError("window_hours 必须是 2、4 或 24")
        if limit <= 0:
            raise ValueError("ranking limit 必须大于 0")
        result = self._request(
            "GET",
            "rh_pool_window_rankings",
            params={
                "chain_id": f"eq.{chain_id}",
                "asset_scope": f"eq.{asset_scope}",
                "window_hours": f"eq.{window_hours}",
                "is_public": "eq.true",
                "order": "annualized_yield_percent.desc.nullslast",
                "limit": str(limit),
            },
        )
        if not isinstance(result, list):
            raise SupabaseRepositoryError("Supabase 排名响应格式无效")
        return [dict(row) for row in result if isinstance(row, dict)]

    def cleanup_expired_data(self) -> None:
        """清理超过默认 7 天保留期的数据。"""

        self._request("POST", "rpc/rh_cleanup_expired_data", payload={}, prefer="return=minimal")
