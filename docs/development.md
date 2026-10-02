# Development and ingestion

## Production ingestion

Railway runs `python -m app.cli ingest` every 15 minutes. Each run checks the
GitHub sources, queues alerts for new jobs, and attempts pending Telegram
deliveries.

`.github/workflows/ingest.yml` provides a manual ingestion trigger through
`workflow_dispatch`. It does not set the production schedule.

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
```
