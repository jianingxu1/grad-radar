export type SourceName = string;

export type SourceFilter = {
  role_terms: string[];
  level_terms: string[];
  exclude_terms: string[];
};

export type SourceDetail = {
  id: string;
  name: string;
  url: string;
  platform: "github" | "greenhouse" | "ashby" | "lever";
  board_name: string | null;
  company_name: string | null;
  enabled: boolean;
  filter_config: SourceFilter | Record<string, never>;
  last_successful_sync_at: string | null;
  last_sync_status: string | null;
};

export type Job = {
  id: string;
  company_name: string;
  title: string;
  apply_url: string;
  location: string;
  listed_at: string | null;
  first_seen_at: string;
  sources: Array<{ name: SourceName; url: string }>;
};

export type SourceFreshness = {
  name: SourceName;
  url: string;
  last_successful_sync_at: string | null;
};

export type JobPage = {
  items: Job[];
  offset: number;
  limit: number;
  total: number;
  source_freshness: SourceFreshness[];
};

export type JobFilters = {
  q: string;
  listedWithinHours: string;
  sources: SourceName[];
  sortBy: "company_name" | "listed_at";
  sortDirection: "asc" | "desc";
  page: number;
};

export const PAGE_SIZE = 25;
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export function toSearchParams(filters: JobFilters): URLSearchParams {
  const params = new URLSearchParams({
    offset: String((filters.page - 1) * PAGE_SIZE),
    limit: String(PAGE_SIZE),
  });
  const scalarFilters: Array<[string, string]> = [
    ["q", filters.q],
    ["listed_within_hours", filters.listedWithinHours],
    ["sort_by", filters.sortBy],
    ["sort_direction", filters.sortDirection],
  ];
  for (const [key, value] of scalarFilters) {
    if (value) params.set(key, value);
  }
  for (const source of filters.sources) params.append("sources", source);
  return params;
}

export async function fetchJobs(filters: JobFilters, signal?: AbortSignal): Promise<JobPage> {
  const response = await fetch(`${apiBaseUrl}/v1/jobs?${toSearchParams(filters)}`, { signal });
  if (!response.ok) throw new Error(`The jobs feed could not be loaded (${response.status}).`);
  return response.json() as Promise<JobPage>;
}

export async function fetchSources(signal?: AbortSignal): Promise<SourceDetail[]> {
  const response = await fetch(`${apiBaseUrl}/v1/sources`, { signal });
  if (!response.ok) throw new Error("Sources could not be loaded.");
  return response.json() as Promise<SourceDetail[]>;
}

export type NotificationSettings = {
  status: "not_connected" | "pending" | "connected" | "disabled";
  expires_at: string | null;
};

async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
  const { supabase } = await import("./supabase");
  const { data } = (await supabase?.auth.getSession()) ?? { data: { session: null } };
  let token = data.session?.access_token;
  if (!token) throw new Error("Please sign in to manage this setting.");
  const request = () =>
    fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { ...init?.headers, Authorization: `Bearer ${token}` },
    });
  let response = await request();
  if (response.status === 401 && supabase) {
    const { data: refreshed } = await supabase.auth.refreshSession();
    token = refreshed.session?.access_token;
    if (token) response = await request();
  }
  return response;
}

export async function fetchSourceAdminStatus(): Promise<boolean> {
  const response = await authenticatedFetch("/v1/me/source-admin");
  if (!response.ok) return false;
  const body = (await response.json()) as { is_admin: boolean };
  return body.is_admin;
}

export async function createSource(input: {
  platform: "greenhouse" | "ashby" | "lever";
  board_name: string;
  company_name: string;
}): Promise<SourceDetail> {
  const response = await authenticatedFetch("/v1/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(`Source could not be added (${response.status}).`);
  return response.json() as Promise<SourceDetail>;
}

export async function updateSource(
  id: string,
  input: { enabled?: boolean; filter_config?: SourceFilter },
): Promise<SourceDetail> {
  const response = await authenticatedFetch(`/v1/sources/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(`Source could not be updated (${response.status}).`);
  return response.json() as Promise<SourceDetail>;
}

export async function fetchNotificationSettings(
  signal?: AbortSignal,
): Promise<NotificationSettings> {
  const response = await authenticatedFetch("/v1/me/notification-settings", { signal });
  if (!response.ok) throw new Error("Notification settings could not be loaded.");
  return response.json() as Promise<NotificationSettings>;
}

export async function createTelegramLink(): Promise<{ deep_link: string; expires_at: string }> {
  const response = await authenticatedFetch("/v1/me/telegram/link", { method: "POST" });
  if (!response.ok) throw new Error("Telegram could not be connected right now.");
  return response.json() as Promise<{ deep_link: string; expires_at: string }>;
}

export async function disconnectTelegram(): Promise<void> {
  const response = await authenticatedFetch("/v1/me/telegram", { method: "DELETE" });
  if (!response.ok) throw new Error("Telegram could not be disconnected right now.");
}
