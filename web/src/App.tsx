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

function formatAge(value: string | null): string {
  if (!value) return "—";
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  return `${days}d ago`;
}

function displayText(value: string): string {
  const element = document.createElement("div");
  element.innerHTML = value;
  return element.textContent?.trim() || value;
}

function updateUrl(filters: JobFilters, replace = false): void {
  const url = `${window.location.pathname}${filtersToSearch(filters)}`;
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
}

function paginationItems(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const pages = new Set([1, 2, totalPages - 1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page > 0 && page <= totalPages) pages.add(page);
  }
  const sortedPages = [...pages].sort((left, right) => left - right);
  return sortedPages.flatMap((page, index) => {
    const previous = sortedPages[index - 1];
    return previous !== undefined && page - previous > 1 ? ["ellipsis", page] : [page];
  });
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
      .then((nextPage) => {
        const lastPage = Math.max(1, Math.ceil(nextPage.total / PAGE_SIZE));
        if (filters.page > lastPage) {
          const next = { ...filters, page: lastPage };
          setFilters(next);
          updateUrl(next, true);
          return;
        }
        setPage(nextPage);
      })
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

  function changeSort(sortBy: JobFilters["sortBy"]): void {
    const sortDirection =
      filters.sortBy === sortBy
        ? filters.sortDirection === "desc"
          ? "asc"
          : "desc"
        : sortBy === "company_name"
          ? "asc"
          : "desc";
    changeFilters({ sortBy, sortDirection });
  }

  const pageCount = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;
  const showInitialSkeleton = loading && page === null;

  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-[1800px] flex-1 px-5 py-5 sm:px-8">
        <header className="mb-5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-slate-200 pb-4">
          <div className="flex items-baseline gap-3">
            <h1 className="text-xl font-semibold tracking-tight">GradRadar</h1>
            <p className="text-sm text-slate-500">U.S. entry-level software engineering jobs</p>
          </div>
          <p className="text-sm text-slate-500">
            {page ? `${page.total} roles` : "Loading roles…"}
          </p>
        </header>

        <section aria-label="Feed filters" className="mb-3 border-b border-slate-200 pb-3">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[1.4fr_1fr_0.8fr_0.8fr_1.2fr]">
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
            <Field label="Listed within">
              <select
                value={filters.listedWithinHours}
                onChange={(event) => changeFilters({ listedWithinHours: event.target.value })}
              >
                <option value="">Any time</option>
                <option value="24">Past 24 hours</option>
                <option value="48">Past 48 hours</option>
                <option value="168">Past 7 days</option>
                <option value="720">Past 30 days</option>
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
        </section>

        {page && <Freshness sources={page.source_freshness} />}
        <section aria-live="polite" aria-busy={loading}>
          <div className="mb-2 flex items-center justify-between gap-4 text-sm text-slate-500">
            <p>{page ? `${page.total} matching jobs` : "Loading jobs…"}</p>
            {loading && page && <span>Refreshing…</span>}
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
            <div className="border border-dashed border-slate-300 p-10 text-center">
              <h2 className="text-lg font-semibold">No jobs match these filters.</h2>
              <button className="mt-3" onClick={() => changeFilters(defaultFilters)}>
                Clear filters
              </button>
            </div>
          )}
          {page?.items.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] table-fixed border-collapse text-left">
                <thead className="border-y border-slate-200 text-sm font-medium text-slate-500">
                  <tr>
                    <SortableHeader
                      className="w-[15%]"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Company"
                      onClick={() => changeSort("company_name")}
                      sortKey="company_name"
                    />
                    <th className="w-[37%] px-3 py-2 font-medium">Role</th>
                    <th className="w-[18%] px-3 py-2 font-medium">Location</th>
                    <SortableHeader
                      className="w-[10%]"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Listed"
                      onClick={() => changeSort("listed_at")}
                      sortKey="listed_at"
                    />
                    <th className="w-[10%] px-3 py-2 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((job) => (
                    <JobRow job={job} key={job.id} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>

        {page && page.total > 0 && (
          <nav
            aria-label="Job feed pages"
            className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4"
          >
            <p className="text-sm text-slate-500">
              Showing {(filters.page - 1) * PAGE_SIZE + 1}–
              {Math.min(filters.page * PAGE_SIZE, page.total)} of {page.total}
            </p>
            <div
              className="flex items-center gap-1"
              aria-label={`Page ${filters.page} of ${pageCount}`}
            >
              <button
                className="bg-transparent px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-950 disabled:bg-transparent disabled:text-slate-300"
                disabled={filters.page === 1}
                onClick={() => changePage(filters.page - 1)}
              >
                Previous
              </button>
              {paginationItems(filters.page, pageCount).map((item, index) =>
                item === "ellipsis" ? (
                  <span
                    className="px-1.5 text-slate-400"
                    key={`ellipsis-${index}`}
                    aria-hidden="true"
                  >
                    …
                  </span>
                ) : (
                  <button
                    aria-current={item === filters.page ? "page" : undefined}
                    className={
                      item === filters.page
                        ? "bg-slate-900 px-2.5 py-1.5 text-white hover:bg-slate-700"
                        : "bg-transparent px-2.5 py-1.5 text-blue-700 hover:bg-blue-50 hover:text-blue-900"
                    }
                    key={item}
                    onClick={() => changePage(item)}
                  >
                    {item}
                  </button>
                ),
              )}
              <button
                className="bg-transparent px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-950 disabled:bg-transparent disabled:text-slate-300"
                disabled={filters.page >= pageCount}
                onClick={() => changePage(filters.page + 1)}
              >
                Next
              </button>
            </div>
          </nav>
        )}
      </div>
      <footer className="border-t border-slate-200 px-5 py-5 sm:px-8">
        <div className="mx-auto max-w-[1800px] text-sm font-medium tracking-tight text-slate-400">
          © GradRadar
        </div>
      </footer>
    </main>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-xs font-medium text-slate-600">
      {label}
      {children}
    </label>
  );
}

