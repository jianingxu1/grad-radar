# GradRadar backend implementation plan

This document is the implementation plan for the backend only. It ends after
reliable ingestion of the two GitHub sources. FastAPI endpoints, the React
client, deployment, and notifications are intentionally outside this plan.

Each phase has a review checkpoint. Do not start the next phase until the
checkpoint is accepted. Each contained change is committed separately; never
bundle schema, normalization, parsers, and ingestion orchestration into one
commit.

## Shared decisions

- PostgreSQL runs through Supabase. Supabase SQL migrations are the only schema
  history; SQLAlchemy maps and queries existing tables but never calls
  `metadata.create_all()`. Alembic is removed rather than used alongside
  Supabase migrations.
- Tables live in the `public` schema. RLS is enabled on every table, but no
  `anon` or `authenticated` policies exist in this backend milestone. The
  Python service connects directly to PostgreSQL. A public schema is not
  permission for browser access.
- `JobPosting` is the domain name. Its database primary key is an opaque UUID;
  `application_key` is a separate, unique, calculated deduplication key.
- `location` is one opaque source-provided string. The system does not split,
  geocode, or normalize locations in this backend.
- `listed_at` is an estimate computed from tracker age and the GitHub source
  revision timestamp. It is never an employer-verified posting date. The
  original tracker age is not persisted.
- Source links point to GitHub repositories only. We do not retain or return
  per-job links pinned to a Git commit SHA.
- Jobs remain stored and visible after a source stops listing them.
  `last_seen_at` is diagnostic provenance, not an `active` flag.
- Initial display-field source priority is `simplify`, then `speedyapply`.
  When both sources resolve to one application key but disagree, the
  higher-priority source wins deterministically.

## Phase 1: Foundation and database

### Goal

Create a reproducible local Supabase database and its first migration. No
parser, GitHub fetch, or application business logic belongs in this phase.

### Prerequisites

- Install and start Docker Desktop. It is required by `supabase start` and is
  a machine prerequisite, not a repository dependency. Docker is currently
  unavailable on this development machine.
- The Supabase CLI is installed. Confirm supported commands with
  `supabase --help` before using them.
- Do not create or link a hosted Supabase project yet. The first validation is
  entirely local.

### Repository setup

1. Run `supabase init` at the repository root and commit generated
   `supabase/` configuration.
2. Add a committed `.env.example` with placeholders for `DATABASE_URL` and
   the later optional `GITHUB_TOKEN`.
3. Keep real `.env` files ignored. Never commit a project URL, database
   password, service-role key, or GitHub token.
4. Document local commands in the README: start Docker Desktop, run
   `supabase start`, inspect `supabase status`, and copy the direct
   PostgreSQL connection string into `.env`.
5. Create the first migration with `supabase migration new`. Do not invent a
   timestamped migration filename manually.

### First migration

Create only these three tables in `public`.

#### `job_postings`

| Column | Type and constraint | Purpose |
| --- | --- | --- |
| `id` | `uuid`, primary key, database default | Opaque database identity. |
| `application_key` | `text`, non-null, unique | Calculated deduplication key. |
| `company_name` | `text`, non-null | Current display company. |
| `title` | `text`, non-null | Current display role title. |
| `apply_url` | `text`, non-null | Source-supplied user link. |
| `location` | `text`, non-null | Unmodified rendered location text. |
| `listed_at` | `timestamptz`, nullable | Estimated tracker-derived timestamp. |
| `first_seen_at` | `timestamptz`, non-null | Time GradRadar first persisted the job. |

`application_key` has a unique constraint. Add an index on
`first_seen_at DESC` for the eventual newest-first feed.

#### `sources`

| Column | Type and constraint | Purpose |
| --- | --- | --- |
| `id` | `uuid`, primary key, database default | Opaque database identity. |
| `name` | `text`, non-null, unique | Initially `simplify` or `speedyapply`. |
| `url` | `text`, non-null | GitHub repository URL. |
| `last_processed_revision_sha` | `text`, nullable | Last source revision fully persisted. |
| `last_successful_sync_at` | `timestamptz`, nullable | Most recent successful ingestion. |

