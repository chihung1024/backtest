import type { BacktestFormState, BacktestRequest, PortfolioResult } from "./types";

export const chartColors = ["#19a88a", "#4169e1", "#f59e0b", "#9b5de5"];

export function buildRequest(model: BacktestFormState): BacktestRequest {
  const portfolios = Array.from({ length: model.portfolioCount }, (_, portfolioIndex) => ({
    name: model.portfolioNames[portfolioIndex] || `Portfolio ${portfolioIndex + 1}`,
    assets: model.assets
      .filter((asset) => asset.symbol.trim() && Number(asset.weights[portfolioIndex]) > 0)
      .map((asset) => ({
        symbol: asset.symbol.trim().toUpperCase(),
        weight: Number(asset.weights[portfolioIndex]),
      })),
  }));
  return {
    portfolios,
    benchmark: model.benchmark.trim().toUpperCase() || null,
    start_date: model.startDate,
    end_date: model.endDate,
    initial_amount: Number(model.initialAmount),
    base_currency: model.baseCurrency,
    include_ytd: model.includeYtd,
    reinvest_dividends: model.reinvestDividends,
    display_income: model.displayIncome,
    transaction_cost_bps: Number(model.transactionCostBps),
    cashflow: {
      type: model.cashflowType,
      amount: Number(model.cashflowAmount),
      frequency: model.cashflowType === "none" ? "none" : model.cashflowFrequency,
      timing: model.cashflowTiming,
      annual_growth_rate: Number(model.cashflowGrowthRate),
    },
    rebalancing: {
      frequency: model.rebalanceFrequency,
      threshold_percent: model.rebalanceThreshold,
    },
    leverage: {
      type: model.leverageType,
      ratio: Number(model.leverageRatio),
      debt_amount: Number(model.debtAmount),
      annual_interest_rate: Number(model.interestRate),
      maintenance_margin: Number(model.maintenanceMargin),
    },
    analytics: {
      style_analysis: model.styleAnalysis,
      factor_regression: model.factorRegression,
      regime: model.regime,
      risk_free_rate: Number(model.riskFreeRate),
      inflation_adjusted: model.inflationAdjusted,
    },
    output_frequency: model.outputFrequency,
  };
}

export function validateModel(model: BacktestFormState): string[] {
  const errors: string[] = [];
  if (!model.startDate || !model.endDate || model.startDate >= model.endDate) {
    errors.push("開始日期必須早於結束日期");
  }
  if (model.initialAmount <= 0) errors.push("初始金額必須大於零");
  for (let index = 0; index < model.portfolioCount; index += 1) {
    const active = model.assets.filter((asset) => asset.symbol && asset.weights[index] > 0);
    const total = active.reduce((sum, asset) => sum + Number(asset.weights[index]), 0);
    if (!active.length) errors.push(`投資組合 ${index + 1} 至少需要一項資產`);
    if (Math.abs(total - 100) > 0.05) {
      errors.push(`投資組合 ${index + 1} 權重目前為 ${total.toFixed(2)}%，必須等於 100%`);
    }
    const symbols = active.map((asset) => asset.symbol.trim().toUpperCase());
    if (new Set(symbols).size !== symbols.length) {
      errors.push(`投資組合 ${index + 1} 有重複代碼`);
    }
  }
  if (model.cashflowType !== "none" && model.cashflowFrequency === "none") {
    errors.push("啟用現金流時必須選擇頻率");
  }
  if (model.leverageType === "fixed_ratio" && model.leverageRatio <= 1) {
    errors.push("固定槓桿倍數必須大於 1");
  }
  return errors;
}

export function formatMoney(value: number, currency: string, locale = "zh-TW"): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 2,
  }).format(value);
}

export function formatPercent(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

export function downloadJson(filename: string, data: unknown): void {
  downloadBlob(filename, JSON.stringify(data, null, 2), "application/json");
}

export function downloadResultsCsv(results: PortfolioResult[]): void {
  const rows = ["date,portfolio,value,return_index,drawdown,cumulative_income"];
  results.forEach((result) => {
    result.series.forEach((point) => {
      rows.push(
        [point.date, quote(result.name), point.value, point.return_index, point.drawdown, point.cumulative_income].join(","),
      );
    });
  });
  downloadBlob("portfolio-backtest.csv", rows.join("\n"), "text/csv;charset=utf-8");
}

function quote(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function downloadBlob(filename: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
