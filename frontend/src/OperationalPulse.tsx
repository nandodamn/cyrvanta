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

  // A bar that is one pixel tall reads as "nothing happened", which is a lie
  // when something did. Real activity always gets a visible bar, and an empty
  // bucket gets no bar at all -- the two must never look alike.
  const MINIMUM_VISIBLE = 4;
  const barHeight = (total: number) =>
    total === 0 ? "0" : `max(${MINIMUM_VISIBLE}px, ${(total / maximum) * 100}%)`;

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
                // The hover target is the whole column, not the bar. A quiet
                // bucket draws four pixels or none at all, so anchoring the
                // tooltip to the bar itself would make the values unreachable
                // for exactly the buckets whose size is hardest to read.
                <span
                  key={bucket.bucket_start}
                  role="listitem"
                  aria-label={label}
                  data-tooltip={label}
                  className="signal-slot"
                >
                  <i
                    className={total === 0 ? "is-empty" : undefined}
                    style={{ height: barHeight(total) }}
                  />
                </span>
              );
            })}
          </div>
          {/* Both ends of a 24h window fall on the same clock time, so showing
              the hour at each end printed "15:20" twice and told the reader
              nothing. Relative labels cannot collide. */}
          <div className="activity-scale">
            <span>{t("activityWindowStart")}</span>
            <span>{t("activityWindowEnd")}</span>
          </div>
          <p className="activity-updated">
            {t("activityUpdated", {
              time: new Date(activity.data.updated_at).toLocaleString(),
            })}
          </p>
        </>
      )}

      {/* These used to read INGESTA / DETECCIONES / RESPUESTA, which implied
          the bars were split into three categories. They never were, so the
          labels invited exactly the wrong reading. The legend now says what a
          bar actually is. */}
      <div className="pulse-legend">
        <span>{t("activityLegend")}</span>
      </div>
    </article>
  );
}
