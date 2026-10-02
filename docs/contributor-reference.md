# Contributor practices

Follow the repository rules in [AGENTS.md](../AGENTS.md). These guidelines
apply when writing code, tests, or commit messages.

## Code and tests

- Keep each function and module focused on one job.
- Use descriptive names and type annotations at public and external-data
  boundaries.
- Keep fetching and other side effects separate from normalization and business
  logic so the latter stays straightforward to test.
- Add abstractions when they simplify shared behavior. Use comments to explain
  decisions and constraints that the code does not make clear.

## Commit messages

Use this Conventional Commits format:

```text
<type>(<scope>): <summary>
```

Keep the summary short and describe what changed. Add a commit body explaining
why the change was needed.

Common types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`.

```text
feat(worker): add scheduled GitHub ingestion

Fetch job listings every 15 minutes so new postings appear automatically.

fix(jobs): normalize application URLs before deduplication

Different trackers can point to the same job using different tracking URLs.
Normalization prevents duplicate listings.
```
