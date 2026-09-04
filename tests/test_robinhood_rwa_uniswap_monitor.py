#!/usr/bin/env python3
"""Robinhood RWA/Uniswap 监控器纯函数测试。"""

import os
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tests._path_setup import ensure_src_path

ensure_src_path()

from analysis.robinhood_rwa_uniswap_monitor import (
    _decode_swap_log,
    annualize_yield_percent,
    calculate_virtual_reserves,
    calculate_yield_percent,
    select_latest_assets,
    RobinhoodRwaUniswapMonitor,
    RwaAsset,
    WindowRanking,
)
from analysis.uniswap_v4_fee_analyzer import PoolMetadata
from core.rpc_pool import mask_rpc_url, parse_rpc_urls
from core.supabase_repository import SupabaseConfig, SupabaseRepository
from core.supabase_repository import load_supabase_config


class TestRobinhoodRwaUniswapMonitor(unittest.TestCase):
    def test_select_latest_assets_uses_registry_order(self) -> None:
        assets = [
            RwaAsset("NEW", "New", "0x0000000000000000000000000000000000000001", None, 18, "ACTIVE", "", "", True, 0),
            RwaAsset("OLD", "Old", "0x0000000000000000000000000000000000000002", None, 18, "ACTIVE", "", "", True, 1),
        ]
        self.assertEqual([asset.token_symbol for asset in select_latest_assets(assets, 1)], ["NEW"])

    def test_window_ranking_exposes_pool_address_column(self) -> None:
        self.assertIn("pool_address", WindowRanking.__dataclass_fields__)

    def test_database_ranking_rows_keep_pool_address(self) -> None:
        rows = RobinhoodRwaUniswapMonitor._database_ranking_rows(
            [
                {
                    "window_hours": 24,
                    "pool_id": "0x" + "11" * 32,
                    "pool_address": "0x" + "11" * 32,
                    "pool_pair": "CIEN/USDG",
                    "swap_count": 3,
                    "pool_size_usd_proxy": "100.25",
                    "window_yield_percent": "1.5",
                    "annualized_yield_percent": "547.5",
                }
            ]
        )
        self.assertEqual(rows[0]["pool_address"], "0x" + "11" * 32)
        self.assertEqual(rows[0]["active_liquidity_usd_proxy"], "100.25")

    def test_pool_row_normalizes_dynamic_initialize_fee(self) -> None:
        pool = PoolMetadata(
            pool_id="0x" + "11" * 32,
            currency0="0x" + "22" * 20,
            currency1="0x" + "33" * 20,
            fee_pips=0x800000,
            tick_spacing=8,
            hooks="0x" + "44" * 20,
            initialize_block=100,
        )

        row = RobinhoodRwaUniswapMonitor._pool_row(pool, {})

        self.assertEqual(row["fee_pips"], 0)

    def test_dashboard_view_migration_exposes_frontend_fields(self) -> None:
        migration_path = Path(__file__).parents[1] / "supabase" / "migrations" / "20260904000001_create_rh_pool_dashboard_view.sql"
        migration = migration_path.read_text(encoding="utf-8")

        self.assertIn("create or replace view public.rh_pool_dashboard", migration.lower())
        for field in (
            "tvl_usd",
            "volume_24h_usd",
            "fee_apr",
            "current_apr",
            "apr_2h",
            "rank_2h",
            "rank_24h",
            "metric_time",
            "sync_time",
        ):
            self.assertIn(f" as {field}", migration.lower())
        self.assertIn("nullif(e.fee_pips, 0)", migration.lower())

    def test_supabase_upsert_uses_rh_table_and_idempotent_conflict(self) -> None:
        session = Mock()
        response = Mock()
        response.content = b""
        session.request.return_value = response
        repository = SupabaseRepository(
            SupabaseConfig("https://example.supabase.co", "service-role-secret"),
            session=session,
        )

        repository.upsert_assets(
            [{
                "chain_id": 4663,
                "token_address": "0x" + "11" * 20,
                "token_symbol": "TEST",
            }]
        )

        request_args = session.request.call_args.args
        request = session.request.call_args.kwargs
        self.assertEqual(request_args[1], "https://example.supabase.co/rest/v1/rh_rwa_assets")
        self.assertEqual(request["params"], {"on_conflict": "chain_id,token_address"})
        self.assertIn("resolution=merge-duplicates", request["headers"]["Prefer"])

    def test_supabase_fetch_rejects_unsupported_window(self) -> None:
        repository = SupabaseRepository(SupabaseConfig("https://example.supabase.co", "key"))
        with self.assertRaises(ValueError):
            repository.fetch_window_rankings(4663, "latest20", 3)

    def test_supabase_config_accepts_secret_key_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co/rest/v1/",
                "SUPABASE_SERVICE_ROLE_KEY": "",
                "SUPABASE_SECRET_KEY": "secret-key",
            },
            clear=False,
        ):
            config = load_supabase_config()

        self.assertIsNotNone(config)
        self.assertEqual(config.url, "https://example.supabase.co")
        self.assertEqual(config.service_role_key, "secret-key")

    def test_sync_pools_backfills_only_new_asset_then_scans_incrementally(self) -> None:
        old_address = "0x" + "11" * 20
        new_address = "0x" + "22" * 20
        pool = PoolMetadata(
            pool_id="0x" + "33" * 32,
            currency0=new_address,
            currency1="0x" + "44" * 20,
            fee_pips=3000,
            tick_spacing=60,
            hooks="0x" + "55" * 20,
            initialize_block=150,
        )
        with TemporaryDirectory() as directory:
            cache_path = Path(directory) / "pools.json"
            cache_path.write_text(
                '{"last_scanned_block":100,"asset_addresses":["%s"],"pools":[]}' % old_address,
                encoding="utf-8",
            )
            monitor = RobinhoodRwaUniswapMonitor(
                assets_path=Path(directory) / "assets.json",
                pool_cache_path=cache_path,
                pool_start_block=0,
            )
            assets = [
                RwaAsset("OLD", "Old", old_address, None, 18, "ACTIVE", "", "", True, 0),
                RwaAsset("NEW", "New", new_address, None, 18, "ACTIVE", "", "", True, 1),
            ]
            with patch.object(
                monitor,
                "_discover_rwa_pools",
                side_effect=[{pool.pool_id: pool}, {pool.pool_id: pool}],
            ) as discover:
                monitor.sync_pools(assets, 200, [assets[1]])

            self.assertEqual(
                [call.args for call in discover.call_args_list],
                [(0, 100, {new_address}), (101, 200, {new_address})],
            )

    def test_decode_swap_log(self) -> None:
        amount0 = (2**256 - 123).to_bytes(32, "big").hex()
        amount1 = (456).to_bytes(32, "big").hex()
        data = "0x" + amount0 + amount1 + (1).to_bytes(32, "big").hex() + (2).to_bytes(32, "big").hex() + (3).to_bytes(32, "big").hex() + (3000).to_bytes(32, "big").hex()
        record = _decode_swap_log(
            {
                "transactionHash": "0x" + "11" * 32,
                "blockNumber": 10,
                "transactionIndex": 2,
                "logIndex": 4,
                "topics": ["0x" + "00" * 32, "0x" + "22" * 32, "0x" + "00" * 12 + "33" * 20],
                "data": data,
            }
        )
        self.assertEqual(record.amount0, -123)
        self.assertEqual(record.amount1, 456)
        self.assertEqual(record.fee_pips, 3000)
        self.assertEqual(record.sqrt_price_x96, 1)
        self.assertEqual(record.active_liquidity, 2)

    def test_parse_rpc_urls_and_mask_secrets(self) -> None:
        self.assertEqual(
            parse_rpc_urls("https://one.example, https://two.example"),
            ("https://one.example", "https://two.example"),
        )
        self.assertEqual(
            mask_rpc_url("https://robinhood-mainnet.g.alchemy.com/v2/secret"),
            "https://robinhood-mainnet.g.alchemy.com/v2/***",
        )

    def test_parse_rpc_urls_reads_provider_specific_environment_variables(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ALCHEMY_RPC_URL": "https://alchemy.example/v2/key",
                "TATUM_RPC_URL": "https://tatum.example",
            },
            clear=True,
        ):
            self.assertEqual(
                parse_rpc_urls(),
                (
                    "https://alchemy.example/v2/key",
                    "https://tatum.example",
                    "https://rpc.mainnet.chain.robinhood.com",
                ),
            )

    def test_calculate_yield_percent(self) -> None:
        self.assertEqual(calculate_yield_percent(Decimal("2"), Decimal("100")), 2.0)
        self.assertIsNone(calculate_yield_percent(Decimal("2"), None))

    def test_annualize_yield_percent(self) -> None:
        self.assertEqual(annualize_yield_percent(2.0, 2), 8760.0)
        self.assertIsNone(annualize_yield_percent(None, 2))

    def test_calculate_virtual_reserves_at_q96(self) -> None:
        self.assertEqual(calculate_virtual_reserves(100, 2**96), (100, 100))

    def test_calculate_virtual_reserves_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            calculate_virtual_reserves(100, 0)


if __name__ == "__main__":
    unittest.main()
