import {
  FlaskConical,
  Languages,
  Menu,
  Moon,
  RotateCcw,
  Settings2,
  Share2,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const mobileMenuTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!mobileMenuOpen) return;

    function closeOnOutsidePress(event: PointerEvent) {
      if (!mobileMenuRef.current?.contains(event.target as Node)) {
        setMobileMenuOpen(false);
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobileMenuOpen(false);
        mobileMenuTriggerRef.current?.focus();
      }
    }

    const focusTimer = window.setTimeout(() => {
      mobileMenuRef.current?.querySelector<HTMLElement>("[role='menuitem']")?.focus();
    }, 0);
    document.addEventListener("pointerdown", closeOnOutsidePress);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("pointerdown", closeOnOutsidePress);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileMenuOpen]);

  function runMobileAction(action: () => void, restoreFocus = true) {
    setMobileMenuOpen(false);
    if (!restoreFocus) mobileMenuTriggerRef.current?.focus();
    action();
    if (restoreFocus) window.setTimeout(() => mobileMenuTriggerRef.current?.focus(), 0);
  }

  function moveMobileMenuFocus(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("[role='menuitem']"));
    if (!items.length) return;

    event.preventDefault();
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    let nextIndex = currentIndex;
    if (event.key === "ArrowDown") nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
    else if (event.key === "ArrowUp") nextIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = items.length - 1;
    items[nextIndex]?.focus();
  }

  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true"><FlaskConical size={24} /></span>
        <div className="brand__copy">
          <div className="brand__title">{t("appName")}</div>
          <div className="brand__subtitle">{t("appTagline")}</div>
        </div>
      </div>
      <div className="header-actions" aria-label={t("moreActions")}>
        <button type="button" className="status-pill" onClick={props.onConnection} aria-label={connected ? t("connected") : t("disconnected")}>
          <span className={`status-dot ${connected ? "status-dot--ok" : ""}`} />
          <span className="status-label">{connected ? t("connected") : t("disconnected")}</span>
        </button>
        <button type="button" className="icon-button" onClick={props.onShare} title={t("share")} aria-label={t("share")}>
          <Share2 size={18} />
        </button>
        <button type="button" className="icon-button" onClick={props.onReset} title={t("reset")} aria-label={t("reset")}>
          <RotateCcw size={18} />
        </button>
        <button
          type="button"
          className="icon-button icon-button--text"
          onClick={props.onLocale}
          title={locale === "zh-TW" ? "English" : "繁體中文"}
          aria-label={locale === "zh-TW" ? "English" : "繁體中文"}
        >
          <Languages size={17} /><span>{t("language")}</span>
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={props.onTheme}
          title={theme === "dark" ? t("lightMode") : t("darkMode")}
          aria-label={theme === "dark" ? t("lightMode") : t("darkMode")}
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={props.onConnection}
          title={t("connection")}
          aria-label={t("connection")}
        >
          <Settings2 size={18} />
        </button>
      </div>

      <div className="mobile-header-actions" ref={mobileMenuRef}>
        <button
          type="button"
          className="status-pill mobile-status"
          onClick={props.onConnection}
          aria-label={connected ? t("connected") : t("disconnected")}
          title={connected ? t("connected") : t("disconnected")}
        >
          <span className={`status-dot ${connected ? "status-dot--ok" : ""}`} />
        </button>
        <button
          ref={mobileMenuTriggerRef}
          type="button"
          className="icon-button mobile-menu-trigger"
          onClick={() => setMobileMenuOpen((open) => !open)}
          aria-expanded={mobileMenuOpen}
          aria-haspopup="menu"
          aria-controls="mobile-action-menu"
          aria-label={mobileMenuOpen ? t("close") : t("moreActions")}
          title={mobileMenuOpen ? t("close") : t("moreActions")}
        >
          {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}
        </button>

        {mobileMenuOpen && (
          <div
            id="mobile-action-menu"
            className="mobile-action-menu"
            role="menu"
            aria-label={t("moreActions")}
            onKeyDown={moveMobileMenuFocus}
          >
            <button type="button" role="menuitem" onClick={() => runMobileAction(props.onShare)}>
              <Share2 size={18} /><span>{t("share")}</span>
            </button>
            <button type="button" role="menuitem" onClick={() => runMobileAction(props.onReset)}>
              <RotateCcw size={18} /><span>{t("reset")}</span>
            </button>
            <button type="button" role="menuitem" onClick={() => runMobileAction(props.onLocale)}>
              <Languages size={18} /><span>{locale === "zh-TW" ? "English" : "繁體中文"}</span>
            </button>
            <button type="button" role="menuitem" onClick={() => runMobileAction(props.onTheme)}>
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              <span>{theme === "dark" ? t("lightMode") : t("darkMode")}</span>
            </button>
            <button type="button" role="menuitem" onClick={() => runMobileAction(props.onConnection, false)}>
              <Settings2 size={18} /><span>{t("connection")}</span>
              <span className={`mobile-menu-status status-dot ${connected ? "status-dot--ok" : ""}`} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
