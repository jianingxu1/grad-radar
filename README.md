# GradRadar

GradRadar is a job-discovery service for U.S. bachelor’s and master’s new
graduates seeking software engineering roles. Its MVP ingests two curated
GitHub tracker files, normalizes their current U.S. listings, deduplicates
matching application links, and presents a fresh public feed.

The current product plan is in [docs/system-design.md](docs/system-design.md).
The first implementation milestone is revision-aware source ingestion and
idempotent PostgreSQL storage; the public API and website follow after that.
