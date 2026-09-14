# GradRadar

GradRadar is a job-discovery service for U.S. bachelor’s and master’s new
graduates seeking software engineering roles. Its MVP ingests two curated
GitHub tracker files, normalizes their current U.S. listings, deduplicates
matching application links, and presents a fresh public feed.

The current product plan is in [docs/system-design.md](docs/system-design.md).
The implementation sequence is in
[docs/implementation-plan.md](docs/implementation-plan.md).
The first implementation milestone is revision-aware source ingestion and
idempotent PostgreSQL storage; the public API and website follow after that.

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
