import { describe, expect, it } from "vitest";

import { sourceLabel } from "./format";

describe("source labels", () => {
  it("preserves well-known company spelling", () => {
    expect(sourceLabel("ashby:openai")).toBe("OpenAI (Ashby)");
    expect(sourceLabel("lever:shieldai")).toBe("Shield AI (Lever)");
    expect(sourceLabel("lever:palantir")).toBe("Palantir (Lever)");
  });
});
