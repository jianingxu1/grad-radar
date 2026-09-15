create table public.telegram_link_intents (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  user_id uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz
);

create index telegram_link_intents_user_pending_idx
  on public.telegram_link_intents (user_id, expires_at desc)
  where consumed_at is null;

create table public.telegram_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users (id) on delete cascade,
  telegram_user_id bigint not null unique,
  telegram_chat_id bigint not null unique,
  status text not null check (status in ('active', 'disabled', 'blocked')),
  created_at timestamptz not null default now(),
  activated_at timestamptz,
  disabled_at timestamptz,
  updated_at timestamptz not null default now()
);

create table public.notification_outbox (
  id uuid primary key default gen_random_uuid(),
  job_posting_id uuid not null references public.job_postings (id) on delete restrict,
  telegram_connection_id uuid not null references public.telegram_connections (id) on delete restrict,
  ingestion_cycle_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'delivered', 'failed', 'cancelled')),
  attempts integer not null default 0 check (attempts >= 0),
  next_attempt_at timestamptz not null default now(),
  locked_at timestamptz,
  delivered_at timestamptz,
  last_error text,
  unique (job_posting_id, telegram_connection_id)
);

create index notification_outbox_pending_idx
  on public.notification_outbox (next_attempt_at, ingestion_cycle_at)
  where status = 'pending';

create table public.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  notification_outbox_id uuid not null references public.notification_outbox (id) on delete restrict,
  attempted_at timestamptz not null default now(),
  telegram_message_id bigint,
  success boolean not null,
  error text
);

alter table public.telegram_link_intents enable row level security;
alter table public.telegram_connections enable row level security;
alter table public.notification_outbox enable row level security;
alter table public.notification_deliveries enable row level security;

revoke all on public.telegram_link_intents, public.telegram_connections,
  public.notification_outbox, public.notification_deliveries from anon, authenticated;
