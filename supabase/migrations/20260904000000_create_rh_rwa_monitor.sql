-- Robinhood Chain RWA / Uniswap v4 monitoring schema.
-- The worker writes through the Supabase service role; the frontend reads only
-- the current precomputed window ranking table.

create table if not exists public.rh_rwa_assets (
    chain_id integer not null,
    token_address text not null
        check (token_address = lower(token_address) and token_address ~ '^0x[0-9a-f]{40}$'),
    token_symbol text not null,
    token_name text not null,
    isin text,
    token_decimals smallint not null check (token_decimals between 0 and 255),
    status text not null,
    active boolean not null default true,
    registry_order integer not null default 0 check (registry_order >= 0),
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    is_new_issue boolean not null default false,
    updated_at timestamptz not null default now(),
    primary key (chain_id, token_address)
);

create table if not exists public.rh_uniswap_v4_pools (
    chain_id integer not null,
    pool_id text not null
        check (pool_id = lower(pool_id) and pool_id ~ '^0x[0-9a-f]{64}$'),
    pool_address text not null
        check (pool_address = lower(pool_address) and pool_address ~ '^0x[0-9a-f]{64}$'),
    pool_manager_address text not null
        check (pool_manager_address = lower(pool_manager_address) and pool_manager_address ~ '^0x[0-9a-f]{40}$'),
    currency0 text not null
        check (currency0 = lower(currency0) and currency0 ~ '^0x[0-9a-f]{40}$'),
    currency1 text not null
        check (currency1 = lower(currency1) and currency1 ~ '^0x[0-9a-f]{40}$'),
    token0_symbol text not null,
    token1_symbol text not null,
    rwa_symbols text not null default '',
    fee_pips integer not null check (fee_pips between 0 and 1000000),
    tick_spacing integer not null,
    hooks text not null
        check (hooks = lower(hooks) and hooks ~ '^0x[0-9a-f]{40}$'),
    initialize_block bigint not null check (initialize_block >= 0),
    initialize_timestamp timestamptz,
    updated_at timestamptz not null default now(),
    primary key (chain_id, pool_id),
    unique (chain_id, pool_address)
);

create table if not exists public.rh_uniswap_v4_swap_events (
    chain_id integer not null,
    tx_hash text not null
        check (tx_hash = lower(tx_hash) and tx_hash ~ '^0x[0-9a-f]{64}$'),
    log_index integer not null check (log_index >= 0),
    pool_id text not null,
    block_number bigint not null check (block_number >= 0),
    block_timestamp timestamptz not null,
    transaction_index integer not null check (transaction_index >= 0),
    amount0 numeric(78, 0) not null,
    amount1 numeric(78, 0) not null,
    fee_pips integer not null check (fee_pips between 0 and 1000000),
    fee_income_token0_raw numeric(78, 0) not null default 0,
    fee_income_token1_raw numeric(78, 0) not null default 0,
    fee_income_usd numeric(38, 18),
    sqrt_price_x96 numeric(78, 0),
    active_liquidity numeric(78, 0),
    pool_size_usd_proxy numeric(38, 18),
    inserted_at timestamptz not null default now(),
    primary key (chain_id, tx_hash, log_index),
    foreign key (chain_id, pool_id)
        references public.rh_uniswap_v4_pools (chain_id, pool_id)
        on delete cascade
);

create table if not exists public.rh_pool_hourly_metrics (
    chain_id integer not null,
    asset_scope text not null check (length(trim(asset_scope)) > 0),
    pool_id text not null,
    bucket_start timestamptz not null
        check (bucket_start = date_trunc('hour', bucket_start)),
    swap_count integer not null default 0 check (swap_count >= 0),
    fee_income_token0_raw numeric(78, 0) not null default 0,
    fee_income_token1_raw numeric(78, 0) not null default 0,
    fee_income_usd numeric(38, 18),
    active_liquidity numeric(78, 0),
    sqrt_price_x96 numeric(78, 0),
    pool_size_usd_proxy numeric(38, 18),
    latest_swap_block bigint,
    bucket_complete boolean not null default false,
    data_quality text not null default 'partial'
        check (data_quality in ('high', 'partial')),
    updated_at timestamptz not null default now(),
    primary key (chain_id, asset_scope, pool_id, bucket_start),
    foreign key (chain_id, pool_id)
        references public.rh_uniswap_v4_pools (chain_id, pool_id)
        on delete cascade
);

