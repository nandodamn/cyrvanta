import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

export function ApiKeysPage() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(false);
  const [url, setUrl] = useState("http://localhost:5678");
  const [apiKey, setApiKey] = useState("");
  const [prepared, setPrepared] = useState(false);

  const clear = () => {
    setApiKey("");
    setPrepared(false);
  };

  const prepareHandoff = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPrepared(true);
  };

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{t("controlPlane")}</p>
          <h1>{t("apiKeys.title")}</h1>
          <p className="muted">{t("apiKeys.intro")}</p>
        </div>
      </div>

      <section className="panel secret-boundary" aria-labelledby="secret-boundary-title">
        <div>
          <p className="eyebrow">{t("apiKeys.securityBoundary")}</p>
          <h2 id="secret-boundary-title">{t("apiKeys.memoryOnlyTitle")}</h2>
        </div>
        <p>{t("apiKeys.memoryOnlyHelp")}</p>
        <ul>
          <li>{t("apiKeys.noPersistence")}</li>
          <li>{t("apiKeys.noNetwork")}</li>
          <li>{t("apiKeys.externalStore")}</li>
        </ul>
      </section>

      <form className="api-key-form" autoComplete="off" onSubmit={prepareHandoff}>
        <section className="panel api-key-card">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">n8n</p>
              <h2>{t("apiKeys.normalConfiguration")}</h2>
            </div>
            <label className="toggle-control">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => {
                  setEnabled(event.target.checked);
                  setPrepared(false);
                }}
              />
              <span>{t("apiKeys.useN8n")}</span>
            </label>
          </div>

          <label htmlFor="n8n-url">{t("apiKeys.url")}</label>
          <input
            id="n8n-url"
            type="url"
            value={url}
            disabled={!enabled}
            onChange={(event) => {
              setUrl(event.target.value);
              setPrepared(false);
            }}
            autoComplete="url"
            maxLength={2048}
          />

          <label htmlFor="n8n-api-key">{t("apiKeys.value")}</label>
          <input
            id="n8n-api-key"
            type="password"
            value={apiKey}
            disabled={!enabled}
            onChange={(event) => {
              setApiKey(event.target.value);
              setPrepared(false);
            }}
            autoComplete="new-password"
            spellCheck={false}
            maxLength={4096}
          />
          <small>{t("apiKeys.replaceOnlyHelp")}</small>
        </section>

        <details className="panel advanced-secrets">
          <summary>{t("apiKeys.advanced")}</summary>
          <p className="muted">{t("apiKeys.internalKeysHelp")}</p>
          <div className="admin-list">
            <div>
              <strong>N8N_DISPATCH_KEY</strong>
              <span className="key-state ready">{t("apiKeys.automatic")}</span>
            </div>
            <div>
              <strong>N8N_CALLBACK_KEY</strong>
              <span className="key-state ready">{t("apiKeys.automatic")}</span>
            </div>
          </div>
        </details>

        <section className="panel key-handoff">
          <div>
            <p className="eyebrow">{t("apiKeys.handoff")}</p>
            <h2>{t("apiKeys.handoffTitle")}</h2>
          </div>
          {prepared && (
            <p className="status-message" role="status">
              {t("apiKeys.prepared")}
            </p>
          )}
          <div className="form-actions">
            <button type="submit" disabled={!enabled || !url || !apiKey}>
              {t("apiKeys.prepare")}
            </button>
            <button className="ghost" type="button" onClick={clear}>
              {t("apiKeys.clear")}
            </button>
          </div>
        </section>
      </form>
    </>
  );
}
