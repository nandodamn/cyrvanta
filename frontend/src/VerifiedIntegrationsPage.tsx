import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getIntegrationHealth, IntegrationHealth } from "./api";


function modeLabel(
  mode: IntegrationHealth["mode"],
  t: (key: string) => string,
): string {
  if (mode === "simulated") return t("activitySource.simulated");
  if (mode === "live") return t("activitySource.live");
  return t("unavailable");
}


export function VerifiedIntegrationsPage() {
  const { t } = useTranslation();
  const health = useQuery({
    queryKey: ["integration-health"],
    queryFn: getIntegrationHealth,
    refetchInterval: 60_000,
  });
  const integrations = health.data ?? [];
  const healthy = integrations.filter((item) => item.healthy).length;
  const simulated = integrations.filter((item) => item.mode === "simulated").length;

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("securityDataSources")}</p>
          <h1>{t("integrations")}</h1>
          <p className="muted">{t("connectorHealth")}</p>
        </div>
      </div>

      {health.isLoading && <p className="muted" role="status">{t("loading")}</p>}
      {health.isError && <p className="error" role="alert">{t("loadError")}</p>}
      {!health.isLoading && !health.isError && integrations.length === 0 && (
        <p className="muted">{t("emptyState")}</p>
      )}

      {integrations.length > 0 && (
        <>
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 180px), 1fr))",
              gap: "0.75rem",
              marginBottom: "1rem",
            }}
            aria-label={t("connectorHealth")}
          >
            <article className="panel">
              <span className="muted">{t("platformServices")}</span>
              <strong style={{ display: "block", fontSize: "1.35rem" }}>
                {integrations.length}
              </strong>
            </article>
            <article className="panel">
              <span className="muted">{t("healthy")}</span>
              <strong style={{ display: "block", fontSize: "1.35rem" }}>{healthy}</strong>
            </article>
            <article className="panel">
              <span className="muted">{t("activitySource.simulated")}</span>
              <strong style={{ display: "block", fontSize: "1.35rem" }}>{simulated}</strong>
            </article>
          </section>

          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))",
              gap: "1rem",
            }}
          >
            {integrations.map((item) => (
              <article className="panel" key={item.code}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                  }}
                >
                  <strong>{item.code}</strong>
                  <span className={item.healthy ? "status success" : "status warning"}>
                    {item.healthy ? t("healthy") : t("unavailable")}
                  </span>
                </div>
                <dl style={{ marginBottom: 0 }}>
                  <dt className="muted">{t("connectorType")}</dt>
                  <dd>{modeLabel(item.mode, t)}</dd>
                  <dt className="muted">{t("connectorHealth")}</dt>
                  <dd style={{ overflowWrap: "anywhere" }}>{item.detail}</dd>
                </dl>
              </article>
            ))}
          </section>
        </>
      )}
    </>
  );
}
