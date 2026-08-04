import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getOperationalActivity24h } from "./api";

export function OperationalPulse() {
  const { t } = useTranslation();

  const activity = useQuery({
    queryKey: ["operations", "activity-24h"],
    queryFn: getOperationalActivity24h,
    refetchInterval: 60_000,
  });

  const maximum = Math.max(
    ...(activity.data?.series.map((bucket) => bucket.alerts + bucket.incidents) ?? [0]),
    1,
  );

  return (
    <article className="panel pulse-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{t("operationalPulse")}</p>
          <h2>{t("operationalPulseTitle")}</h2>
        </div>
        {activity.data && activity.data.source_mode !== "EMPTY" && (
          <span className={`preview-badge source-${activity.data.source_mode.toLowerCase()}`}>
            {t(`activitySource.${activity.data.source_mode.toLowerCase()}`)}
          </span>
        )}
      </div>

      {activity.isLoading && (
        <p className="status-message" role="status">
          {t("loading")}
        </p>
      )}
      {activity.isError && (
        <p className="status-message status-error" role="alert">
          {t("loadError")}
        </p>
      )}
      {activity.data?.source_mode === "EMPTY" && (
        <p className="status-message">{t("activityEmpty")}</p>
      )}

      {activity.data && activity.data.source_mode !== "EMPTY" && (
        <>
          <div className="activity-summary" aria-label={t("operationalPulseTitle")}>
            <span>
              {t("alerts")}: <strong>{activity.data.totals.alerts}</strong>
            </span>
            <span>
              {t("incidents")}: <strong>{activity.data.totals.incidents}</strong>
            </span>
          </div>
          <div className="signal-grid" role="list" aria-label={t("operationalPulseTitle")}>
            {activity.data.series.map((bucket) => {
              const total = bucket.alerts + bucket.incidents;
              const label = t("activityBucket", {
                time: new Date(bucket.bucket_start).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                }),
                alerts: bucket.alerts,
                incidents: bucket.incidents,
              });
              return (
                <i
                  key={bucket.bucket_start}
                  role="listitem"
                  aria-label={label}
                  title={label}
                  style={{ height: total === 0 ? "2px" : `${(total / maximum) * 100}%` }}
                />
              );
            })}
          </div>
          <p className="activity-updated">
            {t("activityUpdated", {
              time: new Date(activity.data.updated_at).toLocaleString(),
            })}
          </p>
        </>
      )}

      <div className="pulse-legend">
        <span>{t("telemetryIngestion")}</span>
        <span>{t("detections")}</span>
        <span>{t("incidentResponse")}</span>
      </div>
    </article>
  );
}
