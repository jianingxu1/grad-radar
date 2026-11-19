# Development and ingestion

## Production ingestion

Railway runs `python -m app.cli ingest` every 15 minutes. Each run checks the
GitHub trackers and enabled company boards and queues eligible alerts for new
jobs. Telegram delivery runs independently, as described below. Board sync
failures are recorded separately. The first successful sync of a board shows
its matching jobs without alerting for its backlog.

Set `SOURCE_ADMIN_USER_IDS` to a comma-separated list of Supabase Auth user
UUIDs in the Railway environment to allow Add Source and filter editing.
Apply database migrations before deploying a worker or API that uses their
columns. The configured company boards in `src/app/sources/seed_boards.py` are
created by the ingestion worker; existing disabled boards remain disabled.
Oracle Recruiting sources also store `host` and `site_number` in
`platform_config`. Use an HTTPS Oracle Cloud tenant hostname and a site number
in the `CX` or `CX_<digits>` form. The source's `board_name` remains the
company identifier (for example, `oracle:uber`).

`.github/workflows/ingest.yml` is a manual backup for running ingestion from
GitHub Actions. It does not set or run the production schedule.

The API verifies Supabase access tokens against the project's asymmetric
signing keys. If the project still issues HS256 tokens, set
`SUPABASE_ALLOW_LEGACY_HS256=true` and provide `SUPABASE_PUBLISHABLE_KEY` on
the API until the project migrates to asymmetric signing.

`GET /v1/jobs` accepts offsets through 10,000 and time filters through
87,600 hours. Each API process handles up to four concurrent job searches
and applies a three-second timeout per PostgreSQL statement.

## Telegram delivery cron

Create a separate Railway cron service from the same repository and backend root
as ingestion:

- Start command: `python -m app.cli deliver-notifications`
- Cron schedule: `*/5 * * * *` (every five minutes, UTC)
- Replicas: one
- Required environment: `DATABASE_URL` (the same database as ingestion) and
  `TELEGRAM_BOT_TOKEN`; optionally set `LOG_LEVEL`.
- Do not configure an HTTP health check; this command sends once and exits.

Keep the ingestion service on `python -m app.cli ingest` every 15 minutes. It
continues to save jobs and enqueue alerts atomically but no longer sends messages.
No schema migration or persistent polling service is needed for this change.

The delivery command attempts a nonblocking PostgreSQL transaction advisory lock
before reading the queue. If another sender holds it, the run logs
`notifications.delivery.skipped reason=worker_already_running` and exits
successfully. The lock is shared by all callers of `deliver_pending` against the
same database and remains held through delivery and commit/rollback. PostgreSQL
releases it when the transaction ends, including when a lost connection is closed;
there is no stale flag to clear. The lock protects notification delivery, not
job ingestion or webhook replies.

[Railway cron](https://docs.railway.com/cron-jobs) also skips a scheduled execution
when the previous execution is still running. The database lock additionally
protects against separate services and manual invocations. Five minutes is the
minimum Railway cron interval; scheduling delay and send duration can make delivery
take longer than five minutes after discovery. Due retries are attempted on the
next run. Delivery retains its existing at-least-once behavior: a crash after
Telegram accepts a message but before commit can cause a duplicate.

For rollout, prepare the delivery service with its schedule disabled. Deploy this
revision to ingestion and wait for any older ingestion execution to finish before
enabling the delivery schedule. Older revisions do not acquire the new lock. Jobs
queued during the transition remain in PostgreSQL for the next delivery run.
Do not leave ingestion on the new revision without enabling the delivery service.

Run a delivery pass manually with:

```bash
uv run python -m app.cli deliver-notifications
```

A missing bot token fails before opening a database connection. Unexpected errors
roll back the delivery transaction and exit nonzero; pending work can be retried
on the next scheduled run. Telegram API failures retain the existing outbox retry
handling.

## Run locally

```bash
uv sync
uv run uvicorn app.main:app --reload  # Backend: http://127.0.0.1:8000
npm --prefix web ci
npm --prefix web run dev              # Frontend: http://localhost:5173
```

## Check changes

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
uv run pytest
uv run pre-commit run --all-files
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web run test
npm --prefix web run build
```
