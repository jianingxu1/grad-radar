import type { ReactNode } from "react";

export function PageShell({
  label,
  onNavigate,
  children,
}: {
  label: string;
  onNavigate: (path: "/") => void;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <header className="border-b border-slate-200">
        <div className="mx-auto grid w-full max-w-[1800px] grid-cols-[1fr_auto] items-center gap-x-4 gap-y-3 px-5 py-4 sm:min-h-[73px] sm:grid-cols-[1fr_auto_1fr] sm:gap-y-0 sm:px-8">
          <button
            aria-label="Go to GradRadar home"
            className="flex w-fit cursor-pointer items-center gap-3 bg-transparent p-0 text-left text-slate-950 shadow-none hover:bg-transparent"
            type="button"
            onClick={() => onNavigate("/")}
          >
            <img
              alt=""
              aria-hidden="true"
              className="size-8 rounded-lg"
              src="/gradradar-logo-512.png"
            />
            <span className="text-xl font-semibold tracking-tight">GradRadar</span>
          </button>
          <h1 className="col-span-2 row-start-2 text-center text-lg font-semibold tracking-tight sm:col-span-1 sm:row-start-auto sm:text-xl">
            {label}
          </h1>
          <button className="button-secondary ml-auto" onClick={() => onNavigate("/")}>
            Back to jobs
          </button>
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1800px] flex-1 px-5 py-8 sm:px-8">{children}</div>
      <footer className="border-t border-slate-200">
        <div className="mx-auto w-full max-w-[1800px] px-5 py-5 text-sm font-medium tracking-tight text-slate-400 sm:px-8">
          © GradRadar
        </div>
      </footer>
    </main>
  );
}
