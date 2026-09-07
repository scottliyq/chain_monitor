-- Store the latest Robinhood corporate-action multiplier for each Stock Token.

alter table public.rh_rwa_assets
    add column if not exists current_multiplier numeric(38, 18);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'rh_rwa_assets_current_multiplier_positive'
          and conrelid = 'public.rh_rwa_assets'::regclass
    ) then
        alter table public.rh_rwa_assets
            add constraint rh_rwa_assets_current_multiplier_positive
            check (current_multiplier is null or current_multiplier > 0);
    end if;
end;
$$;
