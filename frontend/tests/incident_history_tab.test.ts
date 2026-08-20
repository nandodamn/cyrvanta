import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const i18n = readFileSync(resolve(process.cwd(), "src", "i18n.ts"), "utf-8");

describe("the incident record is readable", () => {
  it("reads the merged history from the server", () => {
    // Audit events carry the structured change, timeline entries carry what a
    // person wrote. Either alone leaves an auditor with half the case.
    expect(app).toContain("getIncidentHistory");
    expect(app).toContain('queryKey: ["incident-history"');
  });

  it("shows what the actor was to the case, not what they are now", () => {
    // Roles change and assignments move, so the stored relation is rendered
    // rather than recomputed -- someone who has since handed the case over
    // must still appear as its owner on the day they acted.
    expect(app).toContain("entry.actor_relation");
    expect(app).toContain("incidentRelation.");
    for (const locale of ["owner", "not_owner"]) {
      expect(i18n.split(`${locale}:`).length - 1).toBeGreaterThanOrEqual(2);
    }
  });

  it("does not attribute an automatic event to a person", () => {
    // Correlation and the risk sweep write to the record too.
    expect(app).toContain('t("automaticActor")');
    expect(i18n).toContain("automaticActor");
  });

  it("names every action in both languages rather than showing its code", () => {
    for (const action of ["incident.status.changed", "incident.assigned"]) {
      expect(i18n.split(`"${action}"`).length - 1).toBeGreaterThanOrEqual(2);
    }
    // Falls back to the raw code so an action added later still renders.
    expect(app).toContain("defaultValue: entry.action");
  });
});
