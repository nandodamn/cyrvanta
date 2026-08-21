import { useTranslation } from "react-i18next";

/** The three things a list can be before it has anything to show.
 *
 * Lives in its own module so pages loaded lazily can use it without importing
 * the shell that loads them.
 */
export function PageState({
  loading,
  error,
  empty,
}: {
  loading: boolean;
  error: boolean;
  empty: boolean;
}) {
  const { t } = useTranslation();
  if (loading)
    return (
      <p className="status-message" role="status">
        {t("loading")}
      </p>
    );
  if (error)
    return (
      <p className="status-message status-error" role="alert">
        {t("loadError")}
      </p>
    );
  if (empty) return <p className="status-message">{t("emptyState")}</p>;
  return null;
}