function SortableHeader({
  className,
  currentSort,
  direction,
  label,
  onClick,
  sortKey,
}: {
  className: string;
  currentSort: JobFilters["sortBy"];
  direction: JobFilters["sortDirection"];
  label: string;
  onClick: () => void;
  sortKey: JobFilters["sortBy"];
}) {
  const isActive = currentSort === sortKey;
  return (
    <th
      aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}
      className={`${className} px-3 py-2 font-medium`}
    >
      <button
        className="bg-transparent p-0 text-slate-500 hover:bg-transparent hover:text-slate-950"
        onClick={onClick}
      >
        {label}
        {isActive && <span className="ml-1 text-xs">{direction === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}

function Freshness({ sources }: { sources: JobPage["source_freshness"] }) {
  return (
    <aside className="mb-3 text-xs text-slate-500" aria-label="Tracker freshness">
      <span>Tracker freshness: </span>
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

function JobRow({ job }: { job: JobPage["items"][number] }) {
  const companyName = displayText(job.company_name);

  return (
    <tr className="border-b border-slate-100 text-sm hover:bg-slate-50">
      <td className="truncate px-3 py-3 font-medium" title={companyName}>
        {companyName}
      </td>
      <td className="truncate px-3 py-3">
        <a
          href={job.apply_url}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-blue-700 no-underline hover:underline"
          aria-label={`Open application link for ${companyName}`}
          title={job.title}
        >
          {job.title}
        </a>
      </td>
      <td className="truncate px-3 py-3 text-slate-600" title={job.location}>
        {job.location}
      </td>
      <td className="px-3 py-3 text-slate-500" title={formatDate(job.listed_at)}>
        {formatAge(job.listed_at)}
      </td>
      <td
        className="truncate px-3 py-3 text-slate-500"
        title={job.sources.map((source) => sourceLabels[source.name]).join(", ")}
      >
        {job.sources.map((source, index) => (
          <span key={source.name}>
            {index > 0 && ", "}
            <a
              className="text-slate-500 no-underline hover:text-blue-700 hover:underline"
              href={source.url}
              target="_blank"
              rel="noreferrer"
            >
              {sourceLabels[source.name]}
            </a>
          </span>
        ))}
      </td>
    </tr>
  );
}

function Skeletons() {
  return (
    <div className="grid gap-0 border-y border-slate-200">
      {[1, 2, 3].map((number) => (
        <div className="h-11 animate-pulse border-b border-slate-100 bg-slate-50" key={number} />
      ))}
    </div>
  );
}
