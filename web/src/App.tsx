import { useEffect, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { fetchJobs, PAGE_SIZE, type JobFilters, type JobPage, type SourceName } from "./api";
import { FeedFilters } from "./components/FeedFilters";
import { FeedHeader } from "./components/FeedHeader";
import { JobFeed } from "./components/JobFeed";
import { Pagination } from "./components/Pagination";
import { NO_SOURCES, defaultFilters, filtersFromSearch, filtersToSearch } from "./filterState";
import { FaqPage } from "./pages/FaqPage";
import { NotificationSettingsPage } from "./pages/NotificationSettingsPage";
import { SourcesPage } from "./pages/SourcesPage";
import { supabase } from "./supabase";

function updateUrl(filters: JobFilters, replace = false): void {
  const url = `${window.location.pathname}${filtersToSearch(filters)}`;
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
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
    let buttonWidth = window.innerWidth < 640 ? 200 : 220;
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
        buttonWidth = window.innerWidth < 640 ? 200 : 220;
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: "outline",
          size: "large",
          text: "sign_in",
          shape: "rectangular",
          width: buttonWidth,
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
    const handleResize = () => {
      if ((window.innerWidth < 640 ? 200 : 220) !== buttonWidth) {
        void renderGoogleButton();
      }
    };
    script?.addEventListener("error", handleScriptError);
    script?.addEventListener("load", renderGoogleButton);
    window.addEventListener("resize", handleResize);
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
      window.removeEventListener("resize", handleResize);
    };
  }, [path, user]);

  useEffect(() => {
    if (path === "/faq" || path === "/settings/notifications" || path === "/sources") return;
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

  function navigate(nextPath: "/" | "/faq" | "/sources" | "/settings/notifications"): void {
    window.history.pushState({}, "", nextPath === "/" ? `/${filtersToSearch(filters)}` : nextPath);
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
    const available = page?.source_freshness.map((item) => item.name) ?? [];
    const selected = filters.sources.length === 0 ? available : filters.sources;
    const next = selected.includes(source)
      ? selected.filter((value) => value !== source)
      : [...selected.filter((value) => value !== NO_SOURCES), source];
    changeFilters({
      sources: next.length === 0 ? [NO_SOURCES] : next.length === available.length ? [] : next,
    });
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
    return (
      <NotificationSettingsPage key={user?.id ?? "signed-out"} user={user} onNavigate={navigate} />
    );
  }
  if (path === "/sources") {
    return <SourcesPage key={user?.id ?? "signed-out"} user={user} onNavigate={navigate} />;
  }

  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-[1800px] flex-1 px-5 py-5 sm:px-8">
        <FeedHeader
          user={user}
          googleLoadError={googleLoadError}
          googleButtonRef={googleButtonRef}
          onNavigate={navigate}
          onSignOut={() => void signOut()}
        />
        {authError && (
          <p className="mb-3 text-sm text-red-700" role="alert">
            {authError}
          </p>
        )}
        <FeedFilters
          filters={filters}
          onChange={changeFilters}
          onToggleSource={toggleSource}
          onUncheckAll={() => changeFilters({ sources: [NO_SOURCES] })}
          onCheckAll={() => changeFilters({ sources: [] })}
          sources={page?.source_freshness.map((source) => source.name) ?? []}
        />
        <JobFeed
          page={page}
          loading={loading}
          error={error}
          filters={filters}
          onRetry={() => {
            setLoading(true);
            setError(null);
            setRetry((value) => value + 1);
          }}
          onClearFilters={() => changeFilters(defaultFilters)}
          onSort={changeSort}
        />
        {page && page.total > 0 && (
          <Pagination filters={filters} page={page} onChangePage={changePage} />
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
