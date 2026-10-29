# GradRadar system design

GradRadar is a public feed of U.S. new-grad and early-career software engineering jobs. The backend ingests two community GitHub trackers and configured company boards on Greenhouse, Ashby, Lever, Oracle Recruiting, and SmartRecruiters. The React site exposes a feed and a public Sources page. Google sign-in through Supabase Auth lets users manage Telegram notifications; source management is limited to allowlisted admins.

## Sources and ingestion

The `sources` table holds each source's platform, board name, company, enabled state, filter, priority, last successful sync, and sync status. The two GitHub rows retain their existing IDs. Company boards are bootstrapped from `src/app/sources/seed_boards.py`; the [board investigation](source-board-investigation-2026-10-28.md) records the initial API verification.

Railway runs `python -m app.cli ingest` every 15 minutes. The worker bootstraps the two GitHub sources and configured company boards, fetches enabled sources independently, stores normalized jobs, and delivers pending Telegram notifications. GitHub parsers fetch changed revisions of the configured files. Company-board adapters call public, server-built API URLs and validate Greenhouse, Ashby, Lever, Oracle, or SmartRecruiters responses. Lever, Oracle, and SmartRecruiters results are paginated. Oracle sources store their tenant hostname and career-site number in `platform_config`; the seeded Uber source uses `iaziqy.fa.ocs.oraclecloud.com` and `CX_1`. SmartRecruiters list titles are checked against role and exclusion terms before details are fetched for possible matches. Details provide descriptions and application URLs; the full board filter still runs on those details. A valid empty board is a successful sync. A failed fetch or parse leaves existing job links untouched and records the error.

Board listings pass through the source's editable filter. The default requires a U.S. location, a full-time SWE title, and an explicit new-grad or early-career level; it excludes internships and senior roles. Ambiguous roles are omitted. A successful board sync marks roles absent from its current filtered result inactive. GitHub links remain active after a role disappears from a tracker. A job stays in the feed while at least one enabled source has an active link.

## Jobs, provenance, and alerts

`job_postings` holds one normalized job per application identity. `job_posting_sources` holds each source's original application link, last observation, order, and active state. Deduplication first matches normalized application URLs and then stable Greenhouse, Ashby, or Lever posting IDs from alternate URL forms. It does not merge roles by similar titles. Both source links remain visible on a merged job, regardless of ingestion order.

New jobs from a board's first successful sync appear in the feed without alerts. Later new jobs enqueue Telegram notifications. A second source for an existing job does not enqueue another alert. Outbox rows provide retryable delivery.

## API and website

- `GET /v1/jobs` returns the paginated public feed, with search, location, company, recency, source, and sort filters.
- `GET /v1/sources` lists GitHub and company-board sources with sync details.
- `POST /v1/sources` and `PATCH /v1/sources/{id}` create or update company boards for admins. New and re-enabled boards are verified against their public API. GitHub sources cannot be edited through these endpoints.
- `GET /v1/me/source-admin` tells an authenticated user whether the server's `SOURCE_ADMIN_USER_IDS` allowlist grants source management.

The public `/sources` page shows all sources and their status. Admins can add Greenhouse, Ashby, Lever, Oracle Recruiting, or SmartRecruiters boards and edit their filters. Oracle configuration requires an Oracle Cloud tenant hostname and a site number such as `CX_1`. The feed loads available source choices from the API and shows each job's source-provided links.

## Release order

Apply all SQL migrations, including `20261029000002_oracle_recruiting_sources.sql`, before deploying the updated worker and API. Set `SOURCE_ADMIN_USER_IDS` in Railway to the intended Supabase Auth user UUIDs. Deploy the website after the API. Inspect the first sync of each seeded board; this initial backlog must not trigger alerts.
