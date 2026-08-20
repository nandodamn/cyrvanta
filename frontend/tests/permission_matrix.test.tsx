import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PermissionMatrix } from "../src/App";
import "../src/i18n";

const PERMISSIONS = [
  { id: "p1", code: "incident.read", description: "Leer incidentes" },
  { id: "p2", code: "incident.close", description: "Cerrar un incidente" },
  { id: "p3", code: "response.approve", description: "Aprobar respuestas" },
];

function renderMatrix(granted: string[] = [], readOnly = false) {
  return render(
    <form>
      <PermissionMatrix permissions={PERMISSIONS} granted={new Set(granted)} readOnly={readOnly} />
    </form>,
  );
}

describe("permission matrix", () => {
  it("keeps filtered-out permissions in the form", () => {
    // The form collects values with FormData.getAll, which only sees inputs
    // that are in the DOM. Rendering only the matches would strip every
    // permission outside the filter the moment someone searched and saved.
    const { container } = renderMatrix(["p1", "p3"]);

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "incident" } });

    const checked = Array.from(
      container.querySelectorAll<HTMLInputElement>('input[name="permission_ids"]'),
    ).filter((input) => input.checked);
    expect(checked.map((input) => input.value).sort()).toEqual(["p1", "p3"]);
  });

  it("says what a permission does in the reader's language", () => {
    renderMatrix();
    // Groups start collapsed when nothing in them is granted -- that is what
    // turns fifty-six checkboxes into nineteen lines -- so the group is opened
    // the way a person would open it.
    fireEvent.click(screen.getByText("Incidentes"));
    // The stored description is written for whoever built the feature and
    // exists only in English. The catalogue entry says the same thing in
    // operational terms, in both languages.
    expect(screen.getByText("Cerrar o reabrir un incidente")).toBeVisible();
  });

  it("falls back to the stored description for a permission it does not know", () => {
    // A permission added later must still show something rather than its
    // bare code while its label is being written.
    render(
      <form>
        <PermissionMatrix
          permissions={[{ id: "px", code: "future.thing", description: "Stored text" }]}
          granted={new Set()}
          readOnly={false}
        />
      </form>,
    );
    fireEvent.click(screen.getByText("future"));
    expect(screen.getByText("Stored text")).toBeVisible();
  });

  it("marks the permissions that grant authority or cannot be undone", () => {
    renderMatrix(["p1", "p2", "p3"]);
    const badges = screen.getAllByText(/alto impacto|high impact/i);
    expect(badges).toHaveLength(2); // incident.close and response.approve
  });

  it("refuses edits on a system role while still showing what it grants", () => {
    renderMatrix(["p1"], true);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.every((box) => (box as HTMLInputElement).disabled)).toBe(true);
    expect(screen.getByText("incident.read")).toBeVisible();
  });
});
