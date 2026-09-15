# GradRadar

**GradRadar is a focused job radar for U.S. entry-level software engineering
roles.** It turns fast-moving community job trackers into one clean, searchable
feed so new graduates can spend less time checking spreadsheets and more time
applying to relevant roles.

## Access

- [Live product](https://gradradar-qikp9zcmp-jianingxu.vercel.app) *(currently protected by Vercel sign-in)*
- [Source code](https://github.com/jianingxu1/grad-radar)

## The problem

New-grad SWE openings can appear and disappear quickly, while job seekers often
have to search several large, frequently changing trackers to find them. That
makes it easy to miss a role, revisit the same posting, or lose track of where
an application link came from.

GradRadar narrows that search to U.S. entry-level SWE roles and makes each
listing easy to scan, filter, and open.

## What it does

- Shows a public feed of current U.S. entry-level software engineering jobs.
- Lets candidates search by company or role and filter by location, remote
  status, posting recency, and tracker source.
- Preserves the application link and source for every job, so candidates can
  quickly check the original listing before applying.
- Shows when a source was last refreshed and when GradRadar first saw a role.

GradRadar is built for bachelor’s and master’s new graduates looking for
full-time SWE roles in the United States. It is a discovery tool: it does not
submit applications or claim to verify employer listings.

## How it works

GradRadar checks two curated GitHub job trackers—
[SpeedyApply](https://github.com/speedyapply/2027-SWE-College-Jobs) and
[Simplify](https://github.com/SimplifyJobs/New-Grad-Positions)—on a schedule.
When either tracker changes, the backend parses its job table, keeps eligible
U.S. entry-level roles, normalizes application URLs, and deduplicates matching
postings. The resulting records are stored in PostgreSQL and served to the web
app through an API.

```text
GitHub trackers → parser and filters → URL deduplication → PostgreSQL → public job feed
```

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python 3.13, FastAPI, SQLAlchemy
- **Data and scheduling:** PostgreSQL/Supabase, APScheduler
- **Data ingestion:** GitHub API, HTTPX, Beautiful Soup
- **Authentication:** Supabase Auth with Google sign-in

## Project structure

- `src/app/` — ingestion pipeline, API, scheduler, and database access
- `web/` — React job-feed interface
- `supabase/` — PostgreSQL schema migrations
- `docs/` — system design and product decisions
