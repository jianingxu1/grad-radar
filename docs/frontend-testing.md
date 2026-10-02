# Test frontend changes locally

1. From the repo root, install dependencies if needed, then start the API and
   frontend in separate terminals. The API needs the local `.env` database
   settings.

   ```bash
   uv sync
   npm --prefix web ci
   uv run uvicorn app.main:app --reload
   npm --prefix web run dev
   ```

2. Check that `http://127.0.0.1:8000/v1/jobs` returns data. Confirm `npx` is
   available, then open the frontend with the Playwright CLI skill:

   ```bash
   curl -fsS 'http://127.0.0.1:8000/v1/jobs?limit=1'
   command -v npx
   PWCLI="$HOME/.codex/skills/playwright/scripts/playwright_cli.sh"
   "$PWCLI" -s=gradradar open http://localhost:5173/ --headed
   "$PWCLI" -s=gradradar snapshot
   ```

3. Use refs from the latest snapshot to test the changed flow. For feed changes,
   check search, date and source filters, sorting, pagination, empty results,
   and Clear filters. Check FAQ and Notifications navigation when relevant.
   Snapshot again after navigation or a major UI change. Reload a direct URL to
   check that it still works.

4. Check a mobile width and the browser console. Save screenshots under
   `output/playwright/` when a visual issue needs evidence.

   ```bash
   "$PWCLI" -s=gradradar resize 390 844
   "$PWCLI" -s=gradradar snapshot
   "$PWCLI" -s=gradradar console
   "$PWCLI" -s=gradradar eval '({viewport:innerWidth,page:document.documentElement.scrollWidth})'
   ```

5. Run `npm --prefix web run test`, `npm --prefix web run lint`, and
   `npm --prefix web run build`. Close Playwright with
   `"$PWCLI" -s=gradradar close` and stop both servers.

Google sign-in and signed-in notification flows need valid local Supabase and
Google client settings; a placeholder Google client ID produces expected
console errors and cannot validate auth.
