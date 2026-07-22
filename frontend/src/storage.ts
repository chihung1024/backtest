import { freshDefaultState, MAX_PORTFOLIOS, preferredPortfolioCount } from "./defaults";
import type { ApiConnection, BacktestFormState, Locale, Theme, WeightValue } from "./types";

const MODEL_KEY = "portfolio-lab:model:v2";
const LEGACY_MODEL_KEY = "portfolio-lab:model:v1";
const CONNECTION_KEY = "portfolio-lab:connection:v1";
const THEME_KEY = "portfolio-lab:theme";
const LOCALE_KEY = "portfolio-lab:locale";

export function loadModel(): BacktestFormState {
  const fromShare = readSharedModel();
  if (fromShare) return mergeModel(fromShare);
  try {
    localStorage.removeItem(MODEL_KEY);
    localStorage.removeItem(LEGACY_MODEL_KEY);
  } catch {
    // Storage can be unavailable in strict privacy modes; blank defaults still work.
  }
  return freshDefaultState();
}

export function loadConnection(): ApiConnection {
  const fallback = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  try {
    const saved = JSON.parse(localStorage.getItem(CONNECTION_KEY) || "{}") as Partial<ApiConnection>;
    return {
      baseUrl: (saved.baseUrl || fallback).replace(/\/$/, ""),
      accessKey: saved.accessKey || "",
    };
  } catch {
    return { baseUrl: fallback, accessKey: "" };
  }
}

export function saveConnection(connection: ApiConnection): void {
  localStorage.setItem(
    CONNECTION_KEY,
    JSON.stringify({ ...connection, baseUrl: connection.baseUrl.replace(/\/$/, "") }),
  );
}

export function loadTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function saveTheme(theme: Theme): void {
  localStorage.setItem(THEME_KEY, theme);
}

export function loadLocale(): Locale {
  return localStorage.getItem(LOCALE_KEY) === "en" ? "en" : "zh-TW";
}

export function saveLocale(locale: Locale): void {
  localStorage.setItem(LOCALE_KEY, locale);
}

export function createShareUrl(model: BacktestFormState): string {
  const bytes = new TextEncoder().encode(JSON.stringify(model));
  let binary = "";
  bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
  const encoded = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const url = new URL(window.location.href);
  url.hash = `model=${encoded}`;
  return url.toString();
}

function readSharedModel(): Partial<BacktestFormState> | null {
  if (!window.location.hash.startsWith("#model=")) return null;
  try {
    const encoded = window.location.hash.slice(7).replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(encoded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)) as Partial<BacktestFormState>;
  } catch {
    return null;
  }
}

function mergeModel(saved: Partial<BacktestFormState>): BacktestFormState {
  const requestedCount = Number(saved.portfolioCount);
  const portfolioCount = Number.isFinite(requestedCount)
    ? Math.min(MAX_PORTFOLIOS, Math.max(1, Math.trunc(requestedCount)))
    : preferredPortfolioCount();
  const defaults = freshDefaultState(portfolioCount);
  return {
    ...defaults,
    ...saved,
    portfolioCount,
    baseCurrency: "TWD",
    outputFrequency: "daily",
    assets: saved.assets?.length
      ? saved.assets.slice(0, 20).map((asset) => ({
          id: asset.id || crypto.randomUUID(),
          symbol: asset.symbol || "",
          weights: Array.from(
            { length: MAX_PORTFOLIOS },
            (_, index) => normalizeWeight(asset.weights?.[index]),
          ),
        }))
      : defaults.assets,
    portfolioNames: Array.from(
      { length: MAX_PORTFOLIOS },
      (_, index) => saved.portfolioNames?.[index] ?? "",
    ),
  };
}

function normalizeWeight(value: unknown): WeightValue {
  if (value === "" || value === null || value === undefined) return "";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : "";
}
