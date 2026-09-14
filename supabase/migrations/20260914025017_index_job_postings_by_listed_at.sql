drop index public.job_postings_first_seen_at_desc_idx;

create index job_postings_listed_at_desc_idx
  on public.job_postings (listed_at desc nulls last, id desc);
