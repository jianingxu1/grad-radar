import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      refreshSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
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
    supabaseMock.auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    supabaseMock.auth.refreshSession.mockResolvedValue({ data: { session: null }, error: null });
    supabaseMock.authStateListeners.length = 0;
    window.history.replaceState({}, "", "/");
  });

  it("renders jobs, freshness, and safe external links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    expect(await screen.findByText("Platform Engineer, New Grad")).toBeVisible();
    const freshness = screen.getByLabelText("Source freshness");
    expect(within(freshness).getByText("Source freshness")).toHaveClass("uppercase");
    const githubToggle = within(freshness).getByText("GitHub sources (2)");
    const githubSection = githubToggle.closest("details");
    expect(githubSection).not.toHaveAttribute("open");
    fireEvent.click(githubToggle);
    expect(githubSection).toHaveAttribute("open");
    expect(githubToggle.closest("summary")).not.toHaveClass("uppercase");
    expect(freshness).toHaveTextContent(/Simplify: Sep 14, 2026/);
    expect(freshness).toHaveTextContent(/SpeedyApply: not checked yet/);
    fireEvent.click(githubToggle);
    expect(githubSection).not.toHaveAttribute("open");
    const applicationLink = screen.getByRole("link", { name: /Open application link for Figma/ });
    expect(applicationLink).toHaveAttribute("target", "_blank");
    expect(applicationLink).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByLabelText("Sign in with Google")).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: "Sign in to set up and receive telegram notifications!",
      }),
    ).toBeVisible();
  });

  it("links each source to its own application URL", async () => {
    const provenance = {
      ...response,
      items: [
        {
          ...response.items[0],
          sources: [
            {
              name: "simplify",
              url: "https://github.com/SimplifyJobs/New-Grad-Positions",
              apply_url: "https://tracker.example/apply",
            },
            {
              name: "greenhouse:figma",
              url: "https://job-boards.greenhouse.io/figma",
              apply_url: "https://job-boards.greenhouse.io/figma/jobs/123",
            },
          ],
        },
      ],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => provenance }));
    render(<App />);

    const listings = await screen.findByRole("region", { name: /Job listings/ });
    expect(within(listings).getByRole("link", { name: "Simplify" })).toHaveAttribute(
      "href",
      "https://tracker.example/apply",
    );
    expect(within(listings).getByRole("link", { name: "Figma (Greenhouse)" })).toHaveAttribute(
      "href",
      "https://job-boards.greenhouse.io/figma/jobs/123",
    );
  });

  it("keeps every job column in a horizontally scrollable table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    const listings = await screen.findByRole("region", {
      name: /Job listings, scroll horizontally/,
    });
    expect(listings).toHaveClass("overflow-x-auto");
    expect(listings).toHaveAttribute("tabindex", "0");
    const table = within(listings).getByRole("table");
    expect(table).toHaveClass("min-w-[700px]", "lg:min-w-[900px]", "text-xs", "lg:text-sm");
    for (const column of ["Company", "Role", "Location", "Listed", "Source"]) {
      expect(within(table).getByRole("columnheader", { name: new RegExp(column) })).not.toHaveClass(
        "hidden",
      );
    }
    const row = within(table).getByRole("row", { name: /Figma/ });
    expect(within(row).getAllByRole("cell")).toHaveLength(5);
    expect(row).toHaveTextContent("Boston, MA");
    expect(row).toHaveTextContent("Simplify");
    expect(within(table).getByRole("button", { name: /Company/ })).toHaveClass(
      "text-xs",
      "lg:text-sm",
    );
  });

  it("keeps the newest filter result when an older request resolves late", async () => {
    let resolveFirstResponse: ((value: typeof response) => void) | undefined;
    const firstResponse = new Promise<typeof response>((resolve) => {
      resolveFirstResponse = resolve;
    });
    const refreshedResponse = {
      ...response,
      items: [{ ...response.items[0], company_name: "Stripe" }],
    };
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(firstResponse.then((value) => ({ ok: true, json: async () => value })))
      .mockResolvedValueOnce({ ok: true, json: async () => refreshedResponse });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByPlaceholderText("Company or role"), {
      target: { value: "stripe" },
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Stripe")).toBeVisible();

    resolveFirstResponse?.(response);
    await waitFor(() => expect(screen.queryByText("Figma")).not.toBeInTheDocument());
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
    expect(
      screen.getByText(/How do I set up Telegram notifications to get the latest postings\?/i),
    ).toBeVisible();
    expect(screen.getByText(/Stop notifications.*send \/stop to the bot/i)).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 1, name: "Frequently asked questions" }),
    ).toBeVisible();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("© GradRadar");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves feed filters when navigating home", async () => {
    window.history.replaceState({}, "", "/?q=platform&page=2");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    fireEvent.click(screen.getByRole("button", { name: "FAQ" }));
    fireEvent.click(screen.getByRole("button", { name: "Back to jobs" }));

    expect(window.location.pathname).toBe("/");
    expect(new URLSearchParams(window.location.search).get("q")).toBe("platform");
    expect(new URLSearchParams(window.location.search).get("page")).toBe("2");
    expect(screen.getByLabelText("Search")).toHaveValue("platform");
  });

  it("renders the configured Google sign-in control", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    expect(screen.getByLabelText("Sign in with Google")).toBeVisible();
  });

  it("keeps the Google sign-in control after navigating from FAQ back to jobs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    const renderButton = vi.fn((container: HTMLElement) => {
      container.append(document.createElement("button"));
    });
    vi.stubGlobal("google", {
      accounts: { id: { initialize: vi.fn(), renderButton } },
    });
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    fireEvent.click(screen.getByRole("button", { name: "FAQ" }));
    fireEvent.click(screen.getByRole("button", { name: "Back to jobs" }));

    await waitFor(() => expect(renderButton).toHaveBeenCalledTimes(2));
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
    expect(screen.queryByLabelText("Location")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Workplace")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "platform" } });
    await waitFor(() => expect(window.location.search).toContain("q=platform"));
    expect(window.location.search).not.toContain("page=");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(window.location.search).toContain("page=2"));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows a grouped source checklist with all checked and can clear it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    fireEvent.click(screen.getByText("All sources (2)"));
    const sourceFilters = screen.getByRole("group", { name: "Source" });
    expect(within(sourceFilters).getByText("All sources (2)").closest("details")).toHaveClass(
      "max-w-96",
    );
    expect(within(sourceFilters).getByText("GitHub sources")).toBeVisible();
    expect(within(sourceFilters).getByText("Company job boards")).toBeVisible();
    const simplifyCheckbox = within(sourceFilters).getByRole("checkbox", { name: "Simplify" });
    const speedyCheckbox = within(sourceFilters).getByRole("checkbox", { name: "SpeedyApply" });
    expect(simplifyCheckbox).toBeChecked();
    expect(speedyCheckbox).toBeChecked();

    fireEvent.click(simplifyCheckbox);
    await waitFor(() => expect(window.location.search).toContain("sources=speedyapply"));
    expect(simplifyCheckbox).not.toBeChecked();
    fireEvent.click(within(sourceFilters).getByRole("button", { name: "Uncheck all" }));
    expect(within(sourceFilters).getByRole("button", { name: "Uncheck all" })).toHaveClass(
      "button-secondary",
    );
    expect(within(sourceFilters).getByRole("button", { name: "Check all" })).toHaveClass(
      "button-secondary",
    );
    expect(simplifyCheckbox).not.toBeChecked();
    expect(speedyCheckbox).not.toBeChecked();
    expect(window.location.search).toContain("sources=__none__");
    fireEvent.click(within(sourceFilters).getByRole("button", { name: "Check all" }));
    expect(simplifyCheckbox).toBeChecked();
    expect(speedyCheckbox).toBeChecked();
    expect(window.location.search).not.toContain("sources=");
  });

  it("selects a date range from the styled dropdown and closes it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    const dateFilter = screen.getByRole("group", { name: "Listed within" });
    const dateDetails = dateFilter.querySelector("details");
    expect(dateDetails).not.toHaveAttribute("open");
    fireEvent.click(dateFilter.querySelector("summary")!);
    expect(dateDetails).toHaveAttribute("open");
    fireEvent.click(within(dateFilter).getByRole("button", { name: "Past 24 hours" }));
    expect(dateDetails).not.toHaveAttribute("open");
    expect(dateFilter.querySelector("summary")).toHaveTextContent("Past 24 hours");
    await waitFor(() => expect(window.location.search).toContain("listed_within_hours=24"));

    fireEvent.click(dateFilter.querySelector("summary")!);
    fireEvent.click(within(dateFilter).getByRole("button", { name: "Any time" }));
    expect(window.location.search).not.toContain("listed_within_hours");
  });

  it("shows company board sources in feed filters", async () => {
    const boardResponse = {
      ...response,
      source_freshness: [
        ...response.source_freshness,
        {
          name: "lever:palantir",
          url: "https://jobs.lever.co/palantir",
          last_successful_sync_at: null,
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => boardResponse }),
    );
    render(<App />);

    await screen.findByText("All sources (3)");
    const freshness = screen.getByLabelText("Source freshness");
    const companyToggle = within(freshness).getByText("Company job boards (1)");
    const companySection = companyToggle.closest("details");
    expect(companySection).not.toHaveAttribute("open");
    fireEvent.click(companyToggle);
    expect(companySection).toHaveAttribute("open");
    expect(within(freshness).getByRole("link", { name: "Palantir (Lever)" })).toHaveAttribute(
      "href",
      "https://jobs.lever.co/palantir",
    );
    fireEvent.click(screen.getByText("All sources (3)"));
    const sourceFilters = screen.getByRole("group", { name: "Source" });
    fireEvent.click(within(sourceFilters).getByRole("button", { name: "Uncheck all" }));
    const checkbox = within(sourceFilters).getByRole("checkbox", { name: "Palantir (Lever)" });
    fireEvent.click(checkbox);
    expect(window.location.search).toContain("sources=lever%3Apalantir");
    expect(checkbox).toBeChecked();
  });

  it("shows the public Sources page without admin controls", async () => {
    window.history.replaceState({}, "", "/sources");
    const sources = [
      {
        id: "1",
        name: "greenhouse:stripe",
        url: "https://job-boards.greenhouse.io/stripe",
        platform: "greenhouse",
        board_name: "stripe",
        company_name: "Stripe",
        enabled: true,
        filter_config: {
          role_terms: ["software engineer"],
          level_terms: ["new grad"],
          exclude_terms: ["intern"],
        },
        last_successful_sync_at: null,
        last_sync_status: "success",
      },
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => sources }));
    render(<App />);

    expect(await screen.findByRole("link", { name: "Stripe" })).toHaveAttribute(
      "href",
      "https://job-boards.greenhouse.io/stripe",
    );
    expect(screen.getByRole("heading", { level: 1, name: "Sources" })).toBeVisible();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("© GradRadar");
    expect(screen.queryByRole("button", { name: "Add Source" })).not.toBeInTheDocument();
  });

  it("lets an admin add a board from the Sources page", async () => {
    window.history.replaceState({}, "", "/sources");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: {
        session: { user: { id: "admin", email: "admin@example.com" }, access_token: "token" },
      },
      error: null,
    });
    const created = {
      id: "1",
      name: "greenhouse:stripe",
      url: "https://job-boards.greenhouse.io/stripe",
      platform: "greenhouse",
      board_name: "stripe",
      company_name: "Stripe",
      enabled: true,
      filter_config: {
        role_terms: ["software engineer"],
        level_terms: ["new grad"],
        exclude_terms: ["intern"],
      },
      last_successful_sync_at: null,
      last_sync_status: null,
    };
    const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/v1/sources") && init?.method === "POST") {
        return { ok: true, json: async () => created };
      }
      if (url.endsWith("/v1/sources")) return { ok: true, json: async () => [] };
      if (url.endsWith("/v1/me/source-admin")) {
        return { ok: true, json: async () => ({ is_admin: true }) };
      }
      throw new Error(`unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Add Source" }));
    fireEvent.change(screen.getByLabelText("Board name"), { target: { value: "stripe" } });
    fireEvent.change(screen.getByLabelText("Company"), { target: { value: "Stripe" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add Source" })[1]);

    expect(await screen.findByRole("link", { name: "Stripe" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/v1/sources"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("lets an admin edit a board filter", async () => {
    window.history.replaceState({}, "", "/sources");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: {
        session: { user: { id: "admin", email: "admin@example.com" }, access_token: "token" },
      },
      error: null,
    });
    const source = {
      id: "1",
      name: "lever:palantir",
      url: "https://jobs.lever.co/palantir",
      platform: "lever",
      board_name: "palantir",
      company_name: "Palantir",
      enabled: true,
      filter_config: {
        role_terms: ["software engineer"],
        level_terms: ["new grad"],
        exclude_terms: ["intern"],
      },
      last_successful_sync_at: null,
      last_sync_status: null,
    };
    const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/v1/sources/1") && init?.method === "PATCH") {
        return { ok: true, json: async () => source };
      }
      if (url.endsWith("/v1/sources")) return { ok: true, json: async () => [source] };
      return { ok: true, json: async () => ({ is_admin: true }) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit filter" }));
    fireEvent.change(screen.getByLabelText(/level terms/i), {
      target: { value: "new grad, early career" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save filter" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/v1/sources/1"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
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

    const accountMenu = await screen.findByLabelText("Account menu");
    expect(accountMenu).toHaveTextContent("user@example.com");
    expect(accountMenu).not.toHaveClass("button-secondary");
    expect(screen.getByRole("button", { name: "Notifications" })).toBeVisible();
    fireEvent.click(accountMenu);
    const signOutButton = screen.getByRole("button", { name: "Sign out" });
    expect(signOutButton).toBeVisible();
    expect(signOutButton).toHaveClass("bg-transparent", "text-slate-700");
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Notifications" })).toBeVisible();
    expect(window.location.pathname).toBe("/settings/notifications");
    expect(screen.queryByLabelText("Sign in with Google")).not.toBeInTheDocument();
  });

  it("shows a login prompt on the notification page when signed out", () => {
    window.history.replaceState({}, "", "/settings/notifications");
    render(<App />);

    expect(screen.getByText("Don’t miss new jobs — sign in for Telegram alerts.")).toBeVisible();
  });

  it("shows Telegram setup steps below the connection box", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: {
        session: { user: { id: "user-1", email: "user@example.com" }, access_token: "token" },
      },
      error: null,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "not_connected", expires_at: null }),
      }),
    );

    render(<App />);

    const connectButton = await screen.findByRole("button", { name: "Connect Telegram" });
    const guide = screen.getByRole("region", { name: "How to set up Telegram alerts" });
    expect(
      connectButton.compareDocumentPosition(guide) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(guide).getAllByRole("listitem")).toHaveLength(4);
    expect(within(guide).getByText(/Telegram alerts connected/)).toBeVisible();
    expect(within(guide).getByText(/Turn on Telegram notifications/)).toBeVisible();
  });

  it("shows connected notification controls for an active Telegram connection", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: {
        session: { user: { id: "user-1", email: "user@example.com" }, access_token: "token" },
      },
      error: null,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "connected", expires_at: null }),
      }),
    );

    render(<App />);

    expect(screen.getByRole("heading", { level: 2, name: "Notifications" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Back to jobs" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("© GradRadar");
    expect(screen.getByText(/Manage Telegram alerts/i)).toBeVisible();
    expect(
      await screen.findByText(
        /You’ll receive a message whenever GradRadar detects a new job posting/i,
      ),
    ).toBeVisible();
    const stopNotificationsButton = screen.getByRole("button", { name: "Stop notifications" });
    expect(stopNotificationsButton).toBeVisible();
    expect(stopNotificationsButton).toHaveClass("bg-red-600", "hover:bg-red-700");
  });

  it("clears notification settings when the signed-in account changes", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    let session = { user: { id: "user-1", email: "first@example.com" }, access_token: "first" };
    supabaseMock.auth.getSession.mockImplementation(async () => ({
      data: { session },
      error: null,
    }));
    let resolveSecond: ((value: { ok: boolean; json: () => Promise<unknown> }) => void) | undefined;
    const secondResponse = new Promise<{ ok: boolean; json: () => Promise<unknown> }>((resolve) => {
      resolveSecond = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "connected", expires_at: null }),
      })
      .mockReturnValueOnce(secondResponse);
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("button", { name: "Stop notifications" })).toBeVisible();
    session = { user: { id: "user-2", email: "second@example.com" }, access_token: "second" };
    act(() => supabaseMock.authStateListeners[0]?.("SIGNED_IN", session));

    expect(screen.queryByRole("button", { name: "Stop notifications" })).not.toBeInTheDocument();
    expect(screen.getByText("Loading notification settings…")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await act(async () => {
      resolveSecond?.({
        ok: true,
        json: async () => ({ status: "not_connected", expires_at: null }),
      });
    });
    expect(await screen.findByRole("button", { name: "Connect Telegram" })).toBeVisible();
  });

  it("ignores a previous account's late notification settings response", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    let session = { user: { id: "user-1", email: "first@example.com" }, access_token: "first" };
    supabaseMock.auth.getSession.mockImplementation(async () => ({
      data: { session },
      error: null,
    }));
    let resolveFirst: ((value: { ok: boolean; json: () => Promise<unknown> }) => void) | undefined;
    const firstResponse = new Promise<{ ok: boolean; json: () => Promise<unknown> }>((resolve) => {
      resolveFirst = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "not_connected", expires_at: null }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    session = { user: { id: "user-2", email: "second@example.com" }, access_token: "second" };
    act(() => supabaseMock.authStateListeners[0]?.("SIGNED_IN", session));
    expect(await screen.findByRole("button", { name: "Connect Telegram" })).toBeVisible();

    await act(async () => {
      resolveFirst?.({
        ok: true,
        json: async () => ({ status: "connected", expires_at: null }),
      });
    });
    expect(screen.getByRole("button", { name: "Connect Telegram" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Stop notifications" })).not.toBeInTheDocument();
  });

  it("refreshes an expired session before retrying notification settings", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: { session: { user: { id: "user-1", email: "user@example.com" }, access_token: "old" } },
      error: null,
    });
    supabaseMock.auth.refreshSession.mockResolvedValue({
      data: { session: { access_token: "new" } },
      error: null,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "not_connected", expires_at: null }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("button", { name: "Connect Telegram" })).toBeVisible();
    expect(supabaseMock.auth.refreshSession).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[1]?.[1]?.headers).toMatchObject({ Authorization: "Bearer new" });
  });

  it("offers a retry when notification settings fail to load", async () => {
    window.history.replaceState({}, "", "/settings/notifications");
    supabaseMock.auth.getSession.mockResolvedValue({
      data: {
        session: { user: { id: "user-1", email: "user@example.com" }, access_token: "token" },
      },
      error: null,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "not_connected", expires_at: null }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Notification settings could not be loaded.",
    );
    expect(screen.queryByText("Loading notification settings…")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("button", { name: "Connect Telegram" })).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
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

  it("uses a narrower Google button on small screens and updates it on resize", async () => {
    vi.stubGlobal("innerWidth", 476);
    const renderButton = vi.fn();
    vi.stubGlobal("google", { accounts: { id: { initialize: vi.fn(), renderButton } } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await waitFor(() =>
      expect(renderButton).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        expect.objectContaining({ width: 200 }),
      ),
    );
    expect(screen.getByLabelText("Sign in with Google").parentElement).toHaveClass(
      "flex-wrap",
      "max-w-full",
    );

    vi.stubGlobal("innerWidth", 800);
    fireEvent.resize(window);
    await waitFor(() =>
      expect(renderButton).toHaveBeenLastCalledWith(
        expect.any(HTMLElement),
        expect.objectContaining({ width: 220 }),
      ),
    );
  });
});
