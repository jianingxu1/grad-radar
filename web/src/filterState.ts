import type { JobFilters, SourceName } from "./api";

const sourceNames: SourceName[] = ["simplify", "speedyapply"];

export const defaultFilters: JobFilters = {
  q: "",
  location: "",
  remote: "",
  company: "",
  postedWithinHours: "",
  listedWithinDays: "",
  sources: [],
  page: 1,
};

function positiveInteger(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function filtersFromSearch(search: string): JobFilters {
  const params = new URLSearchParams(search);
  const remote = params.get("remote");
  return {
    q: params.get("q") ?? "",
    location: params.get("location") ?? "",
    remote: remote === "true" || remote === "false" ? remote : "",
    company: params.get("company") ?? "",
    postedWithinHours: params.get("posted_within_hours") ?? "",
    listedWithinDays: params.get("listed_within_days") ?? "",
    sources: params
      .getAll("sources")
      .filter((source): source is SourceName => sourceNames.includes(source as SourceName)),
    page: positiveInteger(params.get("page"), 1),
  };
}

export function filtersToSearch(filters: JobFilters): string {
  const params = new URLSearchParams();
  const values: Array<[string, string]> = [
    ["q", filters.q],
    ["location", filters.location],
    ["remote", filters.remote],
    ["company", filters.company],
    ["posted_within_hours", filters.postedWithinHours],
    ["listed_within_days", filters.listedWithinDays],
  ];
  for (const [key, value] of values) if (value) params.set(key, value);
  for (const source of filters.sources) params.append("sources", source);
  if (filters.page > 1) params.set("page", String(filters.page));
  const query = params.toString();
  return query ? `?${query}` : "";
}
