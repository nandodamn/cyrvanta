/**
 * Following the machine's theme is the default, and following means keeping
 * up with it. A SOC is read at 3am as often as at midday; someone who has
 * already told their operating system how they want to read then should not
 * have to tell this one as well.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../src/api";
import App from "../src/App";
import { AuthProvider } from "../src/AuthContext";
import "../src/i18n";

/** A controllable `prefers-color-scheme`, which jsdom does not provide. */
function systemPrefersLight(initial: boolean) {
  const listeners = new Set<() => void>();
  let matches = initial;
  window.matchMedia = ((query: string) => ({
    media: query,
    get matches() {
      return matches;
    },
    onchange: null,
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.add(listener as () => void);
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.delete(listener as () => void);
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
  return (next: boolean) => {
    matches = next;
    act(() => listeners.forEach((listener) => listener()));
  };
}

function signIn() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "synthetic", token_type: "bearer" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.spyOn(api, "getMe").mockResolvedValue({
    id: "00000000-0000-0000-0000-000000000001",
    tenant_id: "00000000-0000-0000-0000-000000000002",
    email: "quien@example.invalid",
    display_name: "Quien Sea",
    roles: [{ code: "soc-analyst", name: "Analista SOC" }],
  });
  vi.spyOn(api, "getIncidents").mockResolvedValue([]);
  vi.spyOn(api, "getAlerts").mockResolvedValue([]);
  vi.spyOn(api, "getOperationalActivity24h").mockResolvedValue({
    window_start: "2026-07-31T12:00:00Z",
    window_end: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    source_mode: "EMPTY",
    totals: { alerts: 0, incidents: 0 },
    series: [],
  });

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const openAccount = async () =>
  fireEvent.click(await screen.findByRole("button", { expanded: false }));

const choice = (name: RegExp) => screen.getByRole("radio", { name });
const FOLLOW = /seguir al sistema|follow the system/i;
const LIGHT = /tema claro|light theme/i;
const DARK = /tema oscuro|dark theme/i;

describe("theme preference", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("follows the machine on arrival, without being asked", async () => {
    systemPrefersLight(true);
    signIn();
    await openAccount();

    expect(choice(FOLLOW)).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement).toHaveClass("light");
    // Nothing stored: absence is what "follow the system" means, so a stale
    // value can never quietly outrank the machine.
    expect(sessionStorage.getItem("theme")).toBeNull();
  });

  it("keeps up when the machine changes its mind", async () => {
    // Machines flip at dusk on their own. Reading the preference once at load
    // would leave the screen bright in a dark room an hour later.
    const setSystem = systemPrefersLight(false);
    signIn();
    await openAccount();
    expect(document.documentElement).not.toHaveClass("light");

    setSystem(true);
    expect(document.documentElement).toHaveClass("light");
  });

  it("stops following once someone chooses for themselves", async () => {
    const setSystem = systemPrefersLight(false);
    signIn();
    await openAccount();
    fireEvent.click(choice(LIGHT));

    expect(choice(FOLLOW)).toHaveAttribute("aria-checked", "false");
    expect(sessionStorage.getItem("theme")).toBe("light");

    // An explicit choice outranks the machine, including afterwards.
    setSystem(false);
    expect(document.documentElement).toHaveClass("light");
  });

  it("lets someone go back to following it", async () => {
    // A one-way door would make the default unreachable after a single click,
    // which is how people end up stuck on a theme they did not want.
    const setSystem = systemPrefersLight(false);
    signIn();
    await openAccount();
    fireEvent.click(choice(LIGHT));
    fireEvent.click(choice(FOLLOW));

    expect(sessionStorage.getItem("theme")).toBeNull();
    expect(document.documentElement).not.toHaveClass("light");
    setSystem(true);
    expect(document.documentElement).toHaveClass("light");
  });

  it("can be pinned dark on a machine set to light", async () => {
    // The case that matters for a night shift on a corporate laptop nobody is
    // allowed to reconfigure.
    systemPrefersLight(true);
    signIn();
    await openAccount();
    fireEvent.click(choice(DARK));

    expect(document.documentElement).not.toHaveClass("light");
    expect(sessionStorage.getItem("theme")).toBe("dark");
  });
});
