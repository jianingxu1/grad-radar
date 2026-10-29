import type { ReactNode } from "react";
import type { JobFilters, SourceName } from "../api";
import { NO_SOURCES } from "../filterState";
import { sourceLabel } from "./format";

export function FeedFilters({
  filters,
  onChange,
  onToggleSource,
  onUncheckAll,
  onCheckAll,
  sources,
}: {
  filters: JobFilters;
  onChange: (changes: Partial<JobFilters>) => void;
  onToggleSource: (source: SourceName) => void;
  onUncheckAll: () => void;
  onCheckAll: () => void;
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
          <details className="group relative">
            <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 rounded border border-slate-300 px-3 text-sm text-slate-800 marker:hidden">
              <span>
                {filters.sources.length === 0
                  ? `All sources (${sources.length})`
                  : `${filters.sources.filter((source) => source !== NO_SOURCES).length} of ${sources.length} sources`}
              </span>
              <span aria-hidden="true" className="text-slate-500 group-open:rotate-180">
                ⌄
              </span>
            </summary>
            <div className="absolute right-0 z-20 mt-1 max-h-80 w-[min(24rem,calc(100vw-2.5rem))] overflow-y-auto rounded border border-slate-200 bg-white p-4 shadow-lg">
              <div className="mb-3 flex gap-2 text-sm">
                <button type="button" className="button-secondary" onClick={onUncheckAll}>
                  Uncheck all
                </button>
                <button type="button" className="button-secondary" onClick={onCheckAll}>
                  Check all
                </button>
              </div>
              <SourceGroup
                title="GitHub sources"
                sources={sources.filter((source) => !source.includes(":"))}
                selected={filters.sources}
                onToggleSource={onToggleSource}
              />
              <SourceGroup
                title="Company job boards"
                sources={sources.filter((source) => source.includes(":"))}
                selected={filters.sources}
                onToggleSource={onToggleSource}
              />
            </div>
          </details>
        </Field>
      </div>
    </section>
  );
}

function SourceGroup({
  title,
  sources,
  selected,
  onToggleSource,
}: {
  title: string;
  sources: SourceName[];
  selected: SourceName[];
  onToggleSource: (source: SourceName) => void;
}) {
  return (
    <fieldset className="mb-3 grid gap-2 border-0 p-0 last:mb-0">
      <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </legend>
      {sources.map((source) => (
        <label
          className="flex cursor-pointer items-center gap-2 text-sm font-normal text-slate-700"
          key={source}
        >
          <input
            aria-label={sourceLabel(source)}
            checked={selected.length === 0 || selected.includes(source)}
            onChange={() => onToggleSource(source)}
            type="checkbox"
          />
          <span>{sourceLabel(source)}</span>
        </label>
      ))}
    </fieldset>
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
