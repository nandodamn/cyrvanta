import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const api = readFileSync(resolve(process.cwd(), "src", "api.ts"), "utf-8");

describe("the action menu comes from the server", () => {
  it("asks which actions are permitted rather than deciding alone", () => {
    // Two sets of rules drift apart, and the one in the browser is the one an
    // attacker can read. The server is the authority; this only draws it.
    expect(api).toContain("/actions");
    expect(app).toContain("getIncidentActions");
    expect(app).toContain('queryKey: ["incident-actions"');
  });

  it("intersects with the state machine so a stale answer cannot widen the menu", () => {
    // The permitted list is a filter over the transitions that exist, never a
    // replacement for them: a cached or malformed response must not be able to
    // offer a move the state machine does not allow.
    expect(app).toContain("INCIDENT_TRANSITIONS[incident.data.status]");
    expect(app).toContain("permitted.has(`transition:${target}`)");
  });

  it("hides what the person cannot do instead of disabling it", () => {
    // An action shown and refused teaches people not to trust the screen.
    expect(app).toContain("hidden={!mayAssign}");
    expect(app).toContain("noTransitionsAvailable");
  });
});
