import type { AssetRow, BacktestFormState, WeightValue } from "./types";

const currentYear = new Date().getFullYear();
export const MAX_PORTFOLIOS = 5;
export const DEFAULT_ASSET_ROWS = 6;
export const MOBILE_BREAKPOINT = "(max-width: 760px)";

export function blankWeights(): WeightValue[] {
  return Array.from({ length: MAX_PORTFOLIOS }, () => "");
}

export function blankAsset(): AssetRow {
  return { id: crypto.randomUUID(), symbol: "", weights: blankWeights() };
}

export function preferredPortfolioCount(): number {
  if (typeof window === "undefined") return MAX_PORTFOLIOS;
  return window.matchMedia?.(MOBILE_BREAKPOINT).matches ? 2 : MAX_PORTFOLIOS;
}

export function freshDefaultState(portfolioCount = preferredPortfolioCount()): BacktestFormState {
  return {
    portfolioCount,
    portfolioNames: Array.from({ length: MAX_PORTFOLIOS }, () => ""),
    benchmark: "",
    startDate: `${currentYear - 10}-01-01`,
    endDate: new Date().toISOString().slice(0, 10),
    includeYtd: true,
    initialAmount: 1_000_000,
    baseCurrency: "TWD",
    cashflowType: "none",
    cashflowAmount: 0,
    cashflowFrequency: "none",
    cashflowTiming: "end",
    cashflowGrowthRate: 0,
    rebalanceFrequency: "annual",
    rebalanceThreshold: null,
    leverageType: "none",
    leverageRatio: 1.5,
    debtAmount: 0,
    interestRate: 0,
    maintenanceMargin: 25,
    reinvestDividends: true,
    displayIncome: true,
    transactionCostBps: 0,
    styleAnalysis: false,
    factorRegression: false,
    regime: "none",
    riskFreeRate: 0,
    inflationAdjusted: false,
    outputFrequency: "daily",
    assets: Array.from({ length: DEFAULT_ASSET_ROWS }, blankAsset),
  };
}
