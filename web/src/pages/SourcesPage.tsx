import { useEffect, useState, type FormEvent } from "react";
import type { User } from "@supabase/supabase-js";
import {
  createSource,
  fetchSourceAdminStatus,
  fetchSources,
  updateSource,
  type SourceDetail,
  type SourceFilter,
} from "../api";
import { PageShell } from "../components/PageShell";
import { formatDate, sourceLabel } from "../components/format";

type BoardPlatform = "greenhouse" | "ashby" | "lever" | "oracle" | "smartrecruiters";

export function SourcesPage({
  user,
  onNavigate,
}: {
  user: User | null;
  onNavigate: (path: "/") => void;
}) {
  const [sources, setSources] = useState<SourceDetail[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [platform, setPlatform] = useState<BoardPlatform>("greenhouse");
  const [boardName, setBoardName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [oracleHost, setOracleHost] = useState("");
  const [oracleSiteNumber, setOracleSiteNumber] = useState("CX_1");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [terms, setTerms] = useState<SourceFilter | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void fetchSources(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setSources(items);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(message(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void fetchSourceAdminStatus()
      .then((value) => {
        if (!cancelled) setIsAdmin(value);
      })
      .catch(() => {
        if (!cancelled) setIsAdmin(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function add(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const source = await createSource({
        platform,
        board_name: boardName.trim(),
        company_name: companyName.trim(),
        ...(platform === "oracle"
          ? { platform_config: { host: oracleHost.trim(), site_number: oracleSiteNumber.trim() } }
          : {}),
      });
      setSources((items) => [...items, source]);
      setFormOpen(false);
      setBoardName("");
      setCompanyName("");
    } catch (reason: unknown) {
      setError(message(reason));
    } finally {
      setSaving(false);
    }
  }

  async function save(id: string, input: { enabled?: boolean; filter_config?: SourceFilter }) {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateSource(id, input);
      setSources((items) => items.map((source) => (source.id === id ? updated : source)));
      setEditingId(null);
    } catch (reason: unknown) {
      setError(message(reason));
    } finally {
      setSaving(false);
    }
  }

  function edit(source: SourceDetail): void {
    setEditingId(source.id);
    const config = source.filter_config as SourceFilter;
    setTerms({
      role_terms: [...config.role_terms],
      level_terms: [...config.level_terms],
      exclude_terms: [...config.exclude_terms],
    });
  }

  return (
    <PageShell label="Sources" onNavigate={onNavigate}>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Sources</h2>
            <p className="text-sm text-slate-600">
              Job listings come from GitHub trackers and company job boards.
            </p>
          </div>
          {isAdmin && (
            <button className="button-secondary" onClick={() => setFormOpen((value) => !value)}>
              Add Source
            </button>
          )}
        </div>

        {error && (
          <p role="alert" className="mb-4 text-sm text-red-700">
            {error}
          </p>
        )}
        {formOpen && isAdmin && (
          <form
            onSubmit={(event) => void add(event)}
            className="mb-6 grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-4"
          >
            <label className="grid gap-1 text-sm">
              Platform
              <select
                value={platform}
                onChange={(event) => setPlatform(event.target.value as BoardPlatform)}
              >
                <option value="greenhouse">Greenhouse</option>
                <option value="ashby">Ashby</option>
                <option value="lever">Lever</option>
                <option value="oracle">Oracle Recruiting</option>
                <option value="smartrecruiters">SmartRecruiters</option>
              </select>
            </label>
            {platform === "oracle" && (
              <>
                <label className="grid gap-1 text-sm">
                  Oracle tenant hostname
                  <input required value={oracleHost} onChange={(event) => setOracleHost(event.target.value)} placeholder="e.g. example.fa.ocs.oraclecloud.com" />
                </label>
                <label className="grid gap-1 text-sm">
                  Oracle site number
                  <input required pattern="CX(_[0-9]+)?" value={oracleSiteNumber} onChange={(event) => setOracleSiteNumber(event.target.value)} placeholder="CX_1" />
                </label>
              </>
            )}
            <label className="grid gap-1 text-sm">
              Board name
              <input
                required
                pattern="[A-Za-z0-9][A-Za-z0-9_-]*"
                value={boardName}
                onChange={(event) => setBoardName(event.target.value)}
                placeholder="e.g. stripe"
              />
            </label>
            <label className="grid gap-1 text-sm">
              Company
              <input
                required
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="e.g. Stripe"
              />
            </label>
            <button disabled={saving} className="button-secondary self-end" type="submit">
              {saving ? "Checking…" : "Add Source"}
            </button>
          </form>
        )}

        {loading ? (
          <p>Loading sources…</p>
        ) : (
          <div
            className="overflow-x-auto rounded-lg border border-slate-200"
            role="region"
            aria-label="Sources table"
            tabIndex={0}
          >
            <table className="min-w-[760px] w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-3">Source</th>
                  <th className="p-3">Platform</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Last sync</th>
                  <th className="p-3">Filter</th>
                  {isAdmin && <th className="p-3">Manage</th>}
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id} className="border-t border-slate-200 align-top">
                    <td className="p-3">
                      <a
                        className="text-blue-700 underline"
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {source.company_name ?? sourceLabel(source.name)}
                      </a>
                      <div className="text-xs text-slate-500">
                        {source.board_name ?? source.name}
                      </div>
                    </td>
                    <td className="p-3 capitalize">{source.platform}</td>
                    <td className="p-3">
                      {source.enabled ? (source.last_sync_status ?? "Pending") : "Disabled"}
                    </td>
                    <td className="p-3">{formatDate(source.last_successful_sync_at)}</td>
                    <td className="p-3">
                      {source.platform === "github" ? "Tracker curated" : "U.S. new-grad SWE"}
                    </td>
                    {isAdmin && (
                      <td className="p-3">
                        {source.platform !== "github" && (
                          <div className="flex gap-2">
                            <button
                              className="button-secondary"
                              disabled={saving}
                              onClick={() => edit(source)}
                            >
                              Edit filter
                            </button>
                            <button
                              className="button-secondary"
                              disabled={saving}
                              onClick={() => void save(source.id, { enabled: !source.enabled })}
                            >
                              {source.enabled ? "Disable" : "Enable"}
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {editingId && terms && isAdmin && (
          <form
            className="mt-5 grid gap-3 rounded-lg border border-slate-200 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              void save(editingId, { filter_config: terms });
            }}
          >
            <h3 className="font-semibold">Edit source filter</h3>
            {(["role_terms", "level_terms", "exclude_terms"] as const).map((key) => (
              <label key={key} className="grid gap-1 text-sm">
                {key.replace("_", " ")} (comma separated)
                <input
                  required
                  value={terms[key].join(", ")}
                  onChange={(event) =>
                    setTerms({
                      ...terms,
                      [key]: event.target.value
                        .split(",")
                        .map((term) => term.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
            ))}
            <div className="flex gap-2">
              <button className="button-secondary" disabled={saving} type="submit">
                Save filter
              </button>
              <button className="button-secondary" type="button" onClick={() => setEditingId(null)}>
                Cancel
              </button>
            </div>
          </form>
        )}
    </PageShell>
  );
}

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : "The request failed.";
}
