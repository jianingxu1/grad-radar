export function PageHeader({
  label,
  onNavigate,
}: {
  label: string;
  onNavigate: (path: "/") => void;
}) {
  return (
    <header className="mb-10 flex items-baseline justify-between gap-4 border-b border-slate-200 pb-4">
      <div className="flex items-center gap-3">
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
        <p className="text-sm text-slate-500">{label}</p>
      </div>
      <button className="button-secondary" onClick={() => onNavigate("/")}>
        Back to jobs
      </button>
    </header>
  );
}
