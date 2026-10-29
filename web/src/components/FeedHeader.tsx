import type { RefObject } from "react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "../supabase";

export function FeedHeader({
  user,
  googleLoadError,
  googleButtonRef,
  onNavigate,
  onSignOut,
}: {
  user: User | null;
  googleLoadError: boolean;
  googleButtonRef: RefObject<HTMLDivElement | null>;
  onNavigate: (path: "/" | "/faq" | "/sources" | "/settings/notifications") => void;
  onSignOut: () => void;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-slate-200 pb-4">
      <button
        aria-label="Go to GradRadar home"
        className="flex cursor-pointer items-center gap-3 bg-transparent p-0 text-left text-slate-950 shadow-none hover:bg-transparent"
        type="button"
        onClick={() => onNavigate("/")}
      >
        <img
          alt=""
          aria-hidden="true"
          className="size-8 rounded-lg"
          src="/gradradar-logo-512.png"
        />
        <h1 className="text-xl font-semibold tracking-tight">GradRadar</h1>
      </button>
      <div className="flex items-center gap-3">
        <p className="text-sm text-slate-500">U.S. entry-level software engineering jobs</p>
      </div>
      <div className="flex max-w-full flex-wrap items-center gap-3 sm:gap-4">
        <button className="button-secondary" onClick={() => onNavigate("/sources")}>
          Sources
        </button>
        <button className="button-secondary" onClick={() => onNavigate("/faq")}>
          FAQ
        </button>
        <button className="button-secondary" onClick={() => onNavigate("/settings/notifications")}>
          {user ? "Notifications" : "Sign in to set up and receive telegram notifications!"}
        </button>
        {user ? (
          <>
            <details className="relative">
              <summary
                className="cursor-pointer list-none rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                aria-label="Account menu"
              >
                {user.email} ▾
              </summary>
              <div className="absolute right-0 z-10 mt-2 grid min-w-48 gap-1 rounded bg-white p-1 shadow-lg ring-1 ring-black/5">
                <button
                  className="w-full bg-transparent text-left text-slate-700 hover:bg-slate-100"
                  type="button"
                  onClick={() => onSignOut()}
                >
                  Sign out
                </button>
              </div>
            </details>
          </>
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
  );
}