The branch, file path, parser, enabled state, and priority are typed,
version-controlled Python configuration added in phase 2.

#### `job_posting_sources`

| Column | Type and constraint | Purpose |
| --- | --- | --- |
| `job_posting_id` | `uuid`, non-null foreign key | References `job_postings.id`. |
| `source_id` | `uuid`, non-null foreign key | References `sources.id`. |
| `last_seen_at` | `timestamptz`, non-null | Last ingestion containing this job. |

`(job_posting_id, source_id)` is the composite primary key. Add an index on
`source_id`. Use restrictive foreign-key deletion behavior; no relationship
deletes a job or source implicitly.

### Security, migration, and validation

- Enable RLS on all three tables. Create no policies and grant no browser
  access.
- Do not create views, functions, triggers, seed data, or extensions beyond
  what is required for UUID defaults.
- Source rows are application configuration, not schema seed data. Bootstrap
  them idempotently in phase 2.
- Develop locally, test using `supabase db reset`, commit the migration, then
  use one coordinated `supabase db push` for a hosted project. Never alter a
  hosted schema in the dashboard.
- Start the local stack, apply the migration, reset it from scratch, inspect
  tables/constraints/indexes/RLS, and run database advisors.

**Review checkpoint:** a clean `supabase db reset` produces the exact schema
above with no manual SQL.

## Phase 2: Core backend boundary

### Goal

Create the Python boundary around the migration-owned database. It connects,
bootstraps known sources, and exposes a safe manual command, but does not fetch
or parse GitHub content yet.

### Package and configuration layout

Create a `src/gradradar/` package:

- `settings.py`: Pydantic settings for `DATABASE_URL` and optional
  `GITHUB_TOKEN`.
- `db.py`: synchronous SQLAlchemy engine, session factory, and transaction
  lifecycle.
- `models.py`: typed SQLAlchemy mappings for the three migration tables.
- `source_config.py`: immutable typed source definitions.
- `bootstrap.py`: idempotent source-row creation.
- `cli.py`: manual commands only; no scheduling loop.

The two definitions are:

| Name | Repository | Branch | File | Parser | Priority |
| --- | --- | --- | --- | --- | --- |
| `simplify` | `SimplifyJobs/New-Grad-Positions` | `dev` | `README.md` | `simplify` | 1 |
| `speedyapply` | `speedyapply/2027-SWE-College-Jobs` | `main` | `NEW_GRAD_USA.md` | `speedyapply` | 2 |

### Dependencies, commands, and tests

- Add `psycopg` with `uv`; remove unused Alembic with `uv`; commit
  `uv.lock` in the same dependency commit.
- Use a synchronous SQLAlchemy engine. Batch ingestion has no need for async
  database access.
- Fail clearly when `DATABASE_URL` is absent or invalid. Never default to
  SQLite or a hosted database.
- Keep each database write in an explicit transaction, committing on success
  and rolling back on exception.
- Implement `bootstrap-sources`: insert the two configured sources by name
  when absent and leave existing rows unchanged.
- Implement placeholder `ingest`: verify configuration, open a session,
  bootstrap sources, and exit with a summary. It makes no HTTP request until
  phase 6.
- Unit-test settings and unique source definitions. Add a local-Supabase
  integration test proving bootstrapping twice creates exactly two rows.

**Review checkpoint:** the CLI connects locally and source bootstrap is
idempotent.

## Phase 3: Normalization and eligibility

### Goal

Build pure functions that decide whether a parsed row can be stored and which
job identity it represents. They have no HTTP or database dependency.

### Application-key normalization

Implement `normalize_apply_url(raw_url) -> str`. Keep the original URL in
`apply_url`; use only the result as `application_key`.

The deliberate aggressive policy is:

1. Trim whitespace and lowercase the candidate key.
2. Before generic cleanup, extract stable identifiers:
   - any `gh_jid` becomes `greenhouse-job-id:{value}`;
   - a Greenhouse `token` becomes `greenhouse-job-id:{value}`;
   - a Microsoft `pid` becomes `microsoft-job-id:{value}`;
   - an Ashby board/UUID job path becomes `ashby-job:{board}:{uuid}`.
