import type { JobFilters, SourceName } from "./api";

const sourceNames: SourceName[] = ["simplify", "speedyapply"];

export const defaultFilters: JobFilters = {
  q: "",
  listedWithinHours: "",
  sources: [],
  sortBy: "listed_at",
  sortDirection: "desc",
  page: 1,
};

function positiveInteger(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function positiveIntegerString(value: string | null): string {
  return positiveInteger(value, 0) ? (value ?? "") : "";
}

export function filtersFromSearch(search: string): JobFilters {
  const params = new URLSearchParams(search);
  const sortBy = params.get("sort_by");
  const sortDirection = params.get("sort_direction");
  return {
    q: params.get("q") ?? "",
    listedWithinHours: positiveIntegerString(params.get("listed_within_hours")),
    sources: params
      .getAll("sources")
      .filter((source): source is SourceName => sourceNames.includes(source as SourceName)),
    sortBy: sortBy === "company_name" ? sortBy : "listed_at",
    sortDirection: sortDirection === "asc" ? sortDirection : "desc",
    page: positiveInteger(params.get("page"), 1),
  };
}

export function filtersToSearch(filters: JobFilters): string {
  const params = new URLSearchParams();
  const values: Array<[string, string]> = [
    ["q", filters.q],
    ["listed_within_hours", filters.listedWithinHours],
    ["sort_by", filters.sortBy],
    ["sort_direction", filters.sortDirection],
  ];
  for (const [key, value] of values) if (value) params.set(key, value);
  for (const source of filters.sources) params.append("sources", source);
  if (filters.page > 1) params.set("page", String(filters.page));
  const query = params.toString();
  return query ? `?${query}` : "";
}
