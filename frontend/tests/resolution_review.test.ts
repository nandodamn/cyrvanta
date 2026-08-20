/**
 * Closing a resolved case is a judgement about someone else's work. The screen
 * has to say whose before it offers the button that accepts it.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const translations = readFileSync(resolve(process.cwd(), "src", "i18n.ts"), "utf-8");
const collapsed = app.replace(/\s+/g, " ");

describe("resolution review", () => {
  it("appears only on a case that is actually awaiting review", () => {
    expect(collapsed).toContain('{incident.data.status === "resolved" && (');
  });

  it("names the resolver from the record, not from a page of users", () => {
    // The person who resolved a case need not be among the first hundred
    // users, and a banner that silently shows nobody is worse than none.
    expect(collapsed).toContain('entry.after.status === "resolved"');
    expect(collapsed).toContain("resolutionReviewUnknown");
  });

  it("says what each outcome means before either is taken", () => {
    expect(translations).toContain("Cerrar es aceptar la resolucion");
    expect(translations).toContain("Closing accepts the resolution");
  });

  it("explains a refusal to close instead of leaving an empty menu", () => {
    // Segregation of duties reads as a broken screen unless it is stated.
    expect(collapsed).toContain('mayClose={permitted.has("transition:closed")}');
    expect(translations).toContain("no puede aceptar su propio trabajo");
    expect(translations).toContain("cannot accept their own work");
  });
});
