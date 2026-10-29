import type { JobFilters, JobPage } from "../api";
import { formatDate, sourceLabel } from "./format";

export function JobFeed({
  page,
  loading,
  error,
  filters,
  onRetry,
  onClearFilters,
  onSort,
}: {
  page: JobPage | null;
  loading: boolean;
  error: string | null;
  filters: JobFilters;
  onRetry: () => void;
  onClearFilters: () => void;
  onSort: (sortBy: JobFilters["sortBy"]) => void;
}) {
  const showInitialSkeleton = loading && page === null;
  return (
    <>
      {page && <Freshness sources={page.source_freshness} />}
      <section aria-live="polite" aria-busy={loading}>
        <div className="mb-2 flex items-center justify-between gap-4 text-sm text-slate-500">
          <p>{page ? `${page.total} matching jobs` : "Loading jobs…"}</p>
          {loading && page && <span>Refreshing…</span>}
        </div>
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900" role="alert">
            <p>{error}</p>
            <button className="mt-3" onClick={onRetry}>
              Try again
            </button>
          </div>
        )}
        {showInitialSkeleton && <Skeletons />}
        {!loading && !error && page?.items.length === 0 && (
          <div className="border border-dashed border-slate-300 p-10 text-center">
            <h2 className="text-lg font-semibold">No jobs match these filters.</h2>
            <button className="mt-3" onClick={() => onClearFilters()}>
              Clear filters
            </button>
          </div>
        )}
        {page?.items.length ? (
          <div>
            <p className="mb-2 text-xs text-slate-500 md:hidden">
              Swipe across the table to see all columns.
            </p>
            <div
              aria-label="Job listings, scroll horizontally to see all columns"
              className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
              role="region"
              tabIndex={0}
            >
              <table className="w-full min-w-[700px] table-fixed border-collapse text-left text-xs lg:min-w-[900px] lg:text-sm">
                <thead className="border-y border-slate-200 font-medium text-slate-500">
                  <tr>
                    <SortableHeader
                      className="w-[16%]"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Company"
                      onClick={() => onSort("company_name")}
                      sortKey="company_name"
                    />
                    <th className="w-[32%] px-3 py-2 font-medium">Role</th>
                    <th className="w-[18%] px-3 py-2 font-medium">Location</th>
                    <SortableHeader
                      className="w-[10%]"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Listed"
                      onClick={() => onSort("listed_at")}
                      sortKey="listed_at"
                    />
                    <th className="w-[24%] px-3 py-2 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((job) => (
                    <JobRow job={job} key={job.id} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </>
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
        className="bg-transparent p-0 text-xs text-slate-500 hover:bg-transparent hover:text-slate-950 lg:text-sm"
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
    <aside className="mb-3 text-xs text-slate-500" aria-label="Source freshness">
      <span>Source freshness: </span>
      {sources.map((source, index) => (
        <span key={source.name}>
          {index > 0 && " · "}
          <a href={source.url} target="_blank" rel="noreferrer">
            {sourceLabel(source.name)}
          </a>
          {": "}
          {source.last_successful_sync_at
            ? formatDate(source.last_successful_sync_at)
            : "not checked yet"}
        </span>
      ))}
    </aside>
  );
}

function JobRow({ job }: { job: JobPage["items"][number] }) {
  const companyName = displayText(job.company_name);

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="break-words px-3 py-3 font-medium" title={companyName}>
        {companyName}
      </td>
      <td className="break-words px-3 py-3">
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
      <td className="break-words px-3 py-3 text-slate-600" title={job.location}>
        {job.location}
      </td>
      <td className="px-3 py-3 text-slate-500" title={formatDate(job.listed_at)}>
        {formatAge(job.listed_at)}
      </td>
      <td
        className="break-words px-3 py-3 text-slate-500"
        title={job.sources.map((source) => sourceLabel(source.name)).join(", ")}
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
              {sourceLabel(source.name)}
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
