# GradRadar system design

## 1. Product goal and MVP boundary

GradRadar helps candidates find **new, U.S.-based, entry-level software
engineering jobs** from configured community trackers. Each current result
provides the source-supplied application link, company, title, location,
estimated listing time, first-seen time, and tracker source.

The target audience is full-time SWE new-grad roles for 2026 or 2027
bachelor's/master's graduates. Exclude PhD-specific roles.

The implemented backend is a public, read-only API with no user accounts. It
ingests only two GitHub repositories; the React website is the next phase. It
does not verify employer listings, create accounts, track applications, scrape
LinkedIn, submit applications, or send individual alerts.

### Product decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Source of truth | The two configured GitHub files | Every displayed row identifies its tracker source. |
| Source repos | SpeedyApply USA file and Simplify SWE table | Both have a maintained job table and direct apply links. |
| Storage | PostgreSQL | Durable dedupe, history, filtering, and subscriptions. |
| API | FastAPI | Matches the Python ingestion service and provides typed OpenAPI docs. |
| Web UI | React + TypeScript, planned | Responsive, filterable public feed. |
| First alert channel, after MVP | Telegram bot | Free, supports opt-in user chats, and is simple to ship. |
| Later alert channel | Discord bot, then email | Discord webhooks are ideal for a shared channel; per-user delivery needs a bot. |
| Do not support in MVP | Alerts, WhatsApp, and iMessage | Prove the feed before introducing notification complexity. |

