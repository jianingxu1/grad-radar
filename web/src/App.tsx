import { useEffect, useRef, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";

import {
  createTelegramLink,
  disconnectTelegram,
  fetchJobs,
  fetchNotificationSettings,
  PAGE_SIZE,
  type JobFilters,
  type JobPage,
  type NotificationSettings,
  type SourceName,
} from "./api";
import { defaultFilters, filtersFromSearch, filtersToSearch } from "./filterState";
import { supabase } from "./supabase";

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
  const [path, setPath] = useState(() => window.location.pathname);
  const [filters, setFilters] = useState<JobFilters>(() =>
    filtersFromSearch(window.location.search),
  );
  const [page, setPage] = useState<JobPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [googleLoadError, setGoogleLoadError] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!supabase) return;

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setAuthError(null);
        googleButtonRef.current?.replaceChildren();
      }
      setUser(session?.user ?? null);
    });
    void supabase.auth
      .getSession()
      .then(({ data, error: sessionError }) => {
        if (sessionError) {
          setAuthError(sessionError.message);
          return;
        }
        setUser(data.session?.user ?? null);
      })
      .catch((reason: unknown) => {
        setAuthError(reason instanceof Error ? reason.message : "Could not restore auth session");
      });
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    if (user || !supabase || !googleClientId || !googleButtonRef.current) return;
    const authClient = supabase;

    let cancelled = false;
    let loadTimeout: ReturnType<typeof setTimeout> | undefined;
    async function renderGoogleButton(): Promise<void> {
      if (!window.google || cancelled || !googleButtonRef.current) return;
      try {
        const nonce = await createNonce();
        if (cancelled || !googleButtonRef.current) return;

        window.google.accounts.id.initialize({
          client_id: googleClientId,
          nonce: nonce.hashed,
          callback: (response) => {
            void authClient.auth
              .signInWithIdToken({
                provider: "google",
                token: response.credential,
                nonce: nonce.raw,
              })
              .then(({ error: signInError }) => {
                if (signInError) {
                  setAuthError(signInError.message);
                } else {
                  setAuthError(null);
                }
              })
              .catch((reason: unknown) => {
                setAuthError(reason instanceof Error ? reason.message : "Google sign-in failed");
              });
          },
        });
        googleButtonRef.current.replaceChildren();
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: "outline",
          size: "large",
          text: "sign_in",
          shape: "rectangular",
          width: 220,
        });
        setGoogleLoadError(false);
      } catch (reason: unknown) {
        setGoogleLoadError(true);
        setAuthError(reason instanceof Error ? reason.message : "Google sign-in failed");
      }
    }

    const script = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    const handleScriptError = () => setGoogleLoadError(true);
    script?.addEventListener("error", handleScriptError);
    script?.addEventListener("load", renderGoogleButton);
    if (window.google) {
      void renderGoogleButton();
    } else {
      loadTimeout = setTimeout(() => {
        if (!cancelled && !window.google) setGoogleLoadError(true);
      }, 10000);
    }
    return () => {
      cancelled = true;
      if (loadTimeout) clearTimeout(loadTimeout);
      script?.removeEventListener("error", handleScriptError);
      script?.removeEventListener("load", renderGoogleButton);
    };
  }, [user]);

  useEffect(() => {
    if (path === "/faq" || path === "/settings/notifications") return;
    const controller = new AbortController();
    void fetchJobs(filters, controller.signal)
      .then((nextPage) => {
        if (controller.signal.aborted) return;
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
  }, [filters, path, retry]);

  useEffect(() => {
    const onPopState = () => {
      setPath(window.location.pathname);
      setLoading(true);
      setError(null);
      setFilters(filtersFromSearch(window.location.search));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function navigate(nextPath: "/" | "/faq" | "/settings/notifications"): void {
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
    if (nextPath === "/") {
      setLoading(true);
      setError(null);
    }
  }

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

  async function signOut(): Promise<void> {
    if (!supabase) return;
    try {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) {
        setAuthError(signOutError.message);
      } else {
        setAuthError(null);
      }
    } catch (reason: unknown) {
      setAuthError(reason instanceof Error ? reason.message : "Sign-out failed");
    }
  }

  if (path === "/faq") {
    return <FaqPage onNavigate={navigate} />;
  }
  if (path === "/settings/notifications") {
    return <NotificationSettingsPage user={user} onNavigate={navigate} />;
  }

  const pageCount = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;
  const showInitialSkeleton = loading && page === null;

  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-[1800px] flex-1 px-5 py-5 sm:px-8">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <img
              alt=""
              aria-hidden="true"
              className="size-8 rounded-lg"
              src="/gradradar-logo-512.png"
            />
            <h1 className="text-xl font-semibold tracking-tight">GradRadar</h1>
            <p className="text-sm text-slate-500">U.S. entry-level software engineering jobs</p>
          </div>
          <div className="flex items-center gap-4">
            <p className="text-sm text-slate-500">
              {page ? `${page.total} roles` : "Loading roles…"}
            </p>
            <button className="button-secondary" onClick={() => navigate("/faq")}>
              FAQ
            </button>
            {user ? (
              <details className="relative">
                <summary
                  className="button-secondary cursor-pointer list-none"
                  aria-label="Account menu"
                >
                  {user.email} ▾
                </summary>
                <div className="absolute right-0 z-10 mt-2 grid min-w-48 gap-1 rounded border border-slate-200 bg-white p-2 shadow-lg">
                  <button
                    className="button-secondary text-left"
                    onClick={() => navigate("/settings/notifications")}
                  >
                    Notifications
                  </button>
                  <button className="button-secondary text-left" onClick={() => void signOut()}>
                    Sign out
                  </button>
                </div>
              </details>
            ) : googleLoadError ? (
              <span className="text-sm text-red-700" role="alert">
                Google sign-in is unavailable. Refresh and try again.
              </span>
            ) : import.meta.env.VITE_GOOGLE_CLIENT_ID && supabase ? (
              <div aria-label="Sign in with Google" ref={googleButtonRef} />
            ) : (
              <span className="text-sm text-slate-500">Google sign-in is not configured</span>
            )}
          </div>
        </header>
        {authError && (
          <p className="mb-3 text-sm text-red-700" role="alert">
            {authError}
          </p>
        )}

        <section aria-label="Feed filters" className="mb-3 border-b border-slate-200 pb-3">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[1.4fr_0.8fr_1.2fr]">
            <Field label="Search">
              <input
                value={filters.q}
                onChange={(event) => changeFilters({ q: event.target.value })}
                placeholder="Company or role"
              />
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
            <div>
              <table className="w-full table-fixed border-collapse text-left">
                <thead className="border-y border-slate-200 text-sm font-medium text-slate-500">
                  <tr>
                    <SortableHeader
                      className="w-[34%] sm:w-[15%]"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Company"
                      onClick={() => changeSort("company_name")}
                      sortKey="company_name"
                    />
                    <th className="w-[66%] px-2 py-2 font-medium sm:w-[37%] sm:px-3">Role</th>
                    <th className="hidden w-[18%] px-3 py-2 font-medium sm:table-cell">Location</th>
                    <SortableHeader
                      className="hidden w-[10%] sm:table-cell"
                      currentSort={filters.sortBy}
                      direction={filters.sortDirection}
                      label="Listed"
                      onClick={() => changeSort("listed_at")}
                      sortKey="listed_at"
                    />
                    <th className="hidden w-[10%] px-3 py-2 font-medium sm:table-cell">Source</th>
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

async function createNonce(): Promise<{ hashed: string; raw: string }> {
  const raw = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw));
  const hashed = Array.from(new Uint8Array(hash))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return { raw, hashed };
}

function NotificationSettingsPage({
  user,
  onNavigate,
}: {
  user: User | null;
  onNavigate: (path: "/") => void;
}) {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async (): Promise<NotificationSettings | null> => {
    try {
      const next = await fetchNotificationSettings();
      setSettings(next);
      setError(null);
      return next;
    } catch (reason: unknown) {
      setError(
        reason instanceof Error ? reason.message : "Notification settings could not be loaded.",
      );
      return null;
    }
  };

  useEffect(() => {
    if (!user) return;
    void Promise.resolve().then(load);
  }, [user]);

  useEffect(() => {
    if (!user || settings?.status !== "pending") return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [settings?.status, user]);

  async function connect(): Promise<void> {
    setBusy(true);
    try {
      const link = await createTelegramLink();
      window.open(link.deep_link, "_blank", "noopener,noreferrer");
      await load();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error ? reason.message : "Telegram could not be connected right now.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function stop(): Promise<void> {
    setBusy(true);
    try {
      await disconnectTelegram();
      await load();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error ? reason.message : "Telegram could not be disconnected right now.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-2xl flex-1 px-5 py-8 sm:px-8">
        <button className="button-secondary" onClick={() => onNavigate("/")}>
          Back to jobs
        </button>
        <h1 className="mt-8 text-3xl font-semibold tracking-tight">Notifications</h1>
        {!user ? (
          <p className="mt-4 text-slate-600">Sign in to connect Telegram alerts.</p>
        ) : (
          <section className="mt-6 rounded border border-slate-200 p-6" aria-live="polite">
            {error && (
              <p className="mb-4 text-red-700" role="alert">
                {error}
              </p>
            )}
            {!settings ? (
              <p>Loading notification settings…</p>
            ) : (
              <NotificationState
                settings={settings}
                busy={busy}
                onConnect={() => void connect()}
                onStop={() => void stop()}
              />
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function NotificationState({
  settings,
  busy,
  onConnect,
  onStop,
}: {
  settings: NotificationSettings;
  busy: boolean;
  onConnect: () => void;
  onStop: () => void;
}) {
  if (settings.status === "connected") {
    return (
      <>
        <p>
          Telegram alerts are connected. You will receive new GradRadar jobs after each ingestion
          cycle.
        </p>
        <button className="mt-4" disabled={busy} onClick={onStop}>
          Stop notifications
        </button>
      </>
    );
  }
  if (settings.status === "pending") {
    return (
      <>
        <p>
          Open Telegram and press Start to finish connecting. This link expires{" "}
          {settings.expires_at ? formatDate(settings.expires_at) : "soon"}.
        </p>
        <button className="mt-4" disabled={busy} onClick={onConnect}>
          Open Telegram
        </button>
        <button className="button-secondary ml-2 mt-4" disabled={busy} onClick={onConnect}>
          Create a new link
        </button>
      </>
    );
  }
  if (settings.status === "disabled") {
    return (
      <>
        <p>Telegram alerts are off or the bot can no longer message this chat.</p>
        <button className="mt-4" disabled={busy} onClick={onConnect}>
          Reconnect Telegram
        </button>
      </>
    );
  }
  return (
    <>
      <p>
        Connect Telegram to get alerts for jobs GradRadar discovers after you confirm the
        connection.
      </p>
      <button className="mt-4" disabled={busy} onClick={onConnect}>
        Connect Telegram
      </button>
    </>
  );
}

function FaqPage({ onNavigate }: { onNavigate: (path: "/") => void }) {
  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-4xl flex-1 px-5 py-5 sm:px-8">
        <header className="mb-10 flex items-baseline justify-between gap-4 border-b border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <img
              alt=""
              aria-hidden="true"
              className="size-8 rounded-lg"
              src="/gradradar-logo-512.png"
            />
            <h1 className="text-xl font-semibold tracking-tight">GradRadar</h1>
            <p className="text-sm text-slate-500">Frequently asked questions</p>
          </div>
          <button className="button-secondary" onClick={() => onNavigate("/")}>
            Back to jobs
          </button>
        </header>

        <section aria-labelledby="faq-heading">
          <h2 className="text-3xl font-semibold tracking-tight" id="faq-heading">
            How GradRadar works
          </h2>
          <dl className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
            <FaqItem question="What jobs does GradRadar show?">
              Full-time U.S. entry-level software engineering roles from the new-grad sections of
              Simplify and SpeedyApply. It is designed for 2026 and 2027 bachelor&apos;s and
              master&apos;s graduates; PhD-specific roles are excluded.
            </FaqItem>
            <FaqItem question="How often is the feed updated?">
              GradRadar checks both trackers every 15 minutes from 7:00 AM through 8:45 PM Pacific.
              Overnight, it checks every two hours at 9:00 PM, 11:00 PM, 1:00 AM, 3:00 AM, and 5:00
              AM Pacific. A tracker is parsed only when its source file has changed.
            </FaqItem>
            <FaqItem question="What does “U.S.” mean here?">
              The filter keeps locations that clearly point to the United States, including U.S.
              states, common U.S. tech hubs, “United States,” and U.S.-eligible remote roles.
              Clearly non-U.S., mixed, or unknown locations are left out rather than guessed. This
              is a location filter, not a visa or sponsorship assessment.
            </FaqItem>
            <FaqItem question="Where do the listings come from?">
              The feed currently uses the Software Engineering new-grad section of Simplify and the
              USA new-grad SWE file from SpeedyApply. Each job shows its tracker source, so you can
              check the original listing context.
            </FaqItem>
            <FaqItem question="Are application links verified by GradRadar?">
              No. Application links are supplied by the source tracker. Open them to confirm the
              employer, requirements, deadline, location, and whether the position is still open.
            </FaqItem>
            <FaqItem question="What do “Listed” and tracker freshness mean?">
              “Listed” is the tracker&apos;s estimated posting age, not an employer-confirmed
              publish time. Tracker freshness shows when GradRadar last successfully synced each
              source.
            </FaqItem>
            <FaqItem question="Does GradRadar require an account or track my applications?">
              No. The current feed is public and read-only. It does not submit applications or track
              application status.
            </FaqItem>
          </dl>
        </section>
      </div>
      <footer className="border-t border-slate-200 px-5 py-5 sm:px-8">
        <div className="mx-auto max-w-4xl text-sm font-medium tracking-tight text-slate-400">
          © GradRadar
        </div>
      </footer>
    </main>
  );
}

function FaqItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <div className="py-6">
      <dt className="text-base font-semibold">{question}</dt>
      <dd className="mt-2 max-w-3xl leading-7 text-slate-600">{children}</dd>
    </div>
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
      <td className="break-words px-2 py-3 font-medium sm:truncate sm:px-3" title={companyName}>
        {companyName}
      </td>
      <td className="break-words px-2 py-3 sm:truncate sm:px-3">
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
      <td className="hidden truncate px-3 py-3 text-slate-600 sm:table-cell" title={job.location}>
        {job.location}
      </td>
      <td
        className="hidden px-3 py-3 text-slate-500 sm:table-cell"
        title={formatDate(job.listed_at)}
      >
        {formatAge(job.listed_at)}
      </td>
      <td
        className="hidden truncate px-3 py-3 text-slate-500 sm:table-cell"
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
