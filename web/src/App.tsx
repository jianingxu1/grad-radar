import { useEffect, useState, type ReactNode } from "react";

import { fetchJobs, PAGE_SIZE, type JobFilters, type JobPage, type SourceName } from "./api";
import { defaultFilters, filtersFromSearch, filtersToSearch } from "./filterState";

const sourceLabels: Record<SourceName, string> = {
  simplify: "Simplify",
  speedyapply: "SpeedyApply",
};

function formatDate(value: string | null): string {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function updateUrl(filters: JobFilters, replace = false): void {
  const url = `${window.location.pathname}${filtersToSearch(filters)}`;
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
}

export function App() {
  const [filters, setFilters] = useState<JobFilters>(() =>
    filtersFromSearch(window.location.search),
  );
  const [page, setPage] = useState<JobPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void fetchJobs(filters, controller.signal)
      .then(setPage)
      .catch((reason: unknown) => {
        if ((reason as Error).name !== "AbortError") setError((reason as Error).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [filters, retry]);

  useEffect(() => {
    const onPopState = () => {
      setLoading(true);
      setError(null);
      setFilters(filtersFromSearch(window.location.search));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function changeFilters(changes: Partial<JobFilters>): void {
    const next = { ...filters, ...changes, page: 1 };
    setLoading(true);
    setError(null);
    setFilters(next);
    updateUrl(next, true);
  }

  function toggleSource(source: SourceName): void {
    const sources = filters.sources.includes(source)
      ? filters.sources.filter((value) => value !== source)
      : [...filters.sources, source];
    changeFilters({ sources });
  }

  function changePage(nextPage: number): void {
    const next = { ...filters, page: nextPage };
    setLoading(true);
    setError(null);
    setFilters(next);
    updateUrl(next);
  }

  const pageCount = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;
  const showInitialSkeleton = loading && page === null;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 max-w-3xl">
          <p className="mb-2 text-sm font-semibold tracking-wide text-indigo-700">GRADRADAR</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Find your next SWE role.
          </h1>
          <p className="mt-3 text-lg leading-8 text-slate-600">
            U.S. entry-level software engineering jobs curated by community trackers.
          </p>
        </header>

        <section
          aria-label="Feed filters"
          className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Field label="Search">
              <input
                value={filters.q}
                onChange={(event) => changeFilters({ q: event.target.value })}
                placeholder="Company or role"
              />
            </Field>
            <Field label="Location">
              <input
                value={filters.location}
                onChange={(event) => changeFilters({ location: event.target.value })}
                placeholder="e.g. New York"
              />
            </Field>
            <Field label="Workplace">
              <select
                value={filters.remote}
                onChange={(event) =>
                  changeFilters({ remote: event.target.value as JobFilters["remote"] })
                }
              >
                <option value="">All locations</option>
                <option value="true">Remote</option>
                <option value="false">On-site or hybrid</option>
              </select>
            </Field>
            <Field label="Tracker source">
              <div className="flex min-h-10 items-center gap-4">
                {(Object.keys(sourceLabels) as SourceName[]).map((source) => (
                  <label className="flex items-center gap-2 text-sm text-slate-700" key={source}>
                    <input
                      checked={filters.sources.includes(source)}
                      onChange={() => toggleSource(source)}
                      type="checkbox"
                    />
                    {sourceLabels[source]}
                  </label>
                ))}
              </div>
            </Field>
          </div>
          <details className="mt-4 border-t border-slate-100 pt-4">
            <summary className="cursor-pointer text-sm font-medium text-indigo-700">
              More filters
            </summary>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Field label="Company">
                <input
                  value={filters.company}
                  onChange={(event) => changeFilters({ company: event.target.value })}
                  placeholder="e.g. Figma"
                />
              </Field>
              <Field label="Found by GradRadar">
                <select
                  value={filters.postedWithinHours}
                  onChange={(event) => changeFilters({ postedWithinHours: event.target.value })}
                >
                  <option value="">Any time</option>
                  <option value="24">Past 24 hours</option>
                  <option value="72">Past 3 days</option>
                  <option value="168">Past 7 days</option>
                </select>
              </Field>
              <Field label="Estimated listing age">
                <select
                  value={filters.listedWithinDays}
                  onChange={(event) => changeFilters({ listedWithinDays: event.target.value })}
                >
                  <option value="">Any time</option>
                  <option value="1">Past day</option>
                  <option value="7">Past week</option>
                  <option value="30">Past month</option>
                </select>
              </Field>
            </div>
          </details>
        </section>

        {page && <Freshness sources={page.source_freshness} />}
        <section aria-live="polite" aria-busy={loading}>
          <div className="mb-4 flex items-center justify-between gap-4">
            <p className="text-sm text-slate-600">
              {page ? `${page.total} matching jobs` : "Loading jobs…"}
            </p>
            {loading && page && <span className="text-sm text-slate-500">Refreshing…</span>}
          </div>
          {error && (
            <div
              className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900"
              role="alert"
            >
              <p>{error}</p>
              <button
                className="mt-3"
                onClick={() => {
                  setLoading(true);
                  setError(null);
                  setRetry((value) => value + 1);
                }}
              >
                Try again
              </button>
            </div>
          )}
          {showInitialSkeleton && <Skeletons />}
          {!loading && !error && page?.items.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
              <h2 className="text-lg font-semibold">No jobs match these filters.</h2>
              <button className="mt-3" onClick={() => changeFilters(defaultFilters)}>
                Clear filters
              </button>
            </div>
          )}
          {page?.items.length ? (
            <div className="grid gap-4">
              {page.items.map((job) => (
                <JobCard job={job} key={job.id} />
              ))}
            </div>
          ) : null}
        </section>

        {page && page.total > 0 && (
          <nav aria-label="Job feed pages" className="mt-8 flex items-center justify-between">
            <button disabled={filters.page === 1} onClick={() => changePage(filters.page - 1)}>
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Page {filters.page} of {pageCount}
            </span>
            <button
              disabled={filters.page >= pageCount}
              onClick={() => changePage(filters.page + 1)}
            >
              Next
            </button>
          </nav>
        )}
      </div>
    </main>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-700">
      {label}
      {children}
    </label>
  );
}

function Freshness({ sources }: { sources: JobPage["source_freshness"] }) {
  return (
    <aside
      className="mb-5 rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-950"
      aria-label="Tracker freshness"
    >
      <span className="font-semibold">Tracker freshness: </span>
      {sources.map((source, index) => (
        <span key={source.name}>
          {index > 0 && " · "}
          <a href={source.url} target="_blank" rel="noreferrer">
            {sourceLabels[source.name]}
          </a>
          {": "}
          {source.last_successful_sync_at
            ? formatDate(source.last_successful_sync_at)
            : "not synced yet"}
        </span>
      ))}
    </aside>
  );
}

function JobCard({ job }: { job: JobPage["items"][number] }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col justify-between gap-4 sm:flex-row">
        <div>
          <p className="text-sm font-semibold text-indigo-700">{job.company_name}</p>
          <h2 className="mt-1 text-xl font-semibold">{job.title}</h2>
          <p className="mt-2 text-slate-600">{job.location}</p>
        </div>
        <a className="button-primary h-fit" href={job.apply_url} target="_blank" rel="noreferrer">
          Open application link <span className="sr-only">for {job.company_name}</span>
        </a>
      </div>
      <div className="mt-5 grid gap-2 border-t border-slate-100 pt-4 text-sm text-slate-600 sm:grid-cols-3">
        <p>
          <span className="font-medium text-slate-800">Estimated listing:</span>{" "}
          {formatDate(job.listed_at)}
        </p>
        <p>
          <span className="font-medium text-slate-800">Found by GradRadar:</span>{" "}
          {formatDate(job.first_seen_at)}
        </p>
        <p>
          <span className="font-medium text-slate-800">Sources:</span>{" "}
          {job.sources.map((source, index) => (
            <span key={source.name}>
              {index > 0 && ", "}
              <a className="underline" href={source.url} target="_blank" rel="noreferrer">
                {sourceLabels[source.name]}
              </a>
            </span>
          ))}
        </p>
      </div>
    </article>
  );
}

function Skeletons() {
  return (
    <div className="grid gap-4">
      {[1, 2, 3].map((number) => (
        <div className="h-44 animate-pulse rounded-2xl bg-slate-200" key={number} />
      ))}
    </div>
  );
}
