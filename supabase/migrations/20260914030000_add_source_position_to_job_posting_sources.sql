alter table public.job_posting_sources
  add column source_position integer;

create index job_posting_sources_source_position_idx
  on public.job_posting_sources (source_id, source_position asc nulls last);
