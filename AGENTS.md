# GradRadar Contributor Guide

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

## Commit conventions

Use Conventional Commits for commit titles and pull request titles:

```text
type(optional-scope): short imperative summary
```

Allowed types include `feat`, `fix`, `refactor`, `test`, `docs`, `chore`,
`ci`, and `build`. Use a scope only when it adds clarity, such as `ingestion`,
`sources`, `storage`, `notifications`, or `tooling`.

- Keep titles lowercase, imperative, and under about 72 characters.
- Do not end titles with a period.
- For non-trivial work, add a blank line and a body explaining what changed and
  why it changed. Wrap body lines at roughly 72 characters.
- Mark intentional breaking changes with `!` in the title and a
  `BREAKING CHANGE:` footer.