Telegram's bot platform is free for users and developers. Discord incoming
webhooks are useful for broadcasting into one channel but do not provide
user-specific subscription management, so that needs a bot/OAuth flow when we
add it. [Telegram](https://core.telegram.org/bots),
[Discord](https://docs.discord.com/developers/platform/webhooks)

## 2. System shape

```mermaid
flowchart LR
  G[GitHub tracker files] --> P[Revision-aware parsers]
  P --> N[Normalize and US filter]
  N --> D[Deduplicate]
  D --> S[(PostgreSQL)]
  S --> A[FastAPI]
  A --> W[React website (planned)]
```

Each GitHub parser reads only a changed source revision, extracts its selected
job table, normalizes the result, applies the U.S. filter, and upserts it. A
current eligible job is then available through the API.

This cleanly separates three different facts:

- **Provenance:** a configured GitHub tracker mentioned the role.
- **Normalized job:** GradRadar's current record, potentially observed in both
  source repositories.

## 3. Ingestion and replication model

### Source registry

The registry has exactly two source files:

- [`speedyapply/2027-SWE-College-Jobs`](https://github.com/speedyapply/2027-SWE-College-Jobs),
  `main`, `NEW_GRAD_USA.md`
- [`SimplifyJobs/New-Grad-Positions`](https://github.com/SimplifyJobs/New-Grad-Positions),
  `dev`, `README.md`, Software Engineering section only

Each source has a GitHub repository, branch, file path, parser name, priority,
last successfully processed SHA, and last successful sync time.
Fetch source metadata first; download and parse the raw file only when the SHA
changes. This makes the scheduled run cheap and repeatable.

The parsers are intentionally separate because the formats differ:

- **SpeedyApply:** Markdown tables with company, position, location, salary,
  application link, and age.
- **Simplify:** HTML `<table>` rows inside Markdown; company cells may be blank
  `↳` continuation rows and application cells include both an apply link and a
  Simplify link. Prefer the link marked Apply and inherit the prior
  company for continuation rows.

### Polling rules

- Check both source files every 15 minutes from 7 AM through 8:45 PM Pacific,
  then every two hours overnight, using their commit/blob SHA; parse only
  changed files.
- Use bounded retries with exponential backoff. One failing source must not halt
  the run.
- Treat a parse as successful only if the expected table is found and basic
  structure checks pass.
- A job is current when at least one linked source saw it in that source's most
  recent successful sync. Preserve historical jobs, but return only current
  jobs from the public feed.

### Idempotency and deduplication

Each parsed posting is linked to its source through the composite
`job_posting_id + source_id` key. A repeat observation updates `last_seen_at`;
the initial job insert sets `first_seen_at`.

Deduplicate across the two sources only when normalized application URLs match.
Normalization removes fragments and known tracking parameters such as `utm_*`
and `ref`, while preserving job-identifying parameters such as `gh_jid`. For
the MVP, do not use fuzzy title/company/location matching; keep uncertain
lookalikes visible rather than accidentally hiding a real role.

## 4. Core data model

| Table | Important fields | Purpose |
| --- | --- | --- |
| `sources` | `id`, name, repository URL, last processed SHA, last successful sync | The two GitHub tracker files. |
| `job_postings` | normalized apply URL, title, company, location, estimated listing date, first seen | Normalized job state. |
| `job_posting_sources` | job, source, last seen, source position | Links a job to the trackers that have listed it and preserves its row order within each tracker. |

`job_postings.location` retains the source text as one opaque string. A job is
current when at least one `job_posting_sources.last_seen_at` matches its
source's `last_successful_sync_at`; otherwise it is historical and omitted from
the public feed.

The application URL is **source-supplied, not employer-verified**. The future
UI must label the external button "Open application link" rather than claim it
is an active official posting.

## 5. Matching rule

The product target is intentionally narrow:

1. **US scope:** include US cities, `United States`, and US-eligible remote;
   exclude explicitly non-US-only roles.
2. **Engineering family:** ingest only the SpeedyApply new-grad USA file and
   Simplify's Software Engineering section; do not add our own role-title
   classifier in the first milestone.
3. **New-grad level:** trust the source category in the first milestone. The
   UI must identify the source so users understand this is source-curated data.
   Include 2026 and 2027 bachelor's/master's new-grad roles; exclude
   PhD-specific roles.

Apply a deterministic U.S. filter: keep clearly U.S. locations and U.S. remote
roles; exclude clearly non-U.S. locations. Unknown or mixed locations are not
persisted. No LLM is needed.

## 6. API and website MVP

### Public API

- `GET /health` — service and database health.
- `GET /v1/jobs` — paginated feed; filters: `q`, `location`, `remote`,
  `posted_within_hours`, `listed_within_hours`, `company`, and repeatable
  `sources` values such as `sources=simplify&sources=speedyapply`; optional
  `sort_by` (`listed_at` or `company_name`) and `sort_direction` (`asc` or
  `desc`) control ordering. Results default to newest listed first. The default
  page is 50 jobs at `offset=0` and includes all sources.

`posted_within_hours` filters on `first_seen_at`; the UI should label it
"Found by GradRadar" rather than implying it is the employer's published
timestamp.

`listed_within_hours` filters by a rolling number of hours. The UI offers a
48-hour option for roles listed yesterday as well as today.

### Initial UI

One page is enough: freshness timestamp, search, location/remote filters, and
a newest-first job list. Each card shows company, role, location,
estimated listing time, GradRadar first-seen time, source, and an **Open
application link** button. Preserve query filters in the URL so a filtered feed
can be shared.

## 7. Notifications after the web MVP

This is deliberately out of scope until the feed works. Telegram is the first
implementation. A user opens the bot, sends `/start`,
and then selects basic preferences (US location/remote and immediate vs digest).
The service stores the Telegram chat ID only after that opt-in. When a job
first enters the public feed, it creates one outbox record per matching active
subscriber. A worker sends the message and records success/failure; retries
must reuse the same outbox row so a job is not repeatedly announced.

Start with a global US-new-grad feed and either no preferences or just remote
vs on-site. Do not build free-form keyword alerts, WhatsApp, Discord, and
iMessage together. That is product surface without proving the core feed is
accurate.

## 8. Requirements to keep us honest

### Functional requirements

- User can browse current matching jobs without creating an account.
- User can filter jobs by keyword, US location, remote status, company, and
  how recently GradRadar found them.
- User can open the source-supplied application link and see the tracker source
  for every displayed job.
- User can see when GradRadar first observed a role.

### Non-functional requirements

- The system should be able to detect a change to an onboarded source file
  within 15 minutes between 7 AM and 9 PM Pacific, and within two hours
  overnight, under normal operation.
- The system should be able to ingest repeated fetches idempotently and avoid
  duplicate job records.
- The system should be able to continue processing healthy sources when one
  source fails and expose its failure state.
- The system should be able to explain each displayed job with its source URL.
- The system should be able to reject a malformed source revision without
  removing currently displayed jobs.
- The system should be able to store secrets only in environment configuration,
  never in source control or the public API.

## 9. Open decisions

1. Is `remote in the US` eligible, and should location filters include visas or
   sponsorship only as a later metadata field?
2. Where do you want to deploy? A simple first choice is one API/worker service,
   managed Postgres, and a static frontend; the exact provider can wait until
   Phase 3.
