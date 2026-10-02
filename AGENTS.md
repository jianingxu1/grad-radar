# GradRadar contributor guide

## Project structure

- `.github/workflows/` contains CI workflows. `ingest.yml` runs GitHub source
  ingestion when triggered manually.
- `docs/` contains product and architecture notes. Start with `system-design.md`
  for the architecture, `implementation-plan.md` for delivery progress, and
  `frontend-testing.md` for local browser checks.
- `src/app/` contains the Python backend.
  - `main.py` creates the FastAPI app.
  - `cli.py` runs source bootstrap and ingestion commands.
  - `scheduler.py` runs scheduled ingestion and Telegram delivery.
  - `api/` contains HTTP routes and response schemas.
  - `config/` loads environment settings.
  - `database/` contains SQLAlchemy models and session setup.
  - `domain/` contains pure normalization and eligibility rules.
  - `models/` contains validated internal data models.
  - `repositories/` contains database persistence logic.
  - `services/` contains auth, GitHub ingestion, notifications, and Telegram
    delivery logic.
  - `sources/` defines configured job trackers and their parsers.
- `supabase/` contains local Supabase config and SQL migrations. The migrations
  define the job posting, source, and Telegram notification tables.
- `tests/` contains Python unit and integration tests for the backend.
  `tests/fixtures/` stores sample tracker files.
- `web/` contains the Vite, React, and TypeScript frontend.
  - `src/App.tsx` is the main feed, FAQ, auth, and notification-settings UI.
  - `src/api.ts` contains API types and fetch helpers.
  - `src/filterState.ts` keeps feed filters in the URL.
  - `src/supabase.ts` creates the optional Supabase browser client.
  - `public/` stores logo and icon assets.
  - `vercel.json` rewrites SPA routes to `index.html`.
- `pyproject.toml`, `uv.lock`, `pyrightconfig.json`, and
  `.pre-commit-config.yaml` configure Python dependencies and checks.
  `web/package.json` and `web/package-lock.json` configure the frontend.
- `.env.example` lists backend and shared settings. `web/.env.example` lists
  browser-exposed settings. Never commit real `.env` files.

Document every new top-level project folder here.

## Development environment

- Use Python 3.13.
- Use `uv` for dependencies, virtual environments, and commands. Do not use
  `pip` or Poetry in this repository.
- Declare dependencies in `pyproject.toml` and commit `uv.lock` whenever they
  change.
- Store local credentials and notification tokens in `.env`. Never commit
  `.env` files or secrets.

## Common commands

### Run locally

```bash
uv sync
uv run uvicorn app.main:app --reload  # Backend: http://127.0.0.1:8000
npm --prefix web ci
npm --prefix web run dev              # Frontend: http://localhost:5173
```

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

## Quality checks

Pre-commit runs Ruff and Pyright on staged Python changes. Run
`uv run pre-commit run --all-files` to check the whole repository.

Run `uv run pytest` after a feature, bug fix, refactor, test change, or dependency
change that can affect application behavior. Run it before opening a pull
request. Documentation-only changes do not need tests.

For frontend browser checks, follow [docs/frontend-testing.md](docs/frontend-testing.md).

External HTTP calls in tests must be mocked with `respx` rather than calling
live sources.

## Testing and code quality

- Every new feature and behavior-changing bug fix must include focused unit
  tests. Update existing tests when changing established behavior.
- Keep each function and module focused on one job.
- Use descriptive names and type annotations at public and external-data
  boundaries.
- Keep fetching and other side effects separate from normalization and business
  logic so the latter stays straightforward to test.
- Add abstractions when they simplify shared behavior. Use comments to explain
  decisions and constraints that the code does not make clear.

## Commit messages

Use Conventional Commits:

```text
<type>(<scope>): <summary>
```

Keep the summary short and describe what changed. Add a commit body explaining
why the change was needed.

Common types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`.

Examples:

```text
feat(worker): add scheduled GitHub ingestion

Fetch job listings every hour so new postings appear automatically.

fix(jobs): normalize application URLs before deduplication

Different trackers can point to the same job using different tracking URLs.
Normalization prevents duplicate listings.
```
