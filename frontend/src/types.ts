export type Locale = "zh-TW" | "en";
export type Theme = "light" | "dark";
export type RebalanceFrequency = "none" | "monthly" | "quarterly" | "semiannual" | "annual";
export type CashflowFrequency = "none" | "monthly" | "quarterly" | "annual";
export type CashflowType = "none" | "fixed" | "percent";
export type LeverageType = "none" | "fixed_ratio" | "fixed_debt";
export type RegimeType = "none" | "market" | "volatility" | "inflation" | "business_cycle";
export type OutputFrequency = "daily" | "weekly" | "monthly";

export interface AssetRow {
  id: string;
  symbol: string;
  weights: number[];
}

export interface BacktestFormState {
  portfolioCount: number;
  portfolioNames: string[];
  benchmark: string;
  startDate: string;
  endDate: string;
  includeYtd: boolean;
  initialAmount: number;
  baseCurrency: "TWD";
  cashflowType: CashflowType;
  cashflowAmount: number;
  cashflowFrequency: CashflowFrequency;
  cashflowTiming: "beginning" | "end";
  cashflowGrowthRate: number;
  rebalanceFrequency: RebalanceFrequency;
  rebalanceThreshold: number | null;
  leverageType: LeverageType;
  leverageRatio: number;
  debtAmount: number;
  interestRate: number;
  maintenanceMargin: number;
  reinvestDividends: boolean;
  displayIncome: boolean;
  transactionCostBps: number;
  styleAnalysis: boolean;
  factorRegression: boolean;
  regime: RegimeType;
  riskFreeRate: number;
  inflationAdjusted: boolean;
  outputFrequency: OutputFrequency;
  assets: AssetRow[];
}

export interface ApiConnection {
  baseUrl: string;
  accessKey: string;
}

export interface AssetAllocationRequest {
  symbol: string;
  weight: number;
}

export interface PortfolioRequest {
  name: string;
  assets: AssetAllocationRequest[];
}

export interface BacktestRequest {
  portfolios: PortfolioRequest[];
  benchmark: string | null;
  start_date: string;
  end_date: string;
  initial_amount: number;
  base_currency: "TWD";
  include_ytd: boolean;
  reinvest_dividends: boolean;
  display_income: boolean;
  transaction_cost_bps: number;
  cashflow: {
    type: CashflowType;
    amount: number;
    frequency: CashflowFrequency;
    timing: "beginning" | "end";
    annual_growth_rate: number;
  };
  rebalancing: {
    frequency: RebalanceFrequency;
    threshold_percent: number | null;
  };
  leverage: {
    type: LeverageType;
    ratio: number;
    debt_amount: number;
    annual_interest_rate: number;
    maintenance_margin: number;
  };
  analytics: {
    style_analysis: boolean;
    factor_regression: boolean;
    regime: RegimeType;
    risk_free_rate: number;
    inflation_adjusted: boolean;
  };
  output_frequency: OutputFrequency;
}

export interface PerformancePoint {
  date: string;
  value: number;
  return_index: number;
  drawdown: number;
  cumulative_income: number;
}

export interface FactorAnalysis {
  model: string;
  observations: number;
  start: string;
  end: string;
  annualized_alpha: number;
  r_squared: number;
  betas: Record<string, number>;
}

export interface StyleAnalysis {
  model: string;
  observations: number;
  start: string;
  end: string;
  r_squared: number;
  exposures: Record<string, number>;
  note: string;
}

export interface RegimeAnalysis {
  type: string;
  regimes: Array<{
    name: string;
    months: number;
    annualized_return: number;
    annualized_volatility: number;
    best_month: number;
    worst_month: number;
  }>;
}

export interface PortfolioResult {
  name: string;
  metrics: Record<string, number | string | null>;
  series: PerformancePoint[];
  annual_returns: Record<string, number>;
  monthly_returns: Array<{ year: number; month: number; return: number }>;
  income_by_year: Record<string, number>;
  final_allocation: Record<string, number>;
  factor_analysis: FactorAnalysis | null;
  style_analysis: StyleAnalysis | null;
  regime_analysis: RegimeAnalysis | null;
}

export interface BacktestResponse {
  request_id: string;
  generated_at: string;
  data_as_of: string;
  effective_start: string;
  effective_end: string;
  base_currency: "TWD";
  results: PortfolioResult[];
  benchmark: PortfolioResult | null;
  assets: Array<{
    symbol: string;
    name: string;
    currency: string;
    first_date: string;
    last_date: string;
    observations: number;
    dividend_events: number;
    capital_gain_events: number;
    split_events: number;
    repaired_observations: number;
    split_corrections: number;
  }>;
  warnings: string[];
}

export interface AssetSearchResult {
  symbol: string;
  name: string;
  exchange: string | null;
  quote_type: string | null;
  currency: string | null;
}
