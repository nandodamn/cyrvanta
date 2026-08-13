import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";


describe("human approval rationale", () => {
  it("requires analyst input and does not synthesize an approval reason", () => {
    const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf8");
    const api = readFileSync(resolve(process.cwd(), "src", "api.ts"), "utf8");

    expect(app).toContain('placeholder={t("approvalReasonPlaceholder")}');
    expect(app).toContain("reason: approvalReasons[decision.approval_request_id!]");
    expect(api).toContain("reason: reason.trim()");
    expect(api).not.toContain("Independent approval after reviewing the real action scope");
  });
});
