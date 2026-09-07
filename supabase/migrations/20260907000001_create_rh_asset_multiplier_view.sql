-- Public, read-only asset view for frontend multiplier display.

create or replace view public.rh_asset_multiplier_dashboard as
select
    chain_id,
    token_address,
    token_symbol,
    token_name,
    current_multiplier::text as current_multiplier,
    updated_at
from public.rh_rwa_assets
where active = true;

revoke all on public.rh_asset_multiplier_dashboard from anon, authenticated;
grant select on public.rh_asset_multiplier_dashboard to anon, authenticated;
