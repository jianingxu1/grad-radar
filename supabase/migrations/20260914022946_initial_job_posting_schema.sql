
create table public.job_postings (
  id uuid primary key default gen_random_uuid(),
  application_key text not null unique,
  company_name text not null,
  title text not null,
  apply_url text not null,
  location text not null,
  listed_at timestamptz,
  first_seen_at timestamptz not null
);

create index job_postings_first_seen_at_desc_idx
  on public.job_postings (first_seen_at desc);

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  url text not null,
  last_processed_revision_sha text,
  last_successful_sync_at timestamptz
);

create table public.job_posting_sources (
  job_posting_id uuid not null references public.job_postings (id)
    on delete restrict,
  source_id uuid not null references public.sources (id) on delete restrict,
  last_seen_at timestamptz not null,
  primary key (job_posting_id, source_id)
);

create index job_posting_sources_source_id_idx
  on public.job_posting_sources (source_id);

alter table public.job_postings enable row level security;
alter table public.sources enable row level security;
alter table public.job_posting_sources enable row level security;
