# Public board investigation — October 28, 2026

The nine seed boards below returned valid public API responses when checked with
GradRadar's adapters. Counts are a snapshot, not a promise of current openings.
"Matching" means the initial conservative U.S. new-grad SWE filter accepted a
posting. A board with zero matches remains useful because future roles may match.

| Platform | Company | Board name | Open jobs | Matching | Board |
| --- | --- | --- | ---: | ---: | --- |
| Greenhouse | Stripe | `stripe` | 722 | 2 | https://job-boards.greenhouse.io/stripe |
| Greenhouse | Databricks | `databricks` | 902 | 2 | https://job-boards.greenhouse.io/databricks |
| Greenhouse | Coinbase | `coinbase` | 228 | 0 | https://job-boards.greenhouse.io/coinbase |
| Ashby | OpenAI | `openai` | 812 | 0 | https://jobs.ashbyhq.com/openai |
| Ashby | Notion | `notion` | 142 | 3 | https://jobs.ashbyhq.com/notion |
| Ashby | Ramp | `ramp` | 168 | 0 | https://jobs.ashbyhq.com/ramp |
| Lever | Palantir | `palantir` | 304 | 17 | https://jobs.lever.co/palantir |
| Lever | Shield AI | `shieldai` | 658 | 4 | https://jobs.lever.co/shieldai |
| Lever | Spotify | `spotify` | 89 | 0 | https://jobs.lever.co/spotify |

The API response fixtures in `tests/fixtures/*_board.json` retain just the
fields needed for offline parser tests. Greenhouse's list response includes an
update timestamp but no publication timestamp; Ashby includes `publishedAt`;
Lever's public list does not supply a publication timestamp.

Checked public endpoints:

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{board}`
- Lever: `https://api.lever.co/v0/postings/{board}?mode=json&skip=0&limit=100`

Other candidates checked but not seeded: Greenhouse Duolingo, Cloudflare, and
Reddit had no default-filter matches; Ashby Linear and Mercury had no matches;
Lever Anduril, Roblox, Plaid, and Affirm returned 404 for the tested board names.

## Additional boards identified — October 29, 2026

Following a review of a target-company list, these board references were added
to the seed config. They use supported adapters, but live API verification was
not available in the environment during this update. Counts and filter matches
are therefore not reported here; the first successful sync should confirm each
board before relying on it.

| Platform | Company | Board name | Board |
| --- | --- | --- | --- |
| Greenhouse | Cloudflare | `cloudflare` | https://job-boards.greenhouse.io/cloudflare |
| Greenhouse | Reddit | `reddit` | https://job-boards.greenhouse.io/reddit |
| Greenhouse | Waymo | `waymo` | https://job-boards.greenhouse.io/waymo |
| Greenhouse | CoreWeave | `coreweave` | https://job-boards.greenhouse.io/coreweave |
| Greenhouse | Brex | `brex` | https://job-boards.greenhouse.io/brex |
| Greenhouse | Dropbox | `dropbox` | https://job-boards.greenhouse.io/dropbox |
| Greenhouse | Twilio | `twilio` | https://job-boards.greenhouse.io/twilio |
| Greenhouse | SpaceX | `spacex` | https://job-boards.greenhouse.io/spacex |
| Greenhouse | Fivetran | `fivetran` | https://job-boards.greenhouse.io/fivetran |
| Greenhouse | Vercel | `vercel` | https://job-boards.greenhouse.io/vercel |
| Ashby | Mercury | `mercury` | https://jobs.ashbyhq.com/mercury |
| Lever | Mistral AI | `mistral-ai` | https://jobs.lever.co/mistral-ai |

## Failed source URL corrections — October 29, 2026

The Supabase `sources` table reported 404 sync failures for several existing
sources. Domino Data Lab's Greenhouse board is `dominodatalab`, and SambaNova's
is `sambanovasystems`; both corrected API URLs returned HTTP 200 with job
listings. Their seed entries and source rows were updated. The remaining failed
sources need further investigation before changing their platform or board.
