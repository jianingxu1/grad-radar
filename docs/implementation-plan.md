# GradRadar implementation plan

This plan turns the current system design into an MVP in small, reviewable
steps. It deliberately proves data quality and idempotent storage before adding
an API or website.

## Confirmed decisions

1. **Database access:** GradRadar tables live in Supabase's `public` schema.
   Row Level Security (RLS) is enabled on every table, with no `anon` or
   `authenticated` policies in the MVP. The Python backend connects directly
   to PostgreSQL; the browser uses the future FastAPI API rather than
   Supabase's Data API.
2. **Listing date:** GitHub trackers supply relative ages such as `3d`, not an
   authoritative employer publication time. The parser will calculate
   `listed_at` as `source_revision_at - age`. It is an estimate and must not be
   described as an employer-verified posting date.
3. **Schema ownership:** Supabase SQL migrations are the sole schema history.
   SQLAlchemy maps and queries the tables but never creates or migrates them.

## Target model

### `public.job_postings`

| Column | Purpose |
| --- | --- |
| `id` | Database-generated UUID primary key. |
| `application_key` | Normalized application URL, stored as text and unique. Used for cross-source deduplication. |
| `company_name` | Displayed company name. |
| `title` | Displayed role title. |
| `apply_url` | Source-supplied URL opened by the user. |
| `location` | Source-provided location text. It remains a single opaque string; no location splitting or normalization occurs in the MVP. |
| `listed_at` | Nullable estimated listing timestamp. |
| `first_seen_at` | Exact timestamp when GradRadar first stored the posting. |

### `public.sources`

| Column | Purpose |
| --- | --- |
| `id` | Database-generated UUID primary key. |
| `name` | Unique stable source name, initially `speedyapply` or `simplify`. |
| `url` | Direct GitHub URL for the configured tracker file. |
| `last_successful_sync_at` | Most recent completed ingestion of this source. Used with source links to derive whether a posting is still present. |

### `public.job_posting_sources`

| Column | Purpose |
| --- | --- |
| `job_posting_id` | Foreign key to `job_postings.id`. |
| `source_id` | Foreign key to `sources.id`. |
| `last_seen_at` | Last successful ingestion that included this posting in this source. |

`(job_posting_id, source_id)` is the composite primary key. It prevents the
same source from being linked to the same posting more than once. A posting is
currently represented in a source when its `last_seen_at` matches that source's
most recent successful sync; this is derived rather than stored as an `active`
column.

## Implementation sequence

### 1. Bootstrap the local database environment

- Install Docker Desktop. It is required by `supabase start` and is not
  currently installed on the development machine.
- Initialize the repository as a Supabase project.
- Add the generated `supabase/` configuration to Git.
- Document local prerequisites, including Docker and the Supabase CLI.
- Add a committed `.env.example` with placeholder database URLs only. Keep the
  real `.env` ignored; never add a project URL, password, or service-role key
  to Git.

**Done when:** a contributor can start the local Supabase stack and retrieve
the local database connection string. Writing migration files may begin before
Docker is installed, but local application and migration validation cannot.

### 2. Create and validate the first database migration

- Create the migration using `supabase migration new`.
- Create the three tables above in the `public` schema.
- Add UUID defaults, foreign keys, `NOT NULL` constraints, a unique
  `application_key`, and useful lookup indexes.
- Enable RLS on every table. Do not create browser-access policies yet.
- Apply the migration locally with `supabase db reset` and inspect the
  resulting schema.
- Commit migration files to Git. Deploy only committed migrations with one
  controlled `supabase db push`; do not change the hosted schema manually.

**Done when:** a fresh local reset produces the three tables, their constraints,
and RLS configuration without manual SQL.

### 3. Add the Python database boundary

- Add the PostgreSQL driver (`psycopg`) through `uv` and commit `uv.lock`.
- Add settings that read `DATABASE_URL` from `.env`.
- Configure a SQLAlchemy engine and session factory.
- Add SQLAlchemy mappings for the migration-owned tables.
- Do not add Alembic or use `metadata.create_all()`.

**Done when:** a focused integration test can connect to local PostgreSQL and
read a test source through SQLAlchemy.

### 4. Implement pure normalization and parsing utilities

- Implement `normalize_apply_url(url) -> application_key`.
- Remove fragments and known `utm_*` parameters, preserve unknown parameters
  and job identifiers, and sort remaining query parameters.
- Implement `parse_tracker_age(age, reference_time) -> listed_at`.
- Handle unknown or malformed ages by returning `None` rather than guessing.
- Add unit tests for each rule.

**Done when:** equivalent tracker URLs produce the same key, while URLs that
only look similar remain distinct.

### 5. Define the normalized parsed-posting contract

- Add a Pydantic model for the data each source parser returns.
- Include company name, title, apply URL, location text, estimated `listed_at`,
  and source name.
- Keep parser-specific HTML and tracker formatting outside this contract.

**Done when:** fixtures from both trackers can be represented by the same
validated Python object.

### 6. Implement idempotent persistence

- Find or create a `job_postings` record by `application_key`.
- Update the display fields from the latest observed source row.
- Register the two configured sources through application configuration or a
  bootstrap command, rather than a schema migration.
- Create the corresponding `job_posting_sources` association if absent.
- Update its `last_seen_at` on every successful observation.
- Test re-ingestion and cross-source deduplication.

**Done when:** ingesting the same posting twice creates one job; ingesting the
same normalized URL from both sources creates one job with two source links.

### 7. Build source parsers using saved fixtures

- Start with SpeedyApply's Markdown table.
- Add Simplify's HTML table, retaining multi-location cells as one location
  string and choosing the employer Apply link over the secondary Simplify link.
- Save representative fixtures: normal US role, non-US role, remote role,
  multi-location role, and malformed row.
- Mock all HTTP calls in tests with `respx`.

**Done when:** both parsers produce the shared parsed-posting contract from
saved fixtures without network access.

### 8. Add revision-aware GitHub ingestion

- Fetch the configured source-file metadata and revision SHA.
- Download and parse only when the revision changes.
- Record successful and failed sync attempts.
- Keep one source failure from blocking the other.
- Feed parsed rows through the persistence workflow.

**Done when:** a no-change run avoids unnecessary parsing, and a changed source
updates the expected records without duplication.

### 9. Verify the ingestion milestone

- Run unit tests, parser tests, and a local PostgreSQL integration test.
- Run formatting, linting, type checking, and pre-commit.
- Inspect database constraints and source/job links manually.

**Done when:** the same fixture set can be ingested repeatedly with stable
records and explainable source links.

### 10. Build the public read path

- Add FastAPI endpoints for health, paginated job listings, one job, and filter
  metadata.
- Return a job's source names and URLs from the association table.
- Keep database credentials and Supabase secrets on the backend only.
- Build the React feed after the API contract is tested.

**Done when:** a user can browse a current job feed and see where every result
came from.

## Deferred work

- Supabase Auth, direct browser access to Supabase, RLS policies for users, and
  subscriptions are intentionally deferred.
- If direct browser access is introduced later, add explicit RLS policies
  before allowing any browser access.
- Official ATS enrichment, sponsorship data, and employer-verified publication
  dates are also deferred.
