-- Include every discovered RWA pool in rankings/dashboard, even when it has no recent Swap.

create or replace function public.rh_refresh_window_rankings(
    p_chain_id integer,
    p_asset_scope text,
    p_pool_ids text[] default null
)
returns void
language sql
security definer
set search_path = public
as $$
with params as (
    select date_trunc('hour', now()) as current_hour
),
windows(window_hours) as (
    values (2::smallint), (4::smallint), (24::smallint)
),
candidates as (
    select p.pool_id
    from rh_uniswap_v4_pools p
    where p.chain_id = p_chain_id
      and (p_pool_ids is null or p.pool_id = any (p_pool_ids))
),
aggregates as (
    select
        c.pool_id,
        w.window_hours,
        params.current_hour - make_interval(hours => w.window_hours - 1) as window_start,
        now() as window_end,
        coalesce(sum(h.swap_count), 0)::integer as swap_count,
        case
            when count(h.pool_id) = 0 then null
            when count(*) filter (where h.fee_income_usd is null) > 0 then null
            else sum(h.fee_income_usd)
        end as fee_income_usd
    from candidates c
    cross join windows w
    cross join params
    left join rh_pool_hourly_metrics h
        on h.chain_id = p_chain_id
       and h.asset_scope = p_asset_scope
       and h.pool_id = c.pool_id
       and h.bucket_start >= params.current_hour - make_interval(hours => w.window_hours - 1)
       and h.bucket_start <= params.current_hour
    group by c.pool_id, w.window_hours, params.current_hour
),
latest_state as (
    select distinct on (h.pool_id)
        h.pool_id,
        h.pool_size_usd_proxy
    from rh_pool_hourly_metrics h
    cross join params
    where h.chain_id = p_chain_id
      and h.asset_scope = p_asset_scope
      and h.bucket_start >= params.current_hour - interval '23 hours'
      and h.bucket_start <= params.current_hour
      and (p_pool_ids is null or h.pool_id = any (p_pool_ids))
    order by h.pool_id, h.bucket_start desc, h.updated_at desc
)
insert into rh_pool_window_rankings (
    chain_id,
    asset_scope,
    pool_id,
    window_hours,
    pool_pair,
    pool_address,
    token0_symbol,
    token0_address,
    token1_symbol,
    token1_address,
    rwa_symbols,
    fee_pips,
    initialize_block,
    swap_count,
    fee_income_usd,
    pool_size_usd_proxy,
    window_yield_percent,
    annualized_yield_percent,
    window_start,
    window_end,
    data_quality,
    computed_at
)
select
    p_chain_id,
    p_asset_scope,
    a.pool_id,
    a.window_hours,
    p.token0_symbol || '/' || p.token1_symbol,
    p.pool_address,
    p.token0_symbol,
    p.currency0,
    p.token1_symbol,
    p.currency1,
    p.rwa_symbols,
    p.fee_pips,
    p.initialize_block,
    a.swap_count,
    a.fee_income_usd,
    s.pool_size_usd_proxy,
    case
        when a.fee_income_usd is null or s.pool_size_usd_proxy is null or s.pool_size_usd_proxy <= 0 then null
        else a.fee_income_usd / s.pool_size_usd_proxy * 100
    end,
    case
        when a.fee_income_usd is null or s.pool_size_usd_proxy is null or s.pool_size_usd_proxy <= 0 then null
        else a.fee_income_usd / s.pool_size_usd_proxy * 100 * 365 * 24 / a.window_hours
    end,
    a.window_start,
    a.window_end,
    case
        when a.fee_income_usd is not null and s.pool_size_usd_proxy is not null then 'high'
        else 'partial'
    end,
    now()
from aggregates a
join rh_uniswap_v4_pools p
  on p.chain_id = p_chain_id
 and p.pool_id = a.pool_id
left join latest_state s on s.pool_id = a.pool_id
on conflict (chain_id, asset_scope, pool_id, window_hours)
do update set
    pool_pair = excluded.pool_pair,
    pool_address = excluded.pool_address,
    token0_symbol = excluded.token0_symbol,
    token0_address = excluded.token0_address,
    token1_symbol = excluded.token1_symbol,
    token1_address = excluded.token1_address,
    rwa_symbols = excluded.rwa_symbols,
    fee_pips = excluded.fee_pips,
    initialize_block = excluded.initialize_block,
    swap_count = excluded.swap_count,
    fee_income_usd = excluded.fee_income_usd,
    pool_size_usd_proxy = excluded.pool_size_usd_proxy,
    window_yield_percent = excluded.window_yield_percent,
    annualized_yield_percent = excluded.annualized_yield_percent,
    window_start = excluded.window_start,
    window_end = excluded.window_end,
    data_quality = excluded.data_quality,
    computed_at = excluded.computed_at;
$$;

revoke all on function public.rh_refresh_window_rankings(integer, text, text[]) from public, anon, authenticated;
grant execute on function public.rh_refresh_window_rankings(integer, text, text[]) to service_role;
