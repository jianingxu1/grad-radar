# Repository bug audit — October 27, 2026

Reviewed tracked application code, tests, migrations, workflow, and configuration. These are concrete bugs or behavior gaps found in the current checkout. No fixes were made.

## Findings

- **P1 — `src/app/services/github_ingestion.py`, lines 53–57 and 130–134.** Posting inserts and the processed source SHA commit before notification outbox rows are created. If the later sync timestamp or enqueue step fails, the next run sees the SHA as unchanged and cannot recover the newly found job IDs. Subscribers permanently miss those alerts. **Possible fix:** Insert outbox rows in the same transaction as postings and the SHA, or persist a recoverable enqueue cursor and retry it on later runs.
- **P2 — `.github/workflows/ingest.yml`, lines 17–20 and 38–39.** This workflow is a manual backup; Railway runs production ingestion. The backup invokes the combined ingest-and-deliver command without `TELEGRAM_BOT_TOKEN`. If it is run while alerts are pending, each run records a failed send; after eight attempts, the outbox rows become `failed` and the production worker will not send them. **Possible fix:** Provide the bot token secret to the backup workflow, or make delivery skip pending rows without changing attempts when no token is configured.
- **P2 — `src/app/sources/parsing.py`, lines 104–106 and 116–120.** A SpeedyApply heading without a table, or a Simplify table without job rows, returns a successful result with `parsed=0`. Ingestion then records that revision as processed at `src/app/services/github_ingestion.py:133`, so a truncated or changed source format is silently accepted. Both cases were reproduced. **Possible fix:** Validate required table headers and a plausible parsed-row count before advancing the source SHA; fail the revision when those checks fail.
- **Investigated — `src/app/domain/job_posting_normalization.py`, lines 70–77.** An unrelated example URL with `gh_jid=123` produces the same key as Greenhouse job 123, so a collision is possible in theory. A read-only Supabase query did not establish an actual merge of unrelated postings; `application_key` is unique and only one apply URL is retained. No code change is recommended without stronger evidence.
- **P2 — `web/src/App.tsx`, lines 208–215.** Home navigation removes the query string but keeps the existing filter and page state. After navigating away from a filtered feed and returning home, the bare `/` URL can still show the old filtered results. **Possible fix:** Reset filters and cached page when navigating home, or preserve the query in the home URL if retaining filters is intended.
- **P2 — `web/src/App.tsx`, lines 535–562.** Notification settings state survives a change of signed-in user, and outstanding fetches are not cancelled or checked against the user they loaded for. A previous account's status can remain visible or overwrite the next account's result. **Possible fix:** Clear settings when the user ID changes and abort or ignore stale fetch and poll responses.
- **P2 — `web/src/App.tsx`, lines 539–550 and 617–625.** If the first notification settings request fails, `settings` stays `null`; the page shows an error alongside `Loading notification settings…` indefinitely and offers no retry. **Possible fix:** Track loading separately from the response and show a retry button after failure.

## Validation and limits

- Reproduced the zero-row parser results, mixed-location classification, and Greenhouse key collision with direct function calls.
- Python unit tests: 64 passed. Frontend tests: 24 passed. Frontend lint and production build passed. Pre-commit checks and Pyright passed.
- The 21 Python integration tests could not start because this environment cannot connect to Docker. Database-backed behavior was traced through code but not executed here.
- Mixed U.S./foreign locations were reviewed and accepted as intended behavior by the project owner; that item is no longer a finding.
- Reviewed all application source, tests, migrations, workflows, and configuration files under `src/app`, `web`, `tests`, `supabase`, and the repository root. Images and generated lockfile contents were excluded from bug analysis.
