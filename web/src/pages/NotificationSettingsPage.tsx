import { useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import {
  createTelegramLink,
  disconnectTelegram,
  fetchNotificationSettings,
  type NotificationSettings,
} from "../api";
import { formatDate } from "../components/format";
import { PageHeader } from "../components/PageHeader";

export function NotificationSettingsPage({
  user,
  onNavigate,
}: {
  user: User | null;
  onNavigate: (path: "/") => void;
}) {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
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
    } finally {
      setSettingsLoaded(true);
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
      <div className="mx-auto w-full max-w-4xl flex-1 px-5 py-5 sm:px-8">
        <PageHeader label="Notifications" onNavigate={onNavigate} />
        <section aria-labelledby="notifications-heading">
          <h2 className="text-3xl font-semibold tracking-tight" id="notifications-heading">
            Notifications
          </h2>
          <p className="mt-3 max-w-2xl text-slate-600">
            Manage Telegram alerts for newly discovered GradRadar jobs.
          </p>
        </section>
        {!user ? (
          <p className="mt-4 max-w-2xl text-slate-600">
            Don’t miss new jobs — sign in for Telegram alerts.
          </p>
        ) : (
          <>
            <section className="mt-6 rounded border border-slate-200 p-6" aria-live="polite">
              {error && (
                <p className="mb-4 text-red-700" role="alert">
                  {error}
                </p>
              )}
              {!settings && !settingsLoaded ? (
                <p>Loading notification settings…</p>
              ) : !settings ? (
                <button
                  onClick={() => {
                    setSettingsLoaded(false);
                    void load();
                  }}
                >
                  Try again
                </button>
              ) : (
                <NotificationState
                  settings={settings}
                  busy={busy}
                  onConnect={() => void connect()}
                  onStop={() => void stop()}
                />
              )}
            </section>
            <section className="mt-8 max-w-2xl" aria-labelledby="telegram-setup-heading">
              <h3 className="text-xl font-semibold" id="telegram-setup-heading">
                How to set up Telegram alerts
              </h3>
              <ol className="mt-4 list-decimal space-y-2 pl-6 text-slate-700">
                <li>Install Telegram on your phone or computer and sign in.</li>
                <li>Click the Telegram button above to open the GradRadar bot in Telegram.</li>
                <li>Press Start in the bot chat to finish connecting.</li>
                <li>Once you receive “Telegram alerts connected.” in the chat, you are done!</li>
              </ol>
              <p className="mt-4 text-slate-600">
                New job postings will be sent to that chat. Turn on Telegram notifications on your
                phone or computer so you don’t miss them.
              </p>
            </section>
          </>
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
          Telegram alerts are on. You’ll receive a message whenever GradRadar detects a new job
          posting, so you can apply early.
        </p>
        <button className="mt-4 bg-red-600 hover:bg-red-700" disabled={busy} onClick={onStop}>
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
