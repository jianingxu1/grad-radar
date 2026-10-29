import { useRef, type ReactNode } from "react";
import type { JobFilters, SourceName } from "../api";
import { NO_SOURCES } from "../filterState";
import { sourceLabel } from "./format";

const LISTED_WITHIN_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "24", label: "Past 24 hours" },
  { value: "48", label: "Past 48 hours" },
  { value: "168", label: "Past 7 days" },
  { value: "720", label: "Past 30 days" },
];

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
  const dateDetails = useRef<HTMLDetailsElement>(null);
  const selectedDate = LISTED_WITHIN_OPTIONS.find(
    (option) => option.value === filters.listedWithinHours,
  );

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
          <details className="group relative w-full max-w-96" ref={dateDetails}>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded border border-slate-300 px-2.5 py-1.5 text-sm text-slate-800 marker:hidden">
              <span>{selectedDate?.label ?? "Any time"}</span>
              <span aria-hidden="true" className="text-slate-500 group-open:rotate-180">
                ⌄
              </span>
            </summary>
            <div className="absolute left-0 z-20 mt-1 w-full rounded border border-slate-200 bg-white p-1 shadow-lg">
              {LISTED_WITHIN_OPTIONS.map((option) => {
                const selected = filters.listedWithinHours === option.value;
                return (
                  <button
                    aria-pressed={selected}
                    className={`flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm font-normal ${
                      selected
                        ? "bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                        : "bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                    key={option.value}
                    onClick={() => {
                      onChange({ listedWithinHours: option.value });
                      if (dateDetails.current) dateDetails.current.open = false;
                    }}
                    type="button"
                  >
                    {option.label}
                    {selected && <span aria-hidden="true">✓</span>}
                  </button>
                );
              })}
            </div>
          </details>
        </Field>
        <Field label="Source">
          <details className="group relative w-full max-w-96">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded border border-slate-300 px-2.5 py-1.5 text-sm text-slate-800 marker:hidden">
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
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 text-xs font-medium text-slate-600">
      <span>{label}</span>
      {children}
    </div>
  );
}
