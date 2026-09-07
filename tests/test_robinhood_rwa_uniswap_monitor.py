#!/usr/bin/env python3
"""Robinhood RWA/Uniswap 监控器纯函数测试。"""

import argparse
import json
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

import requests

from tests._path_setup import ensure_src_path

ensure_src_path()

from analysis.robinhood_rwa_uniswap_monitor import (
    _decode_swap_log,
    annualize_yield_percent,
    calculate_virtual_reserves,
    calculate_yield_percent,
    build_monitoring_asset_selection,
    is_new_issue,
    main as monitor_main,
    RwaAssetRegistry,
    RobinhoodRwaUniswapMonitor,
    RwaAsset,
    WindowRanking,
)
from analysis.uniswap_v4_fee_analyzer import PoolMetadata
from core.rpc_pool import RotatingHTTPProvider, mask_rpc_url, parse_rpc_urls
from core.supabase_repository import SupabaseConfig, SupabaseRepository, SupabaseRepositoryError
from core.supabase_repository import load_supabase_config


class TestRobinhoodRwaUniswapMonitor(unittest.TestCase):
    def test_periodic_worker_continues_after_retryable_scan_failure(self) -> None:
        args = argparse.Namespace(
            interval_minutes=1,
            supabase_publish=False,
            rpc_check_only=False,
            rpc_url="https://rpc.example",
            rpc_health_output=Path("rpc-health.json"),
            assets_output=Path("assets.json"),
            pool_cache=Path("pools.json"),
            output=Path("report.json"),
            csv_output=Path("report.csv"),
            pool_start_block=0,
            chunk_size=1_000_000,
            native_price_usd=None,
            all_rwa_pairs=False,
        )
        monitor = Mock()
        monitor.run_once.side_effect = [
            requests.HTTPError("temporary RPC failure"),
            {"active_asset_count": 1, "rwa_pool_count": 1},
        ]
        with patch("analysis.robinhood_rwa_uniswap_monitor.load_dotenv"), patch(
            "analysis.robinhood_rwa_uniswap_monitor._parse_args", return_value=args
        ), patch(
            "analysis.robinhood_rwa_uniswap_monitor.RobinhoodRwaUniswapMonitor",
            return_value=monitor,
        ), patch(
            "analysis.robinhood_rwa_uniswap_monitor.time.sleep",
            side_effect=[None, StopIteration],
        ) as sleep:
            with self.assertRaises(StopIteration):
                monitor_main()

        self.assertEqual(monitor.run_once.call_count, 2)
        self.assertEqual(sleep.call_count, 2)

    def test_new_issue_marker_is_true_for_first_24_hours_only(self) -> None:
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

        self.assertTrue(is_new_issue("2026-09-03T12:00:00+00:00", now))
        self.assertFalse(is_new_issue("2026-09-03T11:59:59+00:00", now))

    def test_registry_persists_full_snapshot_and_discovery_time(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "assets": [
                {
                    "tokenSymbol": "NEW",
                    "tokenName": "New",
                    "tokenDecimals": 18,
                    "currentMultiplier": "1.010000000000000000",
                    "status": "ASSET_STATUS_ACTIVE",
                    "isin": "NEW-ISIN",
                    "deployments": [{"chainId": 4663, "contractAddress": "0x" + "11" * 20}],
                },
                {
                    "tokenSymbol": "OLD",
                    "tokenName": "Old",
                    "tokenDecimals": 18,
                    "status": "ASSET_STATUS_ACTIVE",
                    "deployments": [{"chainId": 4663, "contractAddress": "0x" + "22" * 20}],
                },
            ]
        }
        session.get.return_value = response

        with TemporaryDirectory() as directory:
            assets_path = Path(directory) / "assets.json"
            registry = RwaAssetRegistry(output_path=assets_path, session=session)
            with patch(
                "analysis.robinhood_rwa_uniswap_monitor._utc_now",
                return_value="2026-09-04T12:00:00+00:00",
            ):
                assets = registry.sync()

            self.assertEqual([asset.token_symbol for asset in assets], ["NEW", "OLD"])
            self.assertTrue(all(asset.is_new_issue for asset in assets))
            snapshot = json.loads(assets_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["active_asset_count"], 2)
            self.assertEqual(snapshot["new_issue_count"], 2)
            self.assertEqual(
                [item["token_symbol"] for item in snapshot["assets"]],
                ["NEW", "OLD"],
            )
            self.assertEqual(snapshot["assets"][0]["first_seen_at"], "2026-09-04T12:00:00+00:00")
            self.assertTrue(snapshot["assets"][0]["is_new_issue"])
            self.assertEqual(snapshot["assets"][0]["current_multiplier"], "1.010000000000000000")
            self.assertIsNone(snapshot["assets"][0]["volume_updated_at"])

    def test_registry_queries_current_multipliers_by_symbol(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "assets": [
                {"tokenSymbol": "NVDA", "currentMultiplier": "1.01"},
                {"tokenSymbol": "AAPL", "currentMultiplier": "1"},
                {"tokenSymbol": "BROKEN", "currentMultiplier": "not-a-number"},
            ]
        }
        session.get.return_value = response

        registry = RwaAssetRegistry(session=session)

        self.assertEqual(
            registry.fetch_multipliers(["nvda", "MISSING"]),
            {"NVDA": Decimal("1.01")},
        )
        session.get.assert_called_once_with(
            "https://api.robinhood.com/rhj/assets",
            timeout=30,
        )

    def test_monitoring_selection_combines_new_assets_and_low_volume_assets(self) -> None:
        assets = [
            RwaAsset("NEW", "New", "0x" + "11" * 20, None, 18, "ACTIVE", "", "", True, 0, daily_trading_volume="100", is_new_asset=True),
            RwaAsset("LOW1", "Low 1", "0x" + "22" * 20, None, 18, "ACTIVE", "", "", True, 1, daily_trading_volume="1"),
            RwaAsset("LOW2", "Low 2", "0x" + "33" * 20, None, 18, "ACTIVE", "", "", True, 2, daily_trading_volume="2"),
            RwaAsset("HIGH", "High", "0x" + "44" * 20, None, 18, "ACTIVE", "", "", True, 3, daily_trading_volume="1000"),
        ]

        selected, new_assets, low_volume_assets = build_monitoring_asset_selection(assets, low_volume_limit=2)

        self.assertEqual([asset.token_symbol for asset in selected], ["NEW", "LOW1", "LOW2"])
        self.assertEqual([asset.token_symbol for asset in new_assets], ["NEW"])
        self.assertEqual([asset.token_symbol for asset in low_volume_assets], ["LOW1", "LOW2"])
        self.assertEqual(selected[0].monitoring_reason, "new_asset")
        self.assertEqual(selected[1].monitoring_reason, "low_volume")

    def test_registry_uses_daily_snapshot_without_repeating_full_api_queries(self) -> None:
        session = Mock()
        assets_response = Mock()
        assets_response.json.return_value = {
            "assets": [
                {
                    "tokenSymbol": "LOW",
                    "tokenName": "Low",
                    "status": "ASSET_STATUS_ACTIVE",
                    "deployments": [{"chainId": 4663, "contractAddress": "0x" + "11" * 20}],
                },
                {
                    "tokenSymbol": "HIGH",
                    "tokenName": "High",
                    "status": "ASSET_STATUS_ACTIVE",
                    "deployments": [{"chainId": 4663, "contractAddress": "0x" + "22" * 20}],
                },
            ]
        }
        low_volume_response = Mock()
        low_volume_response.json.return_value = {"quotes": [{"dailyTradingVolume": "1"}]}
        high_volume_response = Mock()
        high_volume_response.json.return_value = {"quotes": [{"dailyTradingVolume": "100"}]}
        session.get.side_effect = [assets_response, high_volume_response, low_volume_response]

        with TemporaryDirectory() as directory:
            registry = RwaAssetRegistry(
                output_path=Path(directory) / "assets.json",
                session=session,
                low_volume_limit=1,
            )
            with patch(
                "analysis.robinhood_rwa_uniswap_monitor._utc_now",
                side_effect=["2026-09-04T12:00:00+00:00", "2026-09-04T12:10:00+00:00"],
            ):
                first = registry.sync()
                second = registry.sync()

            self.assertEqual(session.get.call_count, 3)
            self.assertEqual([asset.token_symbol for asset in registry.get_monitoring_assets(first)], ["LOW"])
            self.assertEqual([asset.token_symbol for asset in registry.get_monitoring_assets(second)], ["LOW"])

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

    def test_token_prices_apply_current_multiplier(self) -> None:
        asset = RwaAsset(
            "NVDA",
            "NVIDIA",
            "0x" + "11" * 20,
            None,
            18,
            "ASSET_STATUS_ACTIVE",
            "",
            "",
            True,
            current_multiplier="1.01",
        )

        prices = RobinhoodRwaUniswapMonitor._apply_current_multipliers(
            {"NVDA": Decimal("100"), "USDG": Decimal("1")},
            [asset],
        )

        self.assertEqual(prices, {"NVDA": Decimal("101.00"), "USDG": Decimal("1")})

    def test_publish_writes_assets_pools_and_reads_all_windows_from_database(self) -> None:
        supabase = Mock()
        supabase.fetch_window_rankings.return_value = []
        asset = RwaAsset(
            "TEST",
            "Test",
            "0x" + "11" * 20,
            None,
            18,
            "ASSET_STATUS_ACTIVE",
            "",
            "",
            True,
            0,
            is_new_issue=True,
        )
        pool = PoolMetadata(
            pool_id="0x" + "22" * 32,
            currency0=asset.contract_address,
            currency1="0x" + "33" * 20,
            fee_pips=3000,
            tick_spacing=60,
            hooks="0x" + "44" * 20,
            initialize_block=100,
        )
        monitor = RobinhoodRwaUniswapMonitor(
            rpc_url="https://one.example",
            supabase_repository=supabase,
        )

        monitor._publish_to_supabase(
            [asset],
            {pool.pool_id: pool},
            [],
            200,
            1_700_000_000,
            {},
        )

        asset_rows = list(supabase.upsert_assets.call_args.args[0])
        pool_rows = list(supabase.upsert_pools.call_args.args[0])
        self.assertEqual(len(asset_rows), 1)
        self.assertEqual(asset_rows[0]["token_symbol"], "TEST")
        self.assertTrue(asset_rows[0]["is_new_issue"])
        self.assertIsNone(asset_rows[0]["current_multiplier"])
        self.assertEqual(len(pool_rows), 1)
        self.assertEqual(pool_rows[0]["pool_address"], pool.pool_id)
        self.assertEqual(
            supabase.fetch_window_rankings.call_args_list,
            [
                call(4663, "daily_candidates", 2, limit=10_000),
                call(4663, "daily_candidates", 4, limit=10_000),
                call(4663, "daily_candidates", 24, limit=10_000),
            ],
        )

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
        schema = (migration_path.parent / "20260904000000_create_rh_rwa_monitor.sql").read_text(encoding="utf-8")
        upgrade = (migration_path.parent / "20260904000003_add_new_issue_tracking.sql").read_text(encoding="utf-8")

        self.assertIn("create or replace view public.rh_pool_dashboard", migration.lower())
        self.assertIn("is_new_issue boolean", schema.lower())
        self.assertIn("add column if not exists is_new_issue", upgrade.lower())
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
        for field in ("is_new_issue", "new_issue_discovered_at"):
            self.assertIn(f" as {field}", upgrade.lower())

    def test_dashboard_pool_type_migration_exposes_v4_and_volume(self) -> None:
        migration_path = (
            Path(__file__).parents[1]
            / "supabase"
            / "migrations"
            / "20260907000003_add_pool_type_to_dashboard.sql"
        )
        self.assertTrue(migration_path.exists())
        migration = migration_path.read_text(encoding="utf-8").lower()

        self.assertIn("'v4' as pool_type", migration)
        self.assertIn("volume.volume_24h_usd", migration)
        self.assertIn("as volume_24h_usd", migration)

    def test_multiplier_view_is_public_and_preserves_decimal_text(self) -> None:
        migration_path = (
            Path(__file__).parents[1]
            / "supabase"
            / "migrations"
            / "20260907000001_create_rh_asset_multiplier_view.sql"
        )
        migration = migration_path.read_text(encoding="utf-8").lower()

        self.assertIn("create or replace view public.rh_asset_multiplier_dashboard", migration)
        self.assertIn("current_multiplier::text as current_multiplier", migration)
        self.assertIn("grant select on public.rh_asset_multiplier_dashboard to anon, authenticated", migration)

    def test_dashboard_ranking_candidates_include_all_registered_pools(self) -> None:
        migration_path = Path(__file__).parents[1] / "supabase" / "migrations"
        base_migration = (migration_path / "20260904000000_create_rh_rwa_monitor.sql").read_text(encoding="utf-8")
        upgrade_migration = (migration_path / "20260904000004_dashboard_all_pools.sql").read_text(encoding="utf-8")

        for migration in (base_migration, upgrade_migration):
            self.assertIn("from rh_uniswap_v4_pools p", migration.lower())
            self.assertIn("p_pool_ids is null or p.pool_id = any (p_pool_ids)", migration.lower())

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

    def test_supabase_error_includes_safe_response_detail(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 400
        response.text = '{"code":"22007","message":"invalid timestamp"}'
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        session.request.return_value = response
        repository = SupabaseRepository(
            SupabaseConfig("https://example.supabase.co", "service-role-secret"),
            session=session,
        )

        with self.assertRaises(SupabaseRepositoryError) as error:
            repository.upsert_assets(
                [{
                    "chain_id": 4663,
                    "token_address": "0x" + "11" * 20,
                    "token_symbol": "TEST",
                }]
            )

        self.assertIn("invalid timestamp", str(error.exception))
        self.assertNotIn("service-role-secret", str(error.exception))

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
                monitor.sync_pools(assets, 200)

            self.assertEqual(
                [call.args for call in discover.call_args_list],
                [(0, 100, {new_address}), (101, 200, {old_address, new_address})],
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
                "QUICKNODE_RPC_URL": "https://quicknode.example/token",
                "BLOCKDAEMON_RPC_URL": "https://blockdaemon.example",
                "DRPC_RPC_URL": "https://drpc.example",
                "VALIDATION_CLOUD_RPC_URL": "https://validation.example",
                "CHAINSTACK_RPC_URL": "https://chainstack.example",
                "GLOBALSTAKE_RPC_URL": "https://globalstake.example",
            },
            clear=True,
        ):
            self.assertEqual(
                parse_rpc_urls(),
                (
                    "https://alchemy.example/v2/key",
                    "https://tatum.example",
                    "https://quicknode.example/token",
                    "https://blockdaemon.example",
                    "https://drpc.example",
                    "https://validation.example",
                    "https://chainstack.example",
                    "https://globalstake.example",
                    "https://rpc.mainnet.chain.robinhood.com",
                ),
            )

    def test_rpc_request_scope_keeps_block_reads_on_one_endpoint(self) -> None:
        provider = RotatingHTTPProvider(
            ("https://one.example", "https://two.example"),
            cooldown_seconds=0,
        )
        first = Mock()
        second = Mock()
        first.make_request.return_value = {"result": "0x1"}
        second.make_request.return_value = {"result": "0x1"}
        provider._providers = (first, second)

        with provider.request_scope():
            provider.make_request("eth_blockNumber", [])
            provider.make_request("eth_getBlockByNumber", ["0x1", False])

        self.assertEqual(first.make_request.call_count, 2)
        self.assertEqual(second.make_request.call_count, 0)

    def test_rpc_request_scope_fails_over_when_block_is_missing(self) -> None:
        provider = RotatingHTTPProvider(
            ("https://one.example", "https://two.example"),
            cooldown_seconds=0,
        )
        first = Mock()
        second = Mock()
        first.make_request.return_value = {
            "error": {"code": -32000, "message": "block not found"},
        }
        second.make_request.return_value = {"result": "0x1"}
        provider._providers = (first, second)

        with provider.request_scope():
            response = provider.make_request("eth_getBlockByNumber", ["0x1", False])

        self.assertEqual(response, {"result": "0x1"})
        self.assertEqual(first.make_request.call_count, 1)
        self.assertEqual(second.make_request.call_count, 1)

    def test_fetch_prices_retries_transient_http_error(self) -> None:
        session = Mock()
        unavailable = Mock(status_code=503)
        unavailable.raise_for_status.side_effect = requests.HTTPError(response=unavailable)
        available = Mock(status_code=200)
        available.json.return_value = {"quotes": [{"bid": "100", "ask": "102"}]}
        session.get.side_effect = [unavailable, available]
        registry = RwaAssetRegistry(session=session)

        with patch("analysis.robinhood_rwa_uniswap_monitor.time.sleep") as sleep:
            prices = registry.fetch_prices(["AVGO"])

        self.assertEqual(prices, {"AVGO": Decimal("101")})
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(1)

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
