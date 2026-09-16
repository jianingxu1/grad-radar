# GradRadar Contributor Guide

## Project structure

- `.github/workflows/` — CI/workflow automation. `ingest.yml` manually runs the
  GitHub source ingestion job.
- `docs/` — product and architecture notes. `system-design.md` is the main
  architecture reference; `implementation-plan.md` tracks delivery progress.
- `src/app/` — Python backend package.
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
- `supabase/` — Supabase local config and SQL migrations. Migrations are the
  schema authority for job postings, sources, and Telegram notification tables.
- `tests/` — Python pytest suite, mirroring backend areas with unit and
  integration tests. `tests/fixtures/` stores sample tracker files.
- `web/` — Vite React and TypeScript frontend.
  - `src/App.tsx` is the main feed, FAQ, auth, and notification-settings UI.
  - `src/api.ts` contains API types and fetch helpers.
  - `src/filterState.ts` keeps feed filters in the URL.
  - `src/supabase.ts` creates the optional Supabase browser client.
  - `public/` stores logo and icon assets.
  - `vercel.json` rewrites SPA routes to `index.html`.
- Root config files: `pyproject.toml`, `uv.lock`, `pyrightconfig.json`, and
  `.pre-commit-config.yaml` define the Python toolchain. `web/package.json` and
  `web/package-lock.json` define the frontend toolchain.
- Env templates: `.env.example` for backend/shared settings and
  `web/.env.example` for browser-exposed frontend settings. Never commit real
  `.env` files.

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

```bash
uv sync
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

Pre-commit automatically runs Ruff and Pyright for staged Python changes. Run
`uv run pre-commit run --all-files` when validating the complete repository
manually.

Run `uv run pytest` after any feature, bug fix, refactor, test change, or
dependency change that can affect application behavior, and before opening a
pull request. Tests are not required for documentation-only changes.

External HTTP calls in tests must be mocked with `respx` rather than calling
live sources.

## Testing and code quality

- Every new feature and behavior-changing bug fix must include focused unit
  tests. Update existing tests when changing established behavior.
- Prefer small, single-purpose functions and modules with clear boundaries.
- Use descriptive names and type annotations at public and external-data
  boundaries.
- Keep fetching and other side effects separate from normalization and business
  logic so the latter stays straightforward to test.
- Avoid premature abstractions and comments that merely restate the code.
  Comments should explain non-obvious decisions and constraints.

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
