/**
 * Collaboration is the part of the model most easily undone by a screen.
 * The backend refuses a collaborator's attempt to judge a case; a panel that
 * offers those buttons anyway teaches people the product is broken.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const app = readFileSync(resolve(process.cwd(), "src", "App.tsx"), "utf-8");
const translations = readFileSync(resolve(process.cwd(), "src", "i18n.ts"), "utf-8");
const collapsed = app.replace(/\s+/g, " ");

describe("collaborators", () => {
  it("only offers adding and removing to someone the server lets update the case", () => {
    // A reader without incident.update sees the list -- who was brought near a
    // case is part of its record -- and no controls.
    expect(collapsed).toContain(
      '<Collaborators incidentId={id} mayManage={permitted.has("update")} />',
    );
    expect(collapsed).toContain("{mayManage && (");
  });

  it("asks why someone is being brought in", () => {
    // At the moment the reason is still known, rather than reconstructed from
    // a timestamp months later.
    expect(collapsed).toContain("collaboratorReason");
  });

  it("reuses the search picker rather than a list capped at a page of users", () => {
    expect(collapsed).toContain("<AssigneeCombobox value={userId} onChange={setUserId} />");
  });

  it("says in both languages that collaborating is not deciding", () => {
    expect(translations).toContain("no pueden darlo por resuelto");
    expect(translations).toContain("they cannot resolve, close or reassign it");
  });
});
