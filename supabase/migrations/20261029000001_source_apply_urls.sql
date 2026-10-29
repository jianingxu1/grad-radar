alter table public.job_posting_sources
  add column apply_url text;

update public.job_posting_sources as link
set apply_url = job.apply_url
from public.job_postings as job
where job.id = link.job_posting_id;

alter table public.job_posting_sources
  alter column apply_url set not null;
