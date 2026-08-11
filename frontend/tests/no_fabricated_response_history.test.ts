import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const api = readFileSync(resolve(process.cwd(), "src", "api.ts"), "utf-8");

describe("response and audit history provenance", () => {
  it("contains no legacy rollback client or fabricated actors and counts", () => {
    expect(source).not.toContain("executeRollbackProposal");
    expect(api).not.toContain("executeRollbackProposal");
    expect(source).not.toContain("ldap-demo@cyrvanta.uy (2º Analista Aprobador)");
    expect(source).not.toContain('event.actor_user_id ? "demo@cyrvanta.uy"');
    expect(source).not.toContain('|| "127.0.0.1"');
    expect(source).not.toContain("isCompleted ? 2");
    expect(source).not.toContain("totalApprovals = 2");
    expect(source).not.toContain(': "synthetic-demo-user"');
    expect(source).toContain("decision.required_approvals");
    expect(source).toContain("entry.actor_user_id");
  });
});
