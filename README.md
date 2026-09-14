# GradRadar

GradRadar is a job-discovery service for U.S. bachelor’s and master’s new
graduates seeking software engineering roles. Its MVP ingests two curated
GitHub tracker files, normalizes their current U.S. listings, deduplicates
matching application links, and presents a fresh public feed.

The current product plan is in [docs/system-design.md](docs/system-design.md).
The implementation sequence is in
[docs/implementation-plan.md](docs/implementation-plan.md).
The backend includes revision-aware source ingestion, idempotent PostgreSQL
storage, a current-job listing endpoint, and a database-backed health check.
The website follows after that.

## Local database

Start Docker Desktop, then run:

```bash
supabase start
supabase status
```

Copy the direct PostgreSQL connection string reported by `supabase status`
into `.env` as `DATABASE_URL`. Reset the local database with
`supabase db reset`.

## Verify ingestion

Integration tests start a disposable PostgreSQL container, apply the committed
Supabase migrations, and roll back each test's changes. Docker must be running.

```bash
uv run pytest
DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:54322/postgres' uv run python -m app.cli ingest
```

The ingestion command logs source revisions, parser counts, elapsed time, and
failures to stderr. Set `LOG_LEVEL=DEBUG` in `.env` when diagnosing a run.

## Run the ingestion scheduler

Run this as a separate, long-lived worker process in the same deployment as the
API. It uses `America/Los_Angeles` time, checks every 15 minutes from 7:00 AM
through 8:45 PM, then at 9:00 PM, 11:00 PM, 1:00 AM, 3:00 AM, and 5:00 AM.

```bash
uv run python -m app.scheduler
```

The worker uses a PostgreSQL advisory lock, so an accidental second worker or
a slow run cannot ingest concurrently. Keep the API and scheduler as separate
processes; the scheduler does not serve HTTP traffic.

## Run the API

The backend reads the direct PostgreSQL connection string from `DATABASE_URL`.
For local Supabase, copy the value from `supabase status` into `.env`; for a
hosted Supabase project, use its direct database connection string in the
deployment environment. Do not put it in `supabase/config.toml` or expose it
to the browser.

```bash
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.
`GET /health` returns `{"status": "ok"}` only when the API can reach the
database.

## Send a Telegram message from the backend

Create a bot with [@BotFather](https://t.me/BotFather), then set its token and
the destination chat or channel ID in `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

The bot must be a member of the destination and, for a channel, an admin with
permission to post. Backend workers can use the client without exposing the
token to the API or browser:

```python
from app.config.settings import get_settings
from app.services.telegram import TelegramClient

settings = get_settings()
with TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id) as telegram:
    delivery = telegram.send_message("GradRadar found a new job")
    if not delivery.success:
        print(delivery.error)
```

Pass `chat_id=` to `send_message` to override the configured destination. A
`TelegramDelivery` includes `success`, an optional Telegram `message_id`, and
an error message when delivery fails.

## Run the website

Install the frontend once, then run the API command above and start Vite in a
second terminal:

```bash
npm --prefix web install
npm --prefix web run dev
```

The website runs at `http://localhost:5173` and fetches the API at
`http://127.0.0.1:8000` by default. Copy `web/.env.example` to `web/.env.local`
and set `VITE_API_BASE_URL` for another public API URL. To validate the
frontend, run `npm --prefix web run lint`, `npm --prefix web run format:check`,
`npm --prefix web run test`, and `npm --prefix web run build`.
