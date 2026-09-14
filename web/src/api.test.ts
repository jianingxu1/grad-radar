import { describe, expect, it } from "vitest";

import { PAGE_SIZE, toSearchParams } from "./api";
import { filtersFromSearch, filtersToSearch } from "./filterState";

describe("job feed query state", () => {
  it("serializes API filters with repeated source parameters and an offset", () => {
    const params = toSearchParams({
      q: "platform",
      location: "New York",
      remote: "true",
      company: "Figma",
      postedWithinHours: "24",
      listedWithinDays: "7",
      sources: ["simplify", "speedyapply"],
      page: 2,
    });

    expect(params.get("offset")).toBe(String(PAGE_SIZE));
    expect(params.getAll("sources")).toEqual(["simplify", "speedyapply"]);
    expect(params.get("posted_within_hours")).toBe("24");
  });

  it("hydrates shareable filters and omits the first page from the URL", () => {
    const filters = filtersFromSearch("?q=platform&remote=false&sources=simplify&page=3");

    expect(filters).toMatchObject({
      q: "platform",
      remote: "false",
      sources: ["simplify"],
      page: 3,
    });
    expect(filtersToSearch({ ...filters, page: 1 })).not.toContain("page=");
  });
});
