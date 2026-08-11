import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const api = readFileSync(resolve(process.cwd(), "src", "api.ts"), "utf-8");

describe("response proposal safety", () => {
  it("exposes only the explicit synthetic demo proposal helper", () => {
    expect(api).not.toContain("createResponseProposal");
    expect(api).not.toContain("192.168.1.105");
    expect(api).not.toContain('parameters: { execution_mode: "live" }');
    expect(api).not.toContain('action_type: "block-ip-address"');
    expect(api).toContain("createDemoResponseProposal");
    expect(api).toContain('parameters: { execution_mode: "demo" }');
  });
});
