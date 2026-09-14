import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
    expect(screen.getByText("Google sign-in is not configured")).toBeVisible();
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

  it("explains when sign-in has not been configured", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
    render(<App />);

    await screen.findByText("Platform Engineer, New Grad");
    expect(screen.getByText("Google sign-in is not configured")).toBeVisible();
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
});
