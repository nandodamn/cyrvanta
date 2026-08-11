import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getNetworkTopology } from "./api";


export function SecurityTopologyPanel() {
  const { t, i18n } = useTranslation();
  const topology = useQuery({
    queryKey: ["operations", "topology"],
    queryFn: getNetworkTopology,
    refetchInterval: 60_000,
  });
  const nodes = topology.data?.nodes ?? [];

  return (
    <article
      className="panel topology-panel"
      style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("monitoredEnvironment")}</p>
          <h2 style={{ margin: "4px 0 0" }}>{t("securityTopology")}</h2>
        </div>
      </div>

      {topology.isLoading && <p className="muted" role="status">{t("loading")}</p>}
      {topology.isError && <p className="error" role="alert">{t("loadError")}</p>}
      {!topology.isLoading && !topology.isError && nodes.length === 0 && (
        <p className="muted">{t("emptyState")}</p>
      )}

      {nodes.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
            gap: "0.75rem",
          }}
        >
          {nodes.map((node) => (
            <article className="panel" key={node.id}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "0.75rem",
                }}
              >
                <strong>{node.name}</strong>
                <span className="status">{node.status}</span>
              </div>
              <p style={{ overflowWrap: "anywhere" }}>{node.ip_address}</p>
              <p className="muted">{node.subnet}</p>
            </article>
          ))}
        </div>
      )}

      {topology.data?.updated_at && (
        <small className="muted">
          {t("activityUpdated", {
            time: new Date(topology.data.updated_at).toLocaleString(i18n.language),
          })}
        </small>
      )}
    </article>
  );
}
