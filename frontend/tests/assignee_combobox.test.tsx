import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import { AssigneeCombobox } from "../src/App";
import "../src/i18n";

function person(id: string, name: string, email: string) {
  return { id, display_name: name, email, is_active: true } as unknown as api.AdminUser;
}

const ANA = person("11111111-1111-4111-8111-111111111111", "Ana Lopez", "ana@cyrvanta.uy");
const BRUNO = person("22222222-2222-4222-8222-222222222222", "Bruno Diaz", "bruno@cyrvanta.uy");

function renderCombobox(value = "") {
  const onChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AssigneeCombobox value={value} onChange={onChange} />
    </QueryClientProvider>,
  );
  return onChange;
}

describe("assignee combobox", () => {
  afterEach(() => vi.restoreAllMocks());

  it("asks the server for matches instead of filtering a capped local list", async () => {
    // The plain select loaded the first 100 users and listed them all. Past
    // that the hundred-and-first person could not be assigned, silently.
    const getUsers = vi.spyOn(api, "getUsers").mockResolvedValue([BRUNO]);
    renderCombobox();

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "bru" } });

    await waitFor(() =>
      expect(getUsers).toHaveBeenCalledWith(expect.objectContaining({ query: "bru" })),
    );
    expect(await screen.findByText("Bruno Diaz")).toBeVisible();
  });

  it("reports the chosen user by id, not by the text that was typed", async () => {
    vi.spyOn(api, "getUsers").mockResolvedValue([ANA, BRUNO]);
    const onChange = renderCombobox();

    fireEvent.focus(screen.getByRole("combobox"));
    fireEvent.mouseDown(await screen.findByText("Ana Lopez"));

    expect(onChange).toHaveBeenCalledWith(ANA.id);
  });

  it("names the person an incident is already assigned to", async () => {
    // Resolved by id: their name is not in a result set nobody has searched.
    vi.spyOn(api, "getUsers").mockResolvedValue([]);
    const getUserById = vi.spyOn(api, "getUserById").mockResolvedValue(ANA);
    renderCombobox(ANA.id);

    await waitFor(() => expect(getUserById).toHaveBeenCalledWith(ANA.id));
    expect(await screen.findByDisplayValue(/Ana Lopez/)).toBeVisible();
  });

  it("can always clear the assignment", async () => {
    vi.spyOn(api, "getUsers").mockResolvedValue([ANA]);
    vi.spyOn(api, "getUserById").mockResolvedValue(ANA);
    const onChange = renderCombobox(ANA.id);

    fireEvent.focus(screen.getByRole("combobox"));
    fireEvent.mouseDown(await screen.findByText(/^sin asignar$|^unassigned$/i));

    expect(onChange).toHaveBeenCalledWith("");
  });
});
