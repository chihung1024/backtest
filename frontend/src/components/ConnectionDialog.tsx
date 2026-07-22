import { CheckCircle2, KeyRound, LoaderCircle, Server, X } from "lucide-react";
import { useEffect, useState } from "react";
import { checkHealth } from "../api";
import type { Translator } from "../i18n";
import type { ApiConnection } from "../types";

export function ConnectionDialog({
  open,
  connection,
  t,
  onClose,
  onSave,
}: {
  open: boolean;
  connection: ApiConnection;
  t: Translator;
  onClose: () => void;
  onSave: (connection: ApiConnection) => void;
}) {
  if (!open) return null;
  return (
    <ConnectionDialogContent
      connection={connection}
      t={t}
      onClose={onClose}
      onSave={onSave}
    />
  );
}

function ConnectionDialogContent({
  connection,
  t,
  onClose,
  onSave,
}: Omit<Parameters<typeof ConnectionDialog>[0], "open">) {
  const [draft, setDraft] = useState(connection);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  async function test() {
    setTesting(true);
    setStatus("idle");
    try {
      setStatus((await checkHealth(draft)) ? "ok" : "error");
    } catch {
      setStatus("error");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="connection-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <div>
            <span className="eyebrow">API</span>
            <h2 id="connection-title">{t("connection")}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>
        <div className="modal__body">
          <label className="field">
            <span className="field__label"><Server size={15} />{t("apiUrl")}</span>
            <input
              value={draft.baseUrl}
              onChange={(event) => setDraft({ ...draft, baseUrl: event.target.value })}
              placeholder="https://portfolio-backtest-api.run.app"
              inputMode="url"
            />
          </label>
          <label className="field">
            <span className="field__label"><KeyRound size={15} />{t("accessKey")}</span>
            <input
              type="password"
              value={draft.accessKey}
              onChange={(event) => setDraft({ ...draft, accessKey: event.target.value })}
              autoComplete="off"
            />
          </label>
          <p className="privacy-note">{t("connectionHint")}</p>
          {status === "ok" && <div className="inline-success"><CheckCircle2 size={17} />{t("connected")}</div>}
          {status === "error" && <div className="inline-error">{t("disconnected")}</div>}
        </div>
        <div className="modal__footer">
          <button type="button" className="button button--ghost modal__test-action" onClick={test} disabled={testing}>
            {testing && <LoaderCircle className="spin" size={16} />}{t("testConnection")}
          </button>
          <div className="modal__footer-spacer" />
          <button type="button" className="button button--subtle" onClick={onClose}>{t("cancel")}</button>
          <button
            type="button"
            className="button button--primary"
            onClick={() => { onSave(draft); onClose(); }}
          >
            {t("save")}
          </button>
        </div>
      </section>
    </div>
  );
}
