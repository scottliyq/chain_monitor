-- Expose the current pool protocol and 24-hour volume to the frontend list.
-- The current registry contains Uniswap v4 pools only; pool_type is appended
-- to preserve the existing rh_pool_dashboard column order.

create or replace view public.rh_pool_dashboard as
with ranking_2h as (
    select
        r.*,
        row_number() over (
            partition by r.chain_id, r.asset_scope
            order by r.annualized_yield_percent desc nulls last, r.pool_id
        )::integer as rank_2h
    from public.rh_pool_window_rankings r
    where r.window_hours = 2
),
ranking_24h as (
    select
        r.*,
        row_number() over (
            partition by r.chain_id, r.asset_scope
            order by r.annualized_yield_percent desc nulls last, r.pool_id
        )::integer as rank_24h
    from public.rh_pool_window_rankings r
    where r.window_hours = 24
),
scopes as (
    select distinct chain_id, asset_scope
    from ranking_2h
)
select
    p.chain_id,
    s.asset_scope,
    p.pool_id,
    p.rwa_symbols as token,
    p.pool_address,
    p.token0_symbol || '/' || p.token1_symbol as pool,
    coalesce(r24.pool_size_usd_proxy, r2.pool_size_usd_proxy) as tvl_usd,
    volume.volume_24h_usd,
    r24.annualized_yield_percent as fee_apr,
    r2.annualized_yield_percent as current_apr,
    r2.annualized_yield_percent as apr_2h,
    r2.rank_2h,
    r24.rank_24h,
    coalesce(r24.computed_at, r2.computed_at) as metric_time,
    c.last_success_at as sync_time,
    r2.swap_count as swap_count_2h,
    r24.swap_count as swap_count_24h,
    r2.fee_income_usd as fee_income_2h_usd,
    r24.fee_income_usd as fee_income_24h_usd,
    r2.window_yield_percent as yield_2h_percent,
    r24.window_yield_percent as yield_24h_percent,
    r2.data_quality as data_quality_2h,
    r24.data_quality as data_quality_24h,
    coalesce(r24.computed_at, r2.computed_at) as computed_at,
    coalesce(issue.is_new_issue, false) as is_new_issue,
    issue.new_issue_discovered_at as new_issue_discovered_at,
    'v4' as pool_type
from ranking_2h r2
join scopes s
  on s.chain_id = r2.chain_id
 and s.asset_scope = r2.asset_scope
join public.rh_uniswap_v4_pools p
  on p.chain_id = r2.chain_id
 and p.pool_id = r2.pool_id
left join ranking_24h r24
  on r24.chain_id = r2.chain_id
 and r24.asset_scope = r2.asset_scope
 and r24.pool_id = r2.pool_id
left join public.rh_sync_checkpoints c
  on c.sync_name = 'rwa_uniswap_v4'
 and c.chain_id = r2.chain_id
 and c.asset_scope = r2.asset_scope
left join lateral (
    select
        bool_or(a.is_new_issue) as is_new_issue,
        min(a.first_seen_at) filter (where a.is_new_issue) as new_issue_discovered_at
    from public.rh_rwa_assets a
    where a.chain_id = p.chain_id
      and a.active
      and a.token_address in (p.currency0, p.currency1)
) issue on true
left join lateral (
    select case
        when count(*) = 0 then 0::numeric
        when count(*) filter (
            where e.fee_income_usd is null or e.fee_pips <= 0
        ) > 0 then null::numeric
        else sum(
            e.fee_income_usd
            * (1000000::numeric + e.fee_pips)
            / nullif(e.fee_pips, 0)
        )
    end as volume_24h_usd
    from public.rh_uniswap_v4_swap_events e
    where e.chain_id = r2.chain_id
      and e.pool_id = r2.pool_id
      and e.block_timestamp >= now() - interval '24 hours'
) volume on true;

revoke all on public.rh_pool_dashboard from public;
grant select on public.rh_pool_dashboard to anon, authenticated;
