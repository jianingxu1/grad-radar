# GradRadar backend implementation plan

This plan covers the backend through reliable GitHub ingestion. The FastAPI
read API, React application, hosting, and notifications come only after these
six phases are reviewed together.

## Phase 1: Foundation and database

- Install Docker Desktop and initialize Supabase locally.
- Add committed Supabase configuration, `.env.example`, and migration workflow
  documentation.
- Create these tables:
  - `job_postings`
  - `sources`
  - `job_posting_sources`
- Use database-generated UUID IDs, a plain-text `application_key`, RLS on every
  table, and no browser-access policies.
- Store GitHub repository URLs in `sources`; keep source branch, file path, and
  parser selection as typed Python configuration.
- Add `last_processed_revision_sha` to `sources` so unchanged GitHub files can
  be skipped.
- Use Supabase SQL migrations as the only schema history. Do not use Alembic.

**Review checkpoint:** `supabase db reset` creates the schema from scratch, and
SQLAlchemy can connect and read/write it locally.

## Phase 2: Core backend boundary

- Add settings loaded from `.env`, `psycopg`, SQLAlchemy engine/session
  management, and typed SQLAlchemy models.
- Add a small manual-ingestion CLI command. Production scheduling comes later
  through a separate worker.
- Bootstrap the two configured sources idempotently.
- Retain jobs after they disappear from a source. `last_seen_at` is provenance
  and debugging information, not an active-status rule.

**Review checkpoint:** the CLI connects locally, initializes sources, and can
run safely twice.

## Phase 3: Normalization and eligibility

- Implement aggressive `application_key` normalization inspired by the Go
  reference: extract stable IDs for known ATSs first; otherwise normalize host
  and path and remove query and fragment data.
- Keep the source-supplied application URL separately from the normalized key.
- Convert tracker ages such as `3d` to UTC
  `listed_at = source_revision_at - age`; do not store the raw age text.
- Keep location as one opaque source-provided string.
- Apply conservative U.S. eligibility before persistence: store clearly U.S.
  and U.S.-remote roles only; log clear non-U.S. and ambiguous rows without
  persisting them.
- Add focused tests that make each intentional URL merge explicit.

**Review checkpoint:** fixtures and tests cover URL normalization, relative-date
conversion, and U.S. eligibility before a live source parser exists.

## Phase 4: Shared ingestion workflow

- Define one Pydantic `ParsedJobPosting` contract.
- Persist idempotently by `application_key`.
- Use a fixed source-priority order when sources disagree on display fields.
- Create a `job_posting_sources` association for every contributing source.
- Test repeat ingestion and cross-source deduplication.

**Review checkpoint:** synthetic data proves that repeated ingestion and two
matching sources create one job record with both source links.

## Phase 5: Source parsers

- Implement the SpeedyApply Markdown-table parser using saved fixtures.
- Implement the Simplify HTML-table parser, including continuation-company rows
  and selection of the employer Apply link over the Simplify link.
- Reject malformed source files safely and isolate failures by source.
- Decide the suspicious row-count-drop threshold before implementing source
  snapshot/removal handling.

**Review checkpoint:** parsers run from local fixtures only, with all HTTP
requests mocked through `respx`.

## Phase 6: GitHub ingestion and worker

- Fetch GitHub file metadata, compare the revision SHA, and parse only changed
  source files.
- Use retry/backoff and continue processing healthy sources when one fails.
- Run ingestion manually locally; later deploy it as a separate worker on a
  10-minute schedule.
- Add integration tests against local Supabase.

**Review checkpoint:** the complete backend ingests both sources reliably and
idempotently. Review it before starting FastAPI, React, or hosting work.

