alter table public.sources
  add column platform text not null default 'github'
    check (platform in ('github', 'greenhouse', 'ashby', 'lever')),
  add column board_name text,
  add column company_name text,
  add column enabled boolean not null default true,
  add column filter_config jsonb not null default '{}'::jsonb,
  add column priority integer not null default 100,
  add column initial_sync_completed boolean not null default false,
  add column last_sync_status text,
  add column last_sync_error text;

update public.sources set priority = case name
  when 'simplify' then 1
  when 'speedyapply' then 2
  else 100 end;

create unique index sources_platform_board_name_idx
  on public.sources (platform, lower(board_name))
  where board_name is not null;

alter table public.job_posting_sources
  add column active boolean not null default true;
