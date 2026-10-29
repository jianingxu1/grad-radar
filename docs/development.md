# Development and ingestion

## Production ingestion

Railway runs `python -m app.cli ingest` every 15 minutes. Each run checks the
GitHub trackers and enabled company boards, queues eligible alerts for new
jobs, and attempts pending Telegram deliveries. Board sync failures are
recorded separately. The first successful sync of a board shows its matching
jobs without alerting for its backlog.

Set `SOURCE_ADMIN_USER_IDS` to a comma-separated list of Supabase Auth user
UUIDs in the Railway environment to allow Add Source and filter editing.
Apply database migrations before deploying a worker or API that uses their
columns. The configured company boards in `src/app/sources/seed_boards.py` are
created by the ingestion worker; existing disabled boards remain disabled.

`.github/workflows/ingest.yml` is a manual backup for running ingestion from
GitHub Actions. It does not set or run the production schedule.

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
