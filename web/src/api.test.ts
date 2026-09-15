import { describe, expect, it } from "vitest";

import { PAGE_SIZE, toSearchParams } from "./api";
import { filtersFromSearch, filtersToSearch } from "./filterState";

describe("job feed query state", () => {
  it("serializes API filters with repeated source parameters and an offset", () => {
    const params = toSearchParams({
      q: "platform",
      listedWithinHours: "168",
      sources: ["simplify", "speedyapply"],
      sortBy: "company_name",
      sortDirection: "asc",
      page: 2,
    });

    expect(params.get("offset")).toBe(String(PAGE_SIZE));
    expect(params.getAll("sources")).toEqual(["simplify", "speedyapply"]);
    expect(params.get("sort_by")).toBe("company_name");
    expect(params.get("sort_direction")).toBe("asc");
  });

  it("hydrates shareable filters and omits the first page from the URL", () => {
    const filters = filtersFromSearch(
      "?q=platform&sources=simplify&sort_by=company_name&sort_direction=asc&page=3",
    );

    expect(filters).toMatchObject({
      q: "platform",
      sources: ["simplify"],
      sortBy: "company_name",
      sortDirection: "asc",
      page: 3,
    });
    expect(filtersToSearch({ ...filters, page: 1 })).not.toContain("page=");
  });

  it("ignores an invalid listing-hours value in a shared URL", () => {
    expect(filtersFromSearch("?listed_within_hours=two-days").listedWithinHours).toBe("");
  });
});
