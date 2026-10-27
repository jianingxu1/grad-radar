# Project structure

- `.github/workflows/` contains CI workflows. `ingest.yml` runs GitHub source
  ingestion when triggered manually.
- `docs/` contains project guides and design notes. Start with
  `system-design.md` for design decisions and `frontend-testing.md` for browser
  checks.
- `src/app/` contains the Python backend.
  - `main.py` creates the FastAPI app.
  - `cli.py` runs source bootstrap and ingestion commands. The ingestion command
    also delivers pending Telegram notifications.
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
  - `src/App.tsx` coordinates routing, authentication, and feed state.
  - `src/components/` contains the feed header, filters, listings, pagination,
    and shared presentation helpers.
  - `src/pages/` contains the FAQ and notification settings pages.
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