create table if not exists public.rh_pool_window_rankings (
    chain_id integer not null,
    asset_scope text not null check (length(trim(asset_scope)) > 0),
    pool_id text not null,
    window_hours smallint not null check (window_hours in (2, 4, 24)),
    pool_pair text not null,
    pool_address text not null
        check (pool_address = lower(pool_address) and pool_address ~ '^0x[0-9a-f]{64}$'),
    token0_symbol text not null,
    token0_address text not null,
    token1_symbol text not null,
    token1_address text not null,
    rwa_symbols text not null default '',
    fee_pips integer not null default 0 check (fee_pips between 0 and 1000000),
    initialize_block bigint not null default 0 check (initialize_block >= 0),
    swap_count integer not null default 0 check (swap_count >= 0),
    fee_income_usd numeric(38, 18),
    pool_size_usd_proxy numeric(38, 18),
    window_yield_percent numeric(38, 18),
    annualized_yield_percent numeric(38, 18),
    window_start timestamptz not null,
    window_end timestamptz not null,
    data_quality text not null default 'partial'
        check (data_quality in ('high', 'partial')),
    is_public boolean not null default true,
    computed_at timestamptz not null default now(),
    primary key (chain_id, asset_scope, pool_id, window_hours),
    foreign key (chain_id, pool_id)
        references public.rh_uniswap_v4_pools (chain_id, pool_id)
        on delete cascade
);

create table if not exists public.rh_sync_checkpoints (
    sync_name text primary key,
    chain_id integer not null,
    asset_scope text not null,
    last_initialize_block bigint not null default 0 check (last_initialize_block >= 0),
    last_swap_block bigint not null default 0 check (last_swap_block >= 0),
    last_asset_sync_at timestamptz,
    last_success_at timestamptz,
    last_error text,
    updated_at timestamptz not null default now()
);

create index if not exists rh_swap_events_pool_block_idx
    on public.rh_uniswap_v4_swap_events (chain_id, pool_id, block_number desc);
create index if not exists rh_swap_events_timestamp_idx
    on public.rh_uniswap_v4_swap_events (chain_id, block_timestamp desc);
create index if not exists rh_hourly_pool_bucket_idx
    on public.rh_pool_hourly_metrics (chain_id, asset_scope, pool_id, bucket_start desc);
create index if not exists rh_hourly_bucket_pool_idx
    on public.rh_pool_hourly_metrics (chain_id, asset_scope, bucket_start desc, pool_id);
create index if not exists rh_window_ranking_order_idx
    on public.rh_pool_window_rankings (
        chain_id,
        asset_scope,
        window_hours,
        annualized_yield_percent desc nulls last
    );

alter table public.rh_rwa_assets enable row level security;
alter table public.rh_uniswap_v4_pools enable row level security;
alter table public.rh_uniswap_v4_swap_events enable row level security;
alter table public.rh_pool_hourly_metrics enable row level security;
alter table public.rh_pool_window_rankings enable row level security;
alter table public.rh_sync_checkpoints enable row level security;

revoke all on public.rh_rwa_assets from anon, authenticated;
revoke all on public.rh_uniswap_v4_pools from anon, authenticated;
revoke all on public.rh_uniswap_v4_swap_events from anon, authenticated;
revoke all on public.rh_pool_hourly_metrics from anon, authenticated;
revoke all on public.rh_sync_checkpoints from anon, authenticated;
revoke all on public.rh_pool_window_rankings from anon, authenticated;
grant select on public.rh_pool_window_rankings to anon, authenticated;

drop policy if exists rh_pool_window_rankings_public_read on public.rh_pool_window_rankings;
create policy rh_pool_window_rankings_public_read
    on public.rh_pool_window_rankings
    for select
    to anon, authenticated
    using (is_public);

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

