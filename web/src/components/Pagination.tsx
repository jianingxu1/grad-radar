import { PAGE_SIZE } from "../api";
import type { JobFilters, JobPage } from "../api";

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
export function Pagination({
  filters,
  page,
  onChangePage,
}: {
  filters: JobFilters;
  page: JobPage;
  onChangePage: (page: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
  return (
    <nav
      aria-label="Job feed pages"
      className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4"
    >
      <p className="text-sm text-slate-500">
        Showing {(filters.page - 1) * PAGE_SIZE + 1}–
        {Math.min(filters.page * PAGE_SIZE, page.total)} of {page.total}
      </p>
      <div className="flex items-center gap-1" aria-label={`Page ${filters.page} of ${pageCount}`}>
        <button
          className="bg-transparent px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-950 disabled:bg-transparent disabled:text-slate-300"
          disabled={filters.page === 1}
          onClick={() => onChangePage(filters.page - 1)}
        >
          Previous
        </button>
        {paginationItems(filters.page, pageCount).map((item, index) =>
          item === "ellipsis" ? (
            <span className="px-1.5 text-slate-400" key={`ellipsis-${index}`} aria-hidden="true">
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
              onClick={() => onChangePage(item)}
            >
              {item}
            </button>
          ),
        )}
        <button
          className="bg-transparent px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-950 disabled:bg-transparent disabled:text-slate-300"
          disabled={filters.page >= pageCount}
          onClick={() => onChangePage(filters.page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