3. Otherwise remove the complete query string and fragment.
4. Remove leading `www.`; normalize Greenhouse hosts to
   `boards.greenhouse.io`; normalize Workday locale prefixes; remove trailing
   slash and trailing `/apply`, `/application`, or `/detail`.
5. Reject empty, relative, malformed, and non-HTTP(S) URLs.

This may merge two URLs that differ in a meaningful query parameter. That
tradeoff is accepted. Every intended merge gets a test; every discovered false
merge requires a regression test before altering the rules.

### Listing date and U.S. eligibility

Implement `parse_tracker_age(age, reference_time) -> datetime | None`:

- Normalize the reference time to UTC.
- Support observed integer hours (`12h`), days (`3d`), and months
  (`1mo`); a month is exactly 30 days.
- Return `reference_time - duration` in UTC.
- Return `None` for blank, malformed, negative, or unsupported values.

Implement `classify_us_location(location) -> eligible | ineligible | unknown`:

- Preserve source text exactly.
- Eligible: `USA`, `United States`, U.S. states/DC, and the source aliases
  `NYC`, `SF`, `LA`; include clear U.S. remote strings.
- Ineligible: explicit non-U.S.-only locations such as Canada or UK.
- Multi-location: eligible if any location is clearly U.S.; otherwise unknown.
  Bare `Remote` and unknown cities are unknown.
- Persist eligible rows only. Log ineligible and unknown counts/reasons without
  adding an eligibility column or storing rejected rows.

Write table-driven tests for every identifier extraction, fallback cleanup,
invalid URL, supported age, timezone conversion, U.S. location, non-U.S.
location, multi-location, and ambiguous remote case.

**Review checkpoint:** all transformations are fixture-tested and pure before a
live source parser exists.

## Phase 4: Shared ingestion workflow

### Goal

Define one normalized input and persist it correctly regardless of source.

### Contract and persistence

Create a Pydantic `ParsedJobPosting` with:

- `source_name`;
- `company_name`;
- `title`;
- `apply_url`;
- `application_key`;
- `location`;
- `listed_at`.

It validates non-empty display fields, an HTTP(S) apply URL, and an aware UTC
`listed_at` when present. Parser HTML/Markdown, tracker age strings, and
GitHub response types never enter this model.

For each eligible posting, in one transaction:

1. Resolve the configured source and priority.
2. Find the job by unique `application_key`.
3. Insert it with a database UUID and `first_seen_at = now()` when absent.
4. When present, update display fields only if the incoming source has higher
   priority than the source currently determining the display values.
5. Insert a missing association or update only its `last_seen_at`.
6. Commit job and association together; never leave an orphaned association.

Do not delete jobs/links when a source drops a role. Do not fuzzy-match company,
title, or location; the application key is the sole cross-source merge rule.
The unique database constraint is the final concurrency guard.

Test same-source repeat ingestion, cross-source dedupe, lookalike distinct
URLs, immutable `first_seen_at`, source-link updates, priority conflicts, and
rollback on failure. Use local Supabase integration tests for upserts.

**Review checkpoint:** repeated synthetic ingestion creates one job with both
source associations and stable display fields.

## Phase 5: Source parsers

### Goal

Parse only intended new-grad SWE source scope, apply shared transformation
rules, and emit eligible `ParsedJobPosting` values without side effects.

### SpeedyApply

- Read only `main/NEW_GRAD_USA.md` from
  `speedyapply/2027-SWE-College-Jobs`.
- Never parse its README, internship file, or international files.
- Require the `2027 USA SWE New Graduate Positions` heading.
- Parse active Markdown tables under `FAANG+`, `Quant`, and `Other`.
  Trust the repository's own selection; do not invent a role-title classifier.
- Map fields by header name because `Other` lacks salary.
- Extract visible company, position, location, the first Posting-cell
  application anchor, and age.
