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

  it("shows the description that the catalogue already carries", () => {
    renderMatrix();
    // Fifty-five dotted codes with no explanation is what made the screen
    // unreadable; the text was in the API all along.
    expect(screen.getByText("Cerrar un incidente")).toBeVisible();
  });

  it("marks the permissions that grant authority or cannot be undone", () => {
    renderMatrix();
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
