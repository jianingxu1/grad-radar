alter table public.sources
  drop constraint sources_platform_check;

alter table public.sources
  add constraint sources_platform_check
    check (platform in ('github', 'greenhouse', 'ashby', 'lever', 'oracle')),
  add column platform_config jsonb;