- Fail the full source when required tables/columns are missing.

### Simplify

- Read only `dev/README.md` from `SimplifyJobs/New-Grad-Positions`.
- Locate `## 💻 Software Engineering New Grad Roles`; parse only its first
  active HTML table.
- Stop before `Inactive roles` and the Product Management heading. Ignore all
  other categories.
- Require Company, Role, Location, Application, and Age headers.
- Select an anchor whose image alt text is `Apply`; never the Simplify link.
  Skip locked `🔒` rows with no employer application URL.
- Inherit the prior company on `↳` continuation rows; skip a leading
  continuation row.
- Render `<br>` as newline. For `<details>`, retain actual location text,
  not only its summary count.

### Common behavior and tests

- Parsers accept raw source text plus an aware revision timestamp.
- They report parsed, eligible, ineligible, unknown, and malformed counts.
- A malformed row is skipped/reported; missing expected structure fails the
  complete parser before persistence.
- Parsers never fetch HTTP, open sessions, or write the database.
- Save local fixtures for normal U.S., non-U.S., U.S. remote, multi-location,
  malformed, continuation, inactive/locked, and unrelated-category examples.
- Parser tests use local fixtures; HTTP-client tests use `respx` and never
  contact GitHub.

**Review checkpoint:** both parsers select only their intended scopes, output
eligible U.S. roles, and fail safely on format drift.

## Phase 6: GitHub ingestion and worker

### Goal

Connect GitHub fetching, parsing, and persistence into a revision-aware manual
command that a later separate worker can run every 10 minutes.

### Fetching and state updates

1. For each configured source, call GitHub's commits API using branch and file
   path; read latest commit SHA and commit timestamp.
2. Compare the SHA with `sources.last_processed_revision_sha`.
3. If equal, report `unchanged` and make no parser or job writes.
4. If changed, download raw content at that exact SHA so content and
   `source_revision_at` match.
5. Parse, normalize, filter, and persist the source transactionally.
6. Only after complete success, update `last_processed_revision_sha` and
   `last_successful_sync_at`.
7. On fetch, validation, parser, or persistence failure, leave both unchanged,
   report the error, and continue with the other source.

Use optional `GITHUB_TOKEN` for production rate limits but support
unauthenticated local use. Retry transient GitHub failures with bounded
exponential backoff and jitter; never retry source-format validation failures.

### Safety, observability, and tests

- Reject a changed revision when eligible count falls by 80%+ from a previous
  count of at least 20. Log the prior/new counts and SHA; do not update source
  state. This protects format drift, not job deletion.
- `ingest` processes both sources and exits nonzero only if both fail. Its
  summary includes source, status, SHA, counts, and errors.
- Structured logs include source, SHA, duration, parsed/eligible/skipped
  counts, inserted/updated jobs, source-link updates, and errors. The lean MVP
  uses logs instead of a `fetch_runs` table.
- Integration tests mock GitHub metadata/raw responses with `respx` and use
  local Supabase. Cover unchanged SHA, changed SHA, failure isolation,
  retryable HTTP error, parse failure with no source-state update, suspicious
  row drop, and repeated success.
- Validate with pytest, Ruff, Pyright, pre-commit, clean `supabase db reset`,
  and a manual local ingestion run.

**Review checkpoint:** repeated runs skip unchanged sources, a broken source
does not block the other, and no duplicate job can be created.

## Commit boundaries

Commit contained, verified behavior in this order:

1. `chore(supabase): initialize local database configuration`
2. `feat(storage): add initial job posting schema`
3. `feat(storage): add sqlalchemy database boundary`
4. `feat(sources): add source bootstrap command`
5. `feat(normalization): add application key and age parsing`
6. `feat(eligibility): add us location filtering`
7. `feat(storage): add idempotent job persistence`
8. `feat(sources): add speedyapply parser`
9. `feat(sources): add simplify parser`
10. `feat(ingestion): add revision-aware github ingestion`

Tests for a behavior ship in its corresponding commit. Do not defer tests until
phase 6 or make one large backend commit.
