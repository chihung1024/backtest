import {
  FlaskConical,
  Languages,
  Moon,
  RotateCcw,
  Settings2,
  Share2,
  Sun,
} from "lucide-react";
import type { Locale, Theme } from "../types";
import type { Translator } from "../i18n";

interface HeaderProps {
  t: Translator;
  locale: Locale;
  theme: Theme;
  connected: boolean;
  onLocale: () => void;
  onTheme: () => void;
  onConnection: () => void;
  onShare: () => void;
  onReset: () => void;
}

export function Header(props: HeaderProps) {
  const { t, locale, theme, connected } = props;
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand__mark"><FlaskConical size={24} /></span>
        <div>
          <div className="brand__title">{t("appName")}</div>
          <div className="brand__subtitle">{t("appTagline")}</div>
        </div>
      </div>
      <div className="header-actions">
        <button type="button" className="status-pill" onClick={props.onConnection}>
          <span className={`status-dot ${connected ? "status-dot--ok" : ""}`} />
          <span className="status-label">{connected ? t("connected") : t("disconnected")}</span>
        </button>
        <button type="button" className="icon-button" onClick={props.onShare} title={t("share")}>
          <Share2 size={18} />
        </button>
        <button type="button" className="icon-button" onClick={props.onReset} title={t("reset")}>
          <RotateCcw size={18} />
        </button>
        <button
          type="button"
          className="icon-button icon-button--text"
          onClick={props.onLocale}
          title={locale === "zh-TW" ? "English" : "繁體中文"}
        >
          <Languages size={17} /><span>{t("language")}</span>
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={props.onTheme}
          title={theme === "dark" ? t("lightMode") : t("darkMode")}
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={props.onConnection}
          title={t("connection")}
        >
          <Settings2 size={18} />
        </button>
      </div>
    </header>
  );
}
