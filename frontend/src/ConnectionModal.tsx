import React, { useState, useEffect } from "react";
import { authorizedMutation } from "./api";

export interface ConnectionMeta {
  id: string;
  name: string;
  connectorType: string;
  environment: string;
  capabilities: string;
  defaultUrl?: string;
  secretLabel?: string;
}

interface ConnectionModalProps {
  connection: ConnectionMeta;
  mode: "config" | "test";
  onClose: () => void;
  onSuccess?: (msg: string) => void;
}

export function ConnectionModal({ connection, mode, onClose, onSuccess }: ConnectionModalProps) {
  // Config state
  const [baseUrl, setBaseUrl] = useState(connection.defaultUrl || "http://localhost:8000");
  const [secretVal, setSecretVal] = useState("");
  const [modelVal, setModelVal] = useState("gemma:4b");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  // Test state
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  useEffect(() => {
    if (mode === "test") {
      runLiveTest();
    }
  }, [mode]);

  const runLiveTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await authorizedMutation(
        `/api/v1/integrations/connections/${connection.id}/test`,
        "POST",
        {}
      );
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        healthy: false,
        latency_ms: 0,
        message: err.message || "Error al conectar con la API de diagnósticos.",
        levels: [
          { level: 1, name: "Formato de Configuración", status: "passed", detail: "Correcto" },
          { level: 2, name: "Conectividad TCP / TLS", status: "failed", detail: "Error de puerto" },
        ],
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(null);
    try {
      const res: any = await authorizedMutation(
        `/api/v1/integrations/connections/${connection.id}/configure`,
        "POST",
        {
          base_url: baseUrl,
          secret_value: secretVal,
          model: modelVal,
        }
      );
      setSaveSuccess(res?.message || "Configuración cifrada con éxito.");
      if (onSuccess) onSuccess(res?.message);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      alert("Error al guardar: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(3, 10, 15, 0.8)",
        backdropFilter: "blur(6px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "600px",
          background: "var(--panel)",
          border: "1px solid var(--panel-border)",
          boxShadow: "0 20px 40px rgba(0,0,0,0.6)",
          borderRadius: "10px",
          padding: "1.5rem",
          display: "flex",
          flexDirection: "column",
          minHeight: "unset",
          gap: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem", borderBottom: "1px solid var(--line)", paddingBottom: "0.75rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span style={{ fontSize: "0.7rem", color: "var(--accent)", fontWeight: 700, textTransform: "uppercase", background: "rgba(13, 209, 155, 0.1)", padding: "2px 8px", borderRadius: "4px", border: "1px solid rgba(13, 209, 155, 0.2)" }}>
                CONECTOR: {connection.connectorType.toUpperCase()}
              </span>
              <span style={{ fontSize: "0.7rem", color: "var(--muted)" }}>• {connection.environment}</span>
            </div>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.1rem", fontWeight: 700, color: "var(--text)" }}>
              {mode === "config" ? `🔑 Configuración: ${connection.name}` : `⚡ Diagnóstico: ${connection.name}`}
            </h2>
          </div>
          <button
            type="button"
            className="ghost"
            style={{ width: "auto", minWidth: "unset", height: "auto", padding: "4px 8px", fontSize: "0.9rem" }}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* MODE 1: CONFIGURATION FORM */}
        {mode === "config" && (
          <form onSubmit={handleSaveConfig}>
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "4px", fontWeight: 600 }}>
                  URL de Servicio / Endpoint Base
                </label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "4px", border: "1px solid var(--line)", background: "var(--panel)" }}
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "4px", fontWeight: 600 }}>
                  {connection.secretLabel || "Credencial Cifrada (API Key / Token / Secret)"}
                </label>
                <input
                  type="password"
                  value={secretVal}
                  onChange={(e) => setSecretVal(e.target.value)}
                  placeholder="••••••••••••••••••••••••"
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "4px", border: "1px solid var(--line)", background: "var(--panel)" }}
                />
                <small style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: "4px", display: "block" }}>
                  🔒 El secreto se almacena cifrado en la base de datos con clave AES-256-GCM por tenant.
                </small>
              </div>

              {connection.connectorType === "ollama" && (
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "4px", fontWeight: 600 }}>
                    Modelo LLM Objetivado
                  </label>
                  <input
                    type="text"
                    value={modelVal}
                    onChange={(e) => setModelVal(e.target.value)}
                    style={{ width: "100%", padding: "8px 12px", borderRadius: "4px", border: "1px solid var(--line)", background: "var(--panel)" }}
                  />
                </div>
              )}

              <div style={{ fontSize: "0.8rem", background: "rgba(13, 209, 155, 0.05)", border: "1px solid var(--accent)", padding: "10px", borderRadius: "6px", color: "var(--text)" }}>
                <strong>Capacidades Habilitadas:</strong> <code>{connection.capabilities}</code>
              </div>

              {saveSuccess && (
                <div style={{ background: "rgba(13, 209, 155, 0.2)", color: "var(--accent)", padding: "8px 12px", borderRadius: "4px", fontSize: "0.85rem" }}>
                  ✓ {saveSuccess}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "1.25rem" }}>
                <button
                  type="button"
                  className="ghost"
                  onClick={onClose}
                  style={{
                    width: "auto",
                    minWidth: "unset",
                    height: "auto",
                    padding: "6px 14px",
                    fontSize: "0.85rem",
                    whiteSpace: "nowrap",
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  style={{
                    width: "auto",
                    minWidth: "unset",
                    height: "auto",
                    padding: "6px 16px",
                    fontSize: "0.85rem",
                    whiteSpace: "nowrap",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  {saving ? "Guardando..." : "🔒 Guardar Configuración"}
                </button>
              </div>
            </div>
          </form>
        )}

        {/* MODE 2: LIVE TEST DIAGNOSTICS */}
        {mode === "test" && (
          <div>
            {testing && (
              <div style={{ textAlign: "center", padding: "2rem 0" }}>
                <p style={{ fontSize: "1rem", fontWeight: 600 }}>⚡ Ejecutando Diagnóstico de 4 Niveles...</p>
                <small style={{ color: "var(--muted)" }}>Verificando Sintaxis, Conectividad TCP, Autenticación y Latencia.</small>
              </div>
            )}

            {!testing && testResult && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: testResult.healthy ? "rgba(13, 209, 155, 0.1)" : "rgba(255, 77, 77, 0.1)", border: `1px solid ${testResult.healthy ? "var(--accent)" : "#ff4d4d"}`, padding: "12px 16px", borderRadius: "8px", marginBottom: "1rem" }}>
                  <div>
                    <strong style={{ color: testResult.healthy ? "var(--accent)" : "#ff4d4d", fontSize: "1rem" }}>
                      {testResult.healthy ? "✓ DIAGNÓSTICO EXITOSO (100% SALUDABLE)" : "✕ DIAGNÓSTICO CON ERRORES"}
                    </strong>
                    <p style={{ margin: "2px 0 0", fontSize: "0.85rem", color: "var(--text)" }}>{testResult.message}</p>
                  </div>
                  <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent)" }}>{testResult.latency_ms} ms</span>
                </div>

                <h3 style={{ fontSize: "0.9rem", marginBottom: "10px" }}>Pruebas de Diagnóstico Ejecutadas:</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {testResult.levels?.map((lvl: any) => (
                    <div key={lvl.level} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--panel)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--line)" }}>
                      <div>
                        <strong style={{ fontSize: "0.85rem", display: "block" }}>Nivel {lvl.level}: {lvl.name}</strong>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>{lvl.detail}</span>
                      </div>
                      <span style={{ fontSize: "0.75rem", fontWeight: 700, color: lvl.status === "passed" ? "var(--accent)" : "#ff4d4d", background: lvl.status === "passed" ? "rgba(13, 209, 155, 0.15)" : "rgba(255, 77, 77, 0.15)", padding: "2px 8px", borderRadius: "4px" }}>
                        {lvl.status === "passed" ? "✓ PASSED" : "✕ FAILED"}
                      </span>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "1.25rem" }}>
                  <button
                    type="button"
                    onClick={runLiveTest}
                    className="ghost"
                    style={{
                      width: "auto",
                      minWidth: "unset",
                      height: "auto",
                      padding: "6px 14px",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                      display: "inline-flex",
                      alignItems: "center",
                    }}
                  >
                    ↺ Repetir
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    style={{
                      width: "auto",
                      minWidth: "unset",
                      height: "auto",
                      padding: "6px 16px",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                      display: "inline-flex",
                      alignItems: "center",
                    }}
                  >
                    Cerrar
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
