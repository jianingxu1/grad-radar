import type { ReactNode } from "react";
import type { JobFilters, SourceName } from "../api";
import { sourceLabel } from "./format";

export function FeedFilters({
  filters,
  onChange,
  onToggleSource,
  sources,
}: {
  filters: JobFilters;
  onChange: (changes: Partial<JobFilters>) => void;
  onToggleSource: (source: SourceName) => void;
  sources: SourceName[];
}) {
  return (
    <section aria-label="Feed filters" className="mb-3 border-b border-slate-200 pb-3">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[0.35fr_0.2fr_1.75fr]">
        <Field label="Search">
          <input
            value={filters.q}
            onChange={(event) => onChange({ q: event.target.value })}
            placeholder="Company or role"
          />
        </Field>
        <Field label="Listed within">
          <select
            value={filters.listedWithinHours}
            onChange={(event) => onChange({ listedWithinHours: event.target.value })}
          >
            <option value="">Any time</option>
            <option value="24">Past 24 hours</option>
            <option value="48">Past 48 hours</option>
            <option value="168">Past 7 days</option>
            <option value="720">Past 30 days</option>
          </select>
        </Field>
        <Field grouped label="Source">
          <div className="flex min-h-10 items-center gap-4">
            {sources.map((source) => (
              <span className="flex items-center gap-2 text-sm text-slate-700" key={source}>
                <input
                  aria-label={sourceLabel(source)}
                  checked={filters.sources.includes(source)}
                  onChange={() => onToggleSource(source)}
                  type="checkbox"
                />
                <span>{sourceLabel(source)}</span>
              </span>
            ))}
          </div>
        </Field>
      </div>
    </section>
  );
}

function Field({
  children,
  grouped = false,
  label,
}: {
  children: ReactNode;
  grouped?: boolean;
  label: string;
}) {
  const className = "grid gap-1 text-xs font-medium text-slate-600";

  if (grouped) {
    return (
      <fieldset className={`${className} border-0 p-0`}>
        <legend className="p-0">{label}</legend>
        {children}
      </fieldset>
    );
  }

  return (
    <label className={className}>
      {label}
      {children}
    </label>
  );
}
