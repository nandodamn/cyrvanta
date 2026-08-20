/**
 * The checklist is the point: an analyst should learn what the case still
 * lacks by reading it, not by pressing resolve and being refused.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const translations = readFileSync(resolve(process.cwd(), "src", "i18n.ts"), "utf-8");

const collapsed = source.replace(/\s+/g, " ");

describe("technical file", () => {
  it("names every requirement the server can withhold a resolution for", () => {
    // Kept in step with MissingRequirement on the backend. A requirement the
    // server enforces and the screen never mentions is a refusal with no
    // explanation.
    for (const requirement of [
      "diagnosis",
      "root_cause",
      "resolution",
      "technical_note",
      "evidence",
    ]) {
      expect(collapsed).toContain(`"${requirement}"`);
      expect(translations).toContain(`${requirement}:`);
    }
  });

  it("asks the server what is missing instead of working it out itself", () => {
    // Two copies of the rule drift, and the copy on the screen is the one
    // nobody notices has gone wrong.
    expect(collapsed).toContain("getResolutionReadiness(incidentId)");
  });

  it("offers recording that the cause could not be determined", () => {
    // Without it the honest ending is unreachable and the pressure is to
    // invent a cause to get the case closed.
    expect(collapsed).toContain("root_cause_undetermined");
  });

  it("refreshes the available actions once an entry is filed", () => {
    // Resolve becomes possible the moment the file is complete; a menu that
    // only catches up on reload teaches people not to trust the screen.
    expect(collapsed).toContain('queryKey: ["incident-actions", incidentId]');
  });

  it("says both requirement and slot names in Spanish and English", () => {
    expect(translations).toContain("Causa raiz no determinada");
    expect(translations).toContain("Root cause undetermined");
  });
});
