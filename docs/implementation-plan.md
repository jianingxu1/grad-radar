# GradRadar implementation plan

This is the remaining-work checklist. The system design describes the current
architecture; this file tracks delivery progress.

## Phase 0 — validate the input

- [x] Register the two GitHub source files and their branches.
- [x] Save fixtures for U.S., non-U.S., remote, malformed, and Simplify
  continuation rows.
- [x] Define and test normalized parser output.

## Phase 1 — reliable ingestion

- [x] Create Supabase migrations and SQLAlchemy mappings.
- [x] Configure database settings, sessions, and source bootstrap.
- [x] Parse the selected SpeedyApply and Simplify sections.
- [x] Normalize application URLs, estimate listing dates, and filter to clearly
  U.S.-eligible locations.
- [x] Deduplicate by application key and retain source associations.
- [x] Fetch GitHub revisions, skip unchanged sources, retry transient failures,
  and isolate a failing source.
- [x] Retain historical jobs while deriving current jobs from the latest
  successful source sync.

## Phase 2 — public API

- [x] Add `GET /health` with a database check.
- [x] Add `GET /v1/jobs` with pagination, search, company, location, remote,
  first-seen, listing-age, and source filters.
- [x] Return only jobs present in at least one source's latest successful sync.
- [x] Return the source-supplied application URL and tracker source for each
  job.

## Phase 3 — website

- [x] Build the React and TypeScript read-only feed.
- [x] Add URL-backed filters, loading/empty/error states, and accessibility
  basics.
- [x] Show clear freshness and source-supplied-link labels.
- [ ] Deploy the API, scheduled ingestion worker, PostgreSQL database, and
  static frontend with health monitoring.

## Phase 4 — subscriptions

- [ ] Build Telegram opt-in, preferences, unsubscribe, and delivery worker.
- [ ] Add subscriber, outbox, and delivery tables.
- [ ] Add idempotent delivery, retries, rate limits, and opt-out handling.

## Phase 5 — coverage and quality

- [ ] Add a human review path for unknown locations and source failures.
- [ ] Track source freshness, failures, duplicates, and source disagreement.
- [ ] Decide whether official ATS enrichment is worthwhile.

## Deferred

- Supabase Auth and direct browser access to Supabase.
- Sponsorship metadata and employer-verified publication dates.
- Discord, email, WhatsApp, and iMessage notifications.