create or replace function public.rh_ingest_hourly_batch(
    p_chain_id integer,
    p_asset_scope text,
    p_pool_ids text[],
    p_last_initialize_block bigint,
    p_last_swap_block bigint
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from rh_pool_hourly_metrics
    where chain_id = p_chain_id
      and asset_scope = p_asset_scope
      and pool_id = any (p_pool_ids)
      and bucket_start >= date_trunc('hour', now() - interval '7 days');

    insert into rh_pool_hourly_metrics (
        chain_id,
        asset_scope,
        pool_id,
        bucket_start,
        swap_count,
        fee_income_token0_raw,
        fee_income_token1_raw,
        fee_income_usd,
        active_liquidity,
        sqrt_price_x96,
        pool_size_usd_proxy,
        latest_swap_block,
        bucket_complete,
        data_quality,
        updated_at
    )
    with event_buckets as (
        select
            e.pool_id,
            date_trunc('hour', e.block_timestamp) as bucket_start,
            count(*)::integer as swap_count,
            sum(e.fee_income_token0_raw) as fee_income_token0_raw,
            sum(e.fee_income_token1_raw) as fee_income_token1_raw,
            case
                when count(*) filter (where e.fee_income_usd is null) > 0 then null
                else sum(e.fee_income_usd)
            end as fee_income_usd,
            max(e.block_number) as latest_swap_block
        from rh_uniswap_v4_swap_events e
        where e.chain_id = p_chain_id
          and e.pool_id = any (p_pool_ids)
          and e.block_timestamp >= now() - interval '7 days'
        group by e.pool_id, date_trunc('hour', e.block_timestamp)
    ),
    latest_states as (
        select distinct on (e.pool_id, date_trunc('hour', e.block_timestamp))
            e.pool_id,
            date_trunc('hour', e.block_timestamp) as bucket_start,
            e.active_liquidity,
            e.sqrt_price_x96,
            e.pool_size_usd_proxy
        from rh_uniswap_v4_swap_events e
        where e.chain_id = p_chain_id
          and e.pool_id = any (p_pool_ids)
          and e.block_timestamp >= now() - interval '7 days'
        order by e.pool_id, date_trunc('hour', e.block_timestamp), e.block_number desc, e.log_index desc
    )
    select
        p_chain_id,
        p_asset_scope,
        b.pool_id,
        b.bucket_start,
        b.swap_count,
        b.fee_income_token0_raw,
        b.fee_income_token1_raw,
        b.fee_income_usd,
        s.active_liquidity,
        s.sqrt_price_x96,
        s.pool_size_usd_proxy,
        b.latest_swap_block,
        b.bucket_start < date_trunc('hour', now()),
        case when b.fee_income_usd is not null and s.pool_size_usd_proxy is not null then 'high' else 'partial' end,
        now()
    from event_buckets b
    left join latest_states s using (pool_id, bucket_start);

    perform rh_refresh_window_rankings(p_chain_id, p_asset_scope, p_pool_ids);

    insert into rh_sync_checkpoints (
        sync_name,
        chain_id,
        asset_scope,
        last_initialize_block,
        last_swap_block,
        last_success_at,
        last_error,
        updated_at
    ) values (
        'rwa_uniswap_v4',
        p_chain_id,
        p_asset_scope,
        greatest(p_last_initialize_block, 0),
        greatest(p_last_swap_block, 0),
        now(),
        null,
        now()
    )
    on conflict (sync_name)
    do update set
        chain_id = excluded.chain_id,
        asset_scope = excluded.asset_scope,
        last_initialize_block = excluded.last_initialize_block,
        last_swap_block = excluded.last_swap_block,
        last_success_at = excluded.last_success_at,
        last_error = null,
        updated_at = excluded.updated_at;
end;
$$;

create or replace function public.rh_cleanup_expired_data(
    p_retention interval default interval '7 days'
)
returns table (swap_events_deleted bigint, hourly_metrics_deleted bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_swap_events_deleted bigint;
    v_hourly_metrics_deleted bigint;
begin
    delete from rh_uniswap_v4_swap_events
    where block_timestamp < now() - p_retention;
    get diagnostics v_swap_events_deleted = row_count;

    delete from rh_pool_hourly_metrics
    where bucket_start < date_trunc('hour', now() - p_retention);
    get diagnostics v_hourly_metrics_deleted = row_count;

    return query select v_swap_events_deleted, v_hourly_metrics_deleted;
end;
$$;

revoke all on function public.rh_refresh_window_rankings(integer, text, text[]) from public, anon, authenticated;
revoke all on function public.rh_ingest_hourly_batch(integer, text, text[], bigint, bigint) from public, anon, authenticated;
revoke all on function public.rh_cleanup_expired_data(interval) from public, anon, authenticated;
grant execute on function public.rh_refresh_window_rankings(integer, text, text[]) to service_role;
grant execute on function public.rh_ingest_hourly_batch(integer, text, text[], bigint, bigint) to service_role;
grant execute on function public.rh_cleanup_expired_data(interval) to service_role;
