import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const supabaseMock = vi.hoisted(() => {
  const authStateListeners: Array<(event: string, session: unknown) => void> = [];
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
      onAuthStateChange: vi.fn((callback: (event: string, session: unknown) => void) => {
        authStateListeners.push(callback);
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      }),
      signInWithIdToken: vi.fn().mockResolvedValue({ error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
    authStateListeners,
  };
});

vi.mock("./supabase", () => ({ supabase: supabaseMock }));

import { App } from "./App";

const response = {
  items: [
    {
      id: "1",
      company_name: "Figma",
      title: "Platform Engineer, New Grad",
      apply_url: "https://jobs.example.com/figma",
      location: "Boston, MA",
      listed_at: "2026-09-14T10:00:00Z",
      first_seen_at: "2026-09-14T11:00:00Z",
      sources: [{ name: "simplify", url: "https://github.com/SimplifyJobs/New-Grad-Positions" }],
    },
  ],
  offset: 0,
  limit: 25,
  total: 26,
  source_freshness: [
    {
      name: "simplify",
      url: "https://github.com/SimplifyJobs/New-Grad-Positions",
      last_successful_sync_at: "2026-09-14T11:00:00Z",
    },
    {
      name: "speedyapply",
      url: "https://github.com/speedyapply/2027-SWE-College-Jobs",
      last_successful_sync_at: null,
    },
  ],
};

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    supabaseMock.authStateListeners.length = 0;
    window.history.replaceState({}, "", "/");
  });

  it("renders jobs, freshness, and safe external links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    expect(await screen.findByText("Platform Engineer, New Grad")).toBeVisible();
    expect(screen.getByText(/Tracker freshness:/)).toBeVisible();
    const applicationLink = screen.getByRole("link", { name: /Open application link for Figma/ });
    expect(applicationLink).toHaveAttribute("target", "_blank");
    expect(applicationLink).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByLabelText("Sign in with Google")).toBeVisible();
  });

  it("shows the FAQ at its own URL without loading the job feed", () => {
    window.history.replaceState({}, "", "/faq");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(screen.getByRole("heading", { name: "How GradRadar works" })).toBeVisible();
    expect(
      screen.getByText(/every 15 minutes from 7:00 AM through 8:45 PM Pacific/i),
    ).toBeVisible();
    expect(screen.getByText(/visa or sponsorship assessment/i)).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders the configured Google sign-in control", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    expect(screen.getByLabelText("Sign in with Google")).toBeVisible();
  });

  it("renders source-supplied HTML in company names as plain text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...response,
          items: [
            {
              ...response.items[0],
              company_name: '<a href="https://example.com"><strong>SpaceX</strong></a>',
            },
          ],
        }),
      }),
    );
    render(<App />);

    expect(await screen.findByText("SpaceX")).toBeVisible();
    expect(screen.queryByText(/<strong>/)).not.toBeInTheDocument();
  });

  it("resets to the first page when a filter changes and advances within bounds", async () => {
    window.history.replaceState({}, "", "/?page=2");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByLabelText("Page 2 of 2");
    fireEvent.change(screen.getByLabelText("Location"), { target: { value: "Boston" } });
    await waitFor(() => expect(window.location.search).toContain("location=Boston"));
    expect(window.location.search).not.toContain("page=");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(window.location.search).toContain("page=2"));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows a compact paginator and GradRadar footer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    expect(await screen.findByText("Showing 1–25 of 26")).toBeVisible();
    expect(screen.getByRole("button", { name: "1" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("GradRadar");
  });

  it("returns an out-of-range shared page to the last available page", async () => {
    window.history.replaceState({}, "", "/?page=99");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await waitFor(() =>
      expect(window.location.search).toBe("?sort_by=listed_at&sort_direction=desc&page=2"),
    );
  });

  it("updates URL-backed sorting from the Company and Listed headers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    fireEvent.click(screen.getByRole("button", { name: "Company" }));
    await waitFor(() => expect(window.location.search).toContain("sort_by=company_name"));
    expect(window.location.search).toContain("sort_direction=asc");
    fireEvent.click(screen.getByRole("button", { name: "Listed" }));
    await waitFor(() => expect(window.location.search).toContain("sort_by=listed_at"));
    expect(window.location.search).toContain("sort_direction=desc");
  });

  it("shows a retryable API error and clears empty filters", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...response, items: [], total: 0 }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No jobs match these filters.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows the signed-in account without the Google button", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    const session = { user: { id: "user-1", email: "user@example.com" } };
    await waitFor(() => expect(supabaseMock.authStateListeners).toHaveLength(1));
    supabaseMock.authStateListeners[0]?.("SIGNED_IN", session);

    expect(await screen.findByText("user@example.com")).toBeVisible();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeVisible();
    expect(screen.queryByLabelText("Sign in with Google")).not.toBeInTheDocument();
  });

  it("clears an auth error after a successful sign-out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    supabaseMock.auth.signOut.mockResolvedValueOnce({ error: new Error("sign-out failed") });
    render(<App />);

    await waitFor(() => expect(supabaseMock.authStateListeners).toHaveLength(1));
    supabaseMock.authStateListeners[0]?.("SIGNED_IN", {
      user: { id: "user-1", email: "user@example.com" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("sign-out failed");

    supabaseMock.auth.signOut.mockResolvedValueOnce({ error: null });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("explains when Google Identity Services fails to load", async () => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    document.head.append(script);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await waitFor(() => expect(screen.getByLabelText("Sign in with Google")).toBeVisible());
    script.dispatchEvent(new Event("error"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Google sign-in is unavailable. Refresh and try again.",
    );
    script.remove();
  });

  it("exchanges the Google credential with Supabase using a nonce", async () => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    document.head.append(script);
    const initialize = vi.fn();
    const renderButton = vi.fn();
    vi.stubGlobal("google", { accounts: { id: { initialize, renderButton } } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await waitFor(() => expect(initialize).toHaveBeenCalledOnce());
    const configuration = initialize.mock.calls[0]?.[0];
    expect(configuration.client_id).toMatch(/\.apps\.googleusercontent\.com$/);
    expect(configuration.nonce).toMatch(/^[0-9a-f]{64}$/);
    configuration.callback({ credential: "google-id-token" });
    await waitFor(() =>
      expect(supabaseMock.auth.signInWithIdToken).toHaveBeenCalledWith({
        provider: "google",
        token: "google-id-token",
        nonce: expect.any(String),
      }),
    );
    expect(supabaseMock.auth.signInWithIdToken.mock.calls[0]?.[0].nonce).toHaveLength(44);
    script.remove();
  });
});
