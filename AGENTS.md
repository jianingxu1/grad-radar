# GradRadar contributor guide

## Read when needed

- [README.md](README.md): Read when you need the product overview or current
  user-facing features.
- [docs/system-design.md](docs/system-design.md): Read when changing the data
  model, ingestion flow, API, or product scope. Check the code before relying on
  older design decisions.
- [docs/project-structure.md](docs/project-structure.md): Read when locating
  code or adding a project folder.
- [docs/development.md](docs/development.md): Read when setting up the project,
  running checks, or changing the production ingestion worker.
- [docs/frontend-testing.md](docs/frontend-testing.md): Read when testing
  frontend changes in a browser; it gives the steps and commands.
- [docs/contributor-reference.md](docs/contributor-reference.md): Read when
  writing code or tests, or preparing a commit; it has coding and commit
  practices.

## Repository layout

- Top-level folders: `.github/workflows/` holds CI and manual ingestion;
  `docs/` holds project notes; `src/` holds the Python backend; `supabase/`
  holds database config and migrations; `tests/` holds backend tests; `web/`
  holds the frontend. Document every new top-level project folder here.
- Railway runs `python -m app.cli ingest` every 15 minutes in production. The
  GitHub Actions ingestion workflow is manual, not the production schedule.

## Development rules

- Use Python 3.13 and `uv` for dependencies, virtual environments, and
  commands. Do not use `pip` or Poetry in this repository.
- Declare dependencies in `pyproject.toml` and commit `uv.lock` whenever they
  change.
- Store local credentials and notification tokens in `.env`. Never commit
  `.env` files or secrets.
- Every new feature and behavior-changing bug fix must include focused unit
  tests. Update existing tests when changing established behavior.
- Mock external HTTP calls in tests with `respx`; do not call live sources.

## Checks

- Pre-commit runs Ruff and Pyright on staged Python changes. Run
  `uv run pre-commit run --all-files` to check the whole repository.
- Run `uv run pytest` after a feature, bug fix, refactor, test change, or
  dependency change that can affect application behavior, and before opening a
  pull request. Documentation-only changes do not need tests.

## Commits

Use Conventional Commits with a short summary and a body explaining why the
change was needed.
