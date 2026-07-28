import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearSession, restoreSession } from "./api";

/* eslint-disable react-refresh/only-export-components */
type AuthState = {
  authenticated: boolean;
  ready: boolean;
  activate: () => void;
  signOut: () => Promise<void>;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"loading" | "authenticated" | "anonymous">("loading");
  useEffect(() => {
    let active = true;
    void restoreSession()
      .then((restored) => {
        if (active) setStatus(restored ? "authenticated" : "anonymous");
      })
      .catch(() => {
        if (active) setStatus("anonymous");
      });
    return () => {
      active = false;
    };
  }, []);
  const value = useMemo(
    () => ({
      authenticated: status === "authenticated",
      ready: status !== "loading",
      activate: () => setStatus("authenticated"),
      signOut: async () => {
        try {
          await clearSession();
        } finally {
          setStatus("anonymous");
        }
      },
    }),
    [status],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is required");
  return context;
}
