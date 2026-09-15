# GradRadar

GradRadar helps U.S. new grads find software engineering roles early by putting new listings from multiple job trackers into one place.

[Live website](https://gradradar-web.vercel.app)

<!-- Add docs/images/gradradar-feed.png here after the deployed feed has listings. -->

## Why I built this

As a CS student looking for new-grad positions, I kept hearing the same advice: apply early. Once a role has thousands of applications, getting an interview is already harder; applying late makes it even harder.

I built GradRadar so I could check one place for new, deduplicated listings instead of manually refreshing several trackers. The goal is also to send alerts for new postings through Telegram, WhatsApp, and Discord, so candidates do not miss an opportunity because they saw it too late.

## Tech stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic
- **Data and jobs:** PostgreSQL/Supabase, GitHub API, HTTPX, APScheduler
- **Testing:** pytest, respx, Vitest, Testing Library

## What it does

- Ingests new-grad SWE listings from the [SpeedyApply](https://github.com/speedyapply/2027-SWE-College-Jobs) and [Simplify](https://github.com/SimplifyJobs/New-Grad-Positions) GitHub trackers.
- Keeps clearly U.S.-eligible roles, normalizes application URLs, and uses those URLs to deduplicate the same job across sources.
- Stores the result and displays it in a searchable, filterable website with the original application link and tracker source.
- Will let users opt in to alerts for new postings through Telegram first, then Discord and WhatsApp.

## Roadmap

- [x] Ingest the SpeedyApply and Simplify new-grad trackers.
- [x] Filter clearly U.S.-eligible SWE roles and normalize application links.
- [x] Deduplicate listings by normalized application URL while retaining their tracker source.
- [x] Build a searchable, filterable web feed and a read-only API.
- [x] Add optional Google sign-in.
- [ ] Run the ingestion worker and database reliably in production, with health monitoring.
- [ ] Build opt-in Telegram alerts, including preferences, unsubscribe, retries, and duplicate-safe delivery.
- [ ] Add Discord and WhatsApp notification channels.
- [ ] Ingest postings directly from ATS platforms such as Ashby and Greenhouse.
