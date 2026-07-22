import type { BacktestFormState } from "./types";

const currentYear = new Date().getFullYear();

export const defaultFormState: BacktestFormState = {
  portfolioCount: 1,
  portfolioNames: ["全球核心", "成長配置", "防禦配置"],
  benchmark: "VT",
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
  outputFrequency: "monthly",
  assets: [
    { id: crypto.randomUUID(), symbol: "VT", weights: [80, 0, 0] },
    { id: crypto.randomUUID(), symbol: "BND", weights: [20, 0, 0] },
    ...Array.from({ length: 4 }, () => ({
      id: crypto.randomUUID(),
      symbol: "",
      weights: [0, 0, 0],
    })),
  ],
};

export function freshDefaultState(): BacktestFormState {
  return structuredClone(defaultFormState);
}
