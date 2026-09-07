-- Persist the daily candidate selection used by the Robinhood worker.

alter table public.rh_rwa_assets
    add column if not exists daily_trading_volume numeric(78, 18),
    add column if not exists volume_updated_at timestamptz,
    add column if not exists is_new_asset boolean not null default false,
    add column if not exists monitoring_selected boolean not null default false,
    add column if not exists monitoring_reason text,
    add column if not exists monitoring_rank integer;

create index if not exists rh_rwa_assets_monitoring_selection_idx
    on public.rh_rwa_assets (chain_id, monitoring_selected, monitoring_rank);

create index if not exists rh_rwa_assets_daily_volume_idx
    on public.rh_rwa_assets (chain_id, daily_trading_volume);
