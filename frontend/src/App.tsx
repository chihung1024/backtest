import { AlertCircle, ArrowRight, Beaker, Check, LoaderCircle } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { checkHealth, runBacktest } from "./api";
import { AssetsTab } from "./components/AssetsTab";
import { ConnectionDialog } from "./components/ConnectionDialog";
import { Header } from "./components/Header";
import { SettingsTab } from "./components/SettingsTab";
import { freshDefaultState } from "./defaults";
import { translator } from "./i18n";
import {
  createShareUrl,
  loadConnection,
  loadLocale,
  loadModel,
  loadTheme,
  saveConnection,
  saveLocale,
  saveTheme,
} from "./storage";
import type { ApiConnection, BacktestResponse, Locale, Theme } from "./types";
import { buildRequest, validateModel } from "./utils";

type ConfigurationTab = "settings" | "assets";

const ResultsDashboard = lazy(() =>
  import("./components/ResultsDashboard").then((module) => ({
    default: module.ResultsDashboard,
  })),
);

export default function App() {
  const [model, setModel] = useState(loadModel);
  const [connection, setConnection] = useState<ApiConnection>(loadConnection);
  const [locale, setLocale] = useState<Locale>(loadLocale);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [tab, setTab] = useState<ConfigurationTab>("settings");
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [response, setResponse] = useState<BacktestResponse | null>(null);
  const [toast, setToast] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);
  const t = translator(locale);
  const activeRequest = buildRequest(model);
  const activeAssetCount = new Set(
    activeRequest.portfolios.flatMap((portfolio) => portfolio.assets.map((asset) => asset.symbol)),
  ).size;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = locale === "zh-TW" ? "zh-Hant" : "en";
    saveLocale(locale);
  }, [locale]);

  useEffect(() => {
    let active = true;
    void checkHealth(connection)
      .then((ok) => active && setConnected(ok))
      .catch(() => active && setConnected(false));
    return () => { active = false; };
  }, [connection]);

  async function submit() {
    const validation = validateModel(model);
    if (validation.length) {
      setErrors(validation);
      setTab(validation.some((error) => error.includes("權重") || error.includes("投資組合")) ? "assets" : "settings");
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const next = await runBacktest(connection, buildRequest(model));
      setResponse(next);
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      setConnected(true);
    } catch (error) {
      setErrors([error instanceof Error ? error.message : String(error)]);
      if (String(error).toLowerCase().includes("access key")) setConnectionOpen(true);
    } finally {
      setLoading(false);
    }
  }

  async function share() {
    try {
      await navigator.clipboard.writeText(createShareUrl(model));
      flash(t("shared"));
    } catch {
      flash(createShareUrl(model));
    }
  }

  function flash(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2800);
  }

  function updateConnection(next: ApiConnection) {
    const clean = { ...next, baseUrl: next.baseUrl.trim().replace(/\/$/, "") };
    setConnection(clean);
    saveConnection(clean);
  }

  return (
    <div className="app-shell">
      <Header
        t={t}
        locale={locale}
        theme={theme}
        connected={connected}
        onLocale={() => setLocale((current) => current === "zh-TW" ? "en" : "zh-TW")}
        onTheme={() => setTheme((current) => current === "dark" ? "light" : "dark")}
        onConnection={() => setConnectionOpen(true)}
        onShare={() => void share()}
        onReset={() => {
          window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
          setModel(freshDefaultState());
          setResponse(null);
          setErrors([]);
          setTab("settings");
        }}
      />

      <main>
        <section className="hero">
          <div className="hero__copy">
            <span className="eyebrow"><Beaker size={14} /> Portfolio Performance</span>
            <h1>{t("appName")}</h1>
            <p>{t("appTagline")}</p>
          </div>
          <div className="hero__facts" aria-label="Capabilities">
            <div><strong>5</strong><span>Portfolios</span></div>
            <div><strong>20</strong><span>Assets each</span></div>
            <div><strong>TWD · Daily</strong><span>Global valuation</span></div>
          </div>
        </section>

        <section className="configuration-card" aria-labelledby="configuration-title">
          <div className="configuration-card__title">
            <div>
              <span className="eyebrow">Model configuration</span>
              <h2 id="configuration-title">Portfolio Model Configuration</h2>
            </div>
            <span className="research-badge"><Check size={14} />{t("personalResearch")}</span>
          </div>

          <div className="configuration-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "settings"}
              className={tab === "settings" ? "active" : ""}
              onClick={() => setTab("settings")}
            >
              <span>01</span>{t("settings")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "assets"}
              className={tab === "assets" ? "active" : ""}
              onClick={() => setTab("assets")}
            >
              <span>02</span>{t("assets")}
            </button>
          </div>

          <div className="configuration-body" role="tabpanel">
            {tab === "settings" ? (
              <SettingsTab model={model} setModel={setModel} t={t} />
            ) : (
              <AssetsTab model={model} setModel={setModel} connection={connection} t={t} />
            )}
          </div>

          {errors.length > 0 && (
            <div className="error-panel" role="alert">
              <AlertCircle size={19} />
              <div><strong>{t("reviewErrors")}</strong><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></div>
            </div>
          )}

          <div className="run-bar">
            <p>
              {loading
                ? t("apiWakeHint")
                : `${activeRequest.portfolios.length} ${t("portfolio")} · ${activeAssetCount} ${t("asset")} · ${model.baseCurrency}`}
            </p>
            <button type="button" className="button button--run" onClick={() => void submit()} disabled={loading}>
              {loading ? <LoaderCircle className="spin" size={19} /> : <Beaker size={19} />}
              {loading ? t("running") : t("runBacktest")}
              {!loading && <ArrowRight size={18} />}
            </button>
          </div>
        </section>

        <div ref={resultRef} className="result-anchor">
          {response ? (
            <Suspense fallback={<section className="empty-results"><LoaderCircle className="spin" size={30} /></section>}>
              <ResultsDashboard response={response} t={t} locale={locale} />
            </Suspense>
          ) : (
            <section className="empty-results">
              <span><LineIcon /></span>
              <h2>{t("results")}</h2>
              <p>{t("noResults")}</p>
            </section>
          )}
        </div>

        <details className="methodology">
          <summary>{t("methodology")}</summary>
          <p>{t("methodologyText")}</p>
        </details>
      </main>

      <footer><p>{t("legal")}</p><a href="https://github.com/chihung1024/backtest" target="_blank" rel="noreferrer">GitHub</a></footer>

      <ConnectionDialog
        open={connectionOpen}
        connection={connection}
        t={t}
        onClose={() => setConnectionOpen(false)}
        onSave={updateConnection}
      />
      {toast && <div className="toast" role="status"><Check size={16} />{toast}</div>}
    </div>
  );
}

function LineIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 17l5-6 4 3 8-10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 21h18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
