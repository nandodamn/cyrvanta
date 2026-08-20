import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const i18n = readFileSync(resolve(process.cwd(), "src", "i18n.ts"), "utf-8");

describe("incident provenance is legible", () => {
  it("labels where an incident came from instead of relying on the code prefix", () => {
    // The prefix already encoded this, but only for someone who knew the
    // convention: CORR- correlation, RISK- entity risk, INC- logged by hand.
    expect(app).toContain('code.startsWith("CORR-")');
    expect(app).toContain('code.startsWith("RISK-")');
    for (const key of ["incidentOriginCorrelated", "incidentOriginRisk", "incidentOriginManual"]) {
      expect(app).toContain(key);
      // Both locales, since bilingual is a product requirement rather than a
      // nicety, and a missing key renders as the raw code.
      expect(i18n.split(key).length - 1).toBeGreaterThanOrEqual(2);
    }
  });

  it("does not name a person or a role it cannot know", () => {
    // The prefix records that a human opened the case, not which human or
    // what they are. An incident a supervisor logged read "logged by an
    // analyst", which is an attribution the value cannot support -- in the
    // one product whose argument is that its record can be trusted.
    // Authorship belongs to the history, which knows it properly.
    for (const role of ["analista", "analyst", "supervisor", "auditor"]) {
      expect(i18n).not.toContain(`incidentOriginManual: "Registrado por ${role}`);
      expect(i18n.toLowerCase()).not.toContain(`incidentoriginmanual: "logged by an ${role}`);
    }
  });

  it("no longer offers to create a *real* incident", () => {
    // The wording only made sense against simulated incidents, which no longer
    // exist. To a client it advertised a demo mode and invited the question of
    // whether the other incidents are fake.
    expect(i18n).not.toContain("Crear incidente real");
    expect(i18n).not.toContain("Create real incident");
  });

  it("lets an analyst attach evidence to an incident", () => {
    expect(app).toContain("function EvidenceLinker");
    expect(app).toContain("linkIncidentAlerts");
    // Additive only: there is deliberately no detach, so nothing should offer one.
    expect(app).not.toContain("unlinkIncidentAlerts");
  });
});
