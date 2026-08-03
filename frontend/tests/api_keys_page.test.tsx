import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiKeysPage } from "../src/ApiKeysPage";
import "../src/i18n";

describe("n8n secure configuration staging", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows one normal API key and keeps internal keys metadata-only", () => {
    render(<ApiKeysPage />);

    const apiKey = screen.getByLabelText(/valor de la llave|key value/i);
    expect(apiKey).toHaveAttribute("type", "password");
    expect(apiKey).toBeDisabled();
    expect(screen.queryAllByLabelText(/valor de la llave|key value/i)).toHaveLength(1);

    fireEvent.click(screen.getByText(/configuración avanzada|advanced configuration/i));
    expect(screen.getByText("N8N_DISPATCH_KEY")).toBeVisible();
    expect(screen.getByText("N8N_CALLBACK_KEY")).toBeVisible();
    expect(screen.getAllByText(/administrada automáticamente|managed automatically/i)).toHaveLength(
      2,
    );
  });

  it("stages the key only in component memory and clears it", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<ApiKeysPage />);

    fireEvent.click(screen.getByRole("checkbox", { name: /usar n8n|use n8n/i }));
    const apiKey = screen.getByLabelText(/valor de la llave|key value/i);
    fireEvent.change(apiKey, { target: { value: "synthetic-not-a-real-secret" } });
    expect(apiKey).toHaveValue("synthetic-not-a-real-secret");

    fireEvent.click(screen.getByRole("button", { name: /borrar todo|clear all/i }));
    expect(apiKey).toHaveValue("");
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage.getItem("N8N_API_KEY")).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
