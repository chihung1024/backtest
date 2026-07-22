import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  Download,
  Grid3X3,
  LineChart as LineIcon,
  PieChart as PieIcon,
  ShieldAlert,
  Sparkles,
  Table2,
  WalletCards,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Translator } from "../i18n";
import type { BacktestResponse, PortfolioResult } from "../types";
import {
  chartColors,
  downloadJson,
  downloadResultsCsv,
  formatMoney,
  formatNumber,
  formatPercent,
} from "../utils";
import { resolveGrowthScale, type GrowthScaleMode } from "../chartScale";
import { resolveDateAxis } from "../dateAxis";

type ResultTab = "overview" | "growth" | "drawdown" | "annual" | "monthly" | "income" | "allocation" | "analytics";

export function ResultsDashboard({
  response,
  t,
  locale,
}: {
  response: BacktestResponse;
  t: Translator;
  locale: string;
}) {
  const [activeTab, setActiveTab] = useState<ResultTab>("overview");
  const [selectedPortfolio, setSelectedPortfolio] = useState(0);
  const [growthScaleMode, setGrowthScaleMode] = useState<GrowthScaleMode>("log");
  const allResults = useMemo(
    () => response.benchmark ? [...response.results, response.benchmark] : response.results,
    [response.benchmark, response.results],
  );
  const chartSeries = useMemo(() => mergePerformanceSeries(allResults), [allResults]);
  const annualData = useMemo(() => mergeAnnualReturns(allResults), [allResults]);
  const incomeData = useMemo(() => mergeIncome(allResults), [allResults]);
  const hasAnalytics = response.results.some(
    (result) => result.factor_analysis || result.style_analysis || result.regime_analysis,
  );

  const tabs: Array<{ id: ResultTab; label: string; icon: typeof Table2; hidden?: boolean }> = [
    { id: "overview", label: t("overview"), icon: Table2 },
    { id: "growth", label: t("growth"), icon: LineIcon },
    { id: "drawdown", label: t("drawdown"), icon: ShieldAlert },
    { id: "annual", label: t("annualReturns"), icon: BarChart3 },
    { id: "monthly", label: t("monthlyReturns"), icon: Grid3X3 },
    { id: "income", label: t("income"), icon: WalletCards, hidden: incomeData.length === 0 },
    { id: "allocation", label: t("allocation"), icon: PieIcon },
    { id: "analytics", label: t("analytics"), icon: Sparkles, hidden: !hasAnalytics },
  ];

  return (
    <section className="results-shell" aria-labelledby="results-title">
      <div className="results-header">
        <div>
          <span className="eyebrow">Portfolio performance</span>
          <h2 id="results-title">{t("results")}</h2>
          <p className="results-meta">
            <span>{t("period")}：{response.effective_start} → {response.effective_end}</span>
            <span>{t("dataAsOf")}：{response.data_as_of}</span>
            <span>{t("valuationBasis")}：{response.base_currency}</span>
          </p>
        </div>
        <div className="results-actions">
          <button type="button" className="button button--subtle" onClick={() => downloadResultsCsv(allResults)}>
            <Download size={16} />{t("exportCsv")}
          </button>
          <button type="button" className="button button--subtle" onClick={() => downloadJson("portfolio-backtest.json", response)}>
            <Download size={16} />{t("exportJson")}
          </button>
        </div>
      </div>

      {response.warnings.length > 0 && (
        <details className="warning-panel">
          <summary><AlertTriangle size={17} />{t("warnings")}<span>{response.warnings.length}</span></summary>
          <ul>{response.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </details>
      )}

      <div className="result-tabs" role="tablist">
        {tabs.filter((tab) => !tab.hidden).map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={activeTab === tab.id ? "active" : ""}
              onClick={() => setActiveTab(tab.id)}
              key={tab.id}
            >
              <Icon size={16} />{tab.label}
            </button>
          );
        })}
      </div>

      <div className="result-content" role="tabpanel">
        {activeTab === "overview" && (
          <Overview results={allResults} currency={response.base_currency} locale={locale} t={t} />
        )}
        {activeTab === "growth" && (
          <GrowthChart
            data={chartSeries}
            results={allResults}
            currency={response.base_currency}
            locale={locale}
            t={t}
            scaleMode={growthScaleMode}
            onScaleMode={setGrowthScaleMode}
          />
        )}
        {activeTab === "drawdown" && (
          <DrawdownChart data={chartSeries} results={allResults} locale={locale} />
        )}
        {activeTab === "annual" && <AnnualChart data={annualData} results={allResults} />}
        {activeTab === "monthly" && (
          <MonthlyHeatmap
            result={allResults[selectedPortfolio]}
            results={allResults}
            selected={selectedPortfolio}
            onSelect={setSelectedPortfolio}
            t={t}
          />
        )}
        {activeTab === "income" && (
          <IncomeChart data={incomeData} results={allResults} currency={response.base_currency} locale={locale} />
        )}
        {activeTab === "allocation" && (
          <AllocationCharts results={response.results} t={t} />
        )}
        {activeTab === "analytics" && <AnalyticsPanels results={response.results} t={t} />}
      </div>
    </section>
  );
}

function Overview({
  results,
  currency,
  locale,
  t,
}: {
  results: PortfolioResult[];
  currency: string;
  locale: string;
  t: Translator;
}) {
  const primaryMetrics = [
    ["cagr", t("cagr"), "percent"],
    ["volatility", t("volatilityMetric"), "percent"],
    ["max_drawdown", t("maxDrawdown"), "percent"],
    ["sharpe_ratio", t("sharpe"), "number"],
  ] as const;
  const metricRows = [
    ["initial_balance", t("initialAmount"), "money"],
    ["final_balance", t("finalBalance"), "money"],
    ["net_profit", t("netProfit"), "money"],
    ["contributions", t("contributions"), "money"],
    ["transaction_costs", t("transactionCosts"), "money"],
    ["borrowing_costs", t("borrowingCosts"), "money"],
    ["rebalance_count", t("rebalanceCount"), "number"],
    ["total_return", t("totalReturn"), "percent"],
    ["cagr", t("cagr"), "percent"],
    ["real_total_return", t("realTotalReturn"), "percent"],
    ["real_cagr", t("realCagr"), "percent"],
    ["cumulative_inflation", t("cumulativeInflation"), "percent"],
    ["money_weighted_return", t("moneyWeighted"), "percent"],
    ["volatility", t("volatilityMetric"), "percent"],
    ["max_drawdown", t("maxDrawdown"), "percent"],
    ["sharpe_ratio", t("sharpe"), "number"],
    ["sortino_ratio", t("sortino"), "number"],
    ["calmar_ratio", t("calmar"), "number"],
    ["best_year", t("bestYear"), "percent"],
    ["worst_year", t("worstYear"), "percent"],
    ["beta", t("beta"), "number"],
    ["alpha", t("alpha"), "percent"],
    ["benchmark_correlation", t("correlation"), "number"],
  ] as const;

  return (
    <div className="overview">
      <div className="summary-grid">
        {results.map((result, index) => (
          <article className="portfolio-summary" key={result.name} style={{ "--series-color": chartColors[index] } as React.CSSProperties}>
            <div className="portfolio-summary__head">
              <span className="series-swatch" />
              <h3 title={result.display_name}>{result.display_name}</h3>
            </div>
            <div className="portfolio-summary__balance">
              <span>{t("finalBalance")}</span>
              <strong>{formatMoney(Number(result.metrics.final_balance), currency, locale)}</strong>
            </div>
            <div className="portfolio-summary__metrics">
              {primaryMetrics.map(([key, label, format]) => (
                <div key={key}>
                  <span>{label}</span>
                  <strong>{formatMetric(result.metrics[key], format, currency, locale)}</strong>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="table-scroll">
        <table className="metrics-table">
          <thead>
            <tr><th>{t("metric")}</th>{results.map((result) => <th key={result.name}>{result.display_name}</th>)}</tr>
          </thead>
          <tbody>
            {metricRows
              .filter(([key]) => results.some((result) => result.metrics[key] !== undefined))
              .map(([key, label, format]) => (
                <tr key={key}>
                  <th>{label}</th>
                  {results.map((result) => (
                    <td key={result.name}>{formatMetric(result.metrics[key], format, currency, locale)}</td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GrowthChart({
  data,
  results,
  currency,
  locale,
  t,
  scaleMode,
  onScaleMode,
}: ChartProps & {
  currency: string;
  locale: string;
  t: Translator;
  scaleMode: GrowthScaleMode;
  onScaleMode: (mode: GrowthScaleMode) => void;
}) {
  const values = useMemo(
    () => results.flatMap((result) => result.series.map((point) => point.value)),
    [results],
  );
  const scale = useMemo(() => resolveGrowthScale(values, scaleMode), [scaleMode, values]);
  const dateAxis = useMemo(
    () => resolveDateAxis(data.map((row) => String(row.date)), locale),
    [data, locale],
  );
  const selectedScaleMode = scaleMode === "log" && !scale.logAvailable ? "linear" : scaleMode;
  const scaleHint = !scale.logAvailable
    ? t("scaleLogUnavailable")
    : scaleMode === "auto"
      ? scale.effectiveMode === "log" ? t("scaleAutoLogHint") : t("scaleAutoLinearHint")
      : scale.effectiveMode === "log" ? t("scaleLogHint") : t("scaleLinearHint");

  return (
    <div className="growth-chart-wrap">
      <div className="chart-scale-toolbar">
        <div className="chart-scale-toolbar__copy">
          <strong>{t("yAxisScale")}</strong>
          <span role="status">{scaleHint}</span>
        </div>
        <div className="scale-toggle" role="group" aria-label={t("yAxisScale")}>
          {(["auto", "linear", "log"] as const).map((mode) => (
            <button
              type="button"
              className={selectedScaleMode === mode ? "active" : ""}
              aria-pressed={selectedScaleMode === mode}
              disabled={mode === "log" && !scale.logAvailable}
              onClick={() => onScaleMode(mode)}
              key={mode}
            >
              {t(mode === "auto" ? "scaleAuto" : mode === "linear" ? "scaleLinear" : "scaleLog")}
            </button>
          ))}
        </div>
      </div>
      <ChartFrame results={results}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            key={scale.effectiveMode}
            data={data}
            margin={{ top: 16, right: 18, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 5" vertical={false} />
            <XAxis
              dataKey="date"
              ticks={dateAxis.ticks}
              tickFormatter={dateAxis.formatTick}
              interval="preserveStartEnd"
              minTickGap={28}
              tickMargin={8}
              height={38}
            />
            <YAxis
              type="number"
              width={96}
              scale={scale.effectiveMode === "log" ? "log" : "auto"}
              domain={scale.logDomain ?? [0, "auto"]}
              ticks={scale.effectiveMode === "log" ? scale.logTicks : undefined}
              allowDataOverflow={scale.effectiveMode === "log"}
              interval="preserveStartEnd"
              tickFormatter={(value) => compactMoney(Number(value), currency, locale)}
            />
            <Tooltip
              formatter={(value) => formatMoney(Number(value), currency, locale)}
              labelFormatter={(label) => dateLabel(String(label), locale)}
            />
            {results.map((result, index) => (
              <Line key={result.name} dataKey={`s${index}_value`} name={result.display_name} stroke={chartColors[index]} strokeWidth={2.4} dot={false} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  );
}

function DrawdownChart({ data, results, locale }: ChartProps & { locale: string }) {
  const dateAxis = useMemo(
    () => resolveDateAxis(data.map((row) => String(row.date)), locale),
    [data, locale],
  );
  return (
    <ChartFrame results={results}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 16, right: 18, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="date"
            ticks={dateAxis.ticks}
            tickFormatter={dateAxis.formatTick}
            interval="preserveStartEnd"
            minTickGap={28}
            tickMargin={8}
            height={38}
          />
          <YAxis width={64} tickFormatter={(value) => formatPercent(Number(value), 0)} />
          <Tooltip
            formatter={(value) => formatPercent(Number(value))}
            labelFormatter={(label) => dateLabel(String(label), locale)}
          />
          {results.map((result, index) => (
            <Area key={result.name} type="linear" dataKey={`s${index}_drawdown`} name={result.display_name} stroke={chartColors[index]} fill={chartColors[index]} fillOpacity={0.08} dot={false} connectNulls />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function AnnualChart({ data, results }: ChartProps) {
  return (
    <ChartFrame results={results}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 16, right: 18, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="year" />
          <YAxis width={64} tickFormatter={(value) => formatPercent(Number(value), 0)} />
          <Tooltip formatter={(value) => formatPercent(Number(value))} />
          {results.map((result, index) => (
            <Bar key={result.name} dataKey={`s${index}`} name={result.display_name} fill={chartColors[index]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function IncomeChart({ data, results, currency, locale }: ChartProps & { currency: string; locale: string }) {
  return (
    <ChartFrame results={results}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 16, right: 18, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="year" />
          <YAxis width={84} tickFormatter={(value) => compactMoney(Number(value), currency, locale)} />
          <Tooltip formatter={(value) => formatMoney(Number(value), currency, locale)} />
          {results.map((result, index) => (
            <Bar key={result.name} dataKey={`s${index}`} name={result.display_name} fill={chartColors[index]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function MonthlyHeatmap({
  result,
  results,
  selected,
  onSelect,
  t,
}: {
  result: PortfolioResult;
  results: PortfolioResult[];
  selected: number;
  onSelect: (index: number) => void;
  t: Translator;
}) {
  const years = Array.from(new Set(result.monthly_returns.map((row) => row.year))).sort((a, b) => a - b);
  const lookup = new Map(result.monthly_returns.map((row) => [`${row.year}-${row.month}`, row.return]));
  return (
    <div className="heatmap-wrap">
      <div className="subtoolbar">
        <label>{t("portfolio")}
          <select value={selected} onChange={(event) => onSelect(Number(event.target.value))}>
            {results.map((item, index) => <option value={index} key={item.name}>{item.display_name}</option>)}
          </select>
        </label>
      </div>
      <div className="table-scroll">
        <table className="heatmap">
          <thead><tr><th><CalendarDays size={15} /></th>{Array.from({ length: 12 }, (_, index) => <th key={index}>{index + 1}</th>)}<th>YTD</th></tr></thead>
          <tbody>
            {years.map((year) => {
              const values = Array.from({ length: 12 }, (_, month) => lookup.get(`${year}-${month + 1}`));
              const valid = values.filter((value): value is number => value !== undefined);
              const ytd = valid.reduce((level, value) => level * (1 + value), 1) - 1;
              return (
                <tr key={year}>
                  <th>{year}</th>
                  {values.map((value, month) => <HeatCell value={value} key={month} />)}
                  <HeatCell value={ytd} strong />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HeatCell({ value, strong = false }: { value?: number; strong?: boolean }) {
  if (value === undefined) return <td className="heatmap__empty">—</td>;
  const intensity = Math.min(Math.abs(value) / 0.12, 1);
  const color = value >= 0 ? `rgba(25,168,138,${0.12 + intensity * 0.68})` : `rgba(225,75,75,${0.12 + intensity * 0.68})`;
  return <td className={strong ? "heatmap__strong" : ""} style={{ backgroundColor: color }}>{formatPercent(value, 1)}</td>;
}

function AllocationCharts({ results, t }: { results: PortfolioResult[]; t: Translator }) {
  return (
    <div className="allocation-grid">
      {results.map((result, resultIndex) => {
        const data = Object.entries(result.final_allocation).map(([name, value]) => ({ name, value }));
        return (
          <article className="allocation-card" key={result.name}>
            <h3 title={result.display_name}>{result.display_name}</h3>
            <div className="allocation-card__chart">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={2}>
                    {data.map((entry, index) => <Cell key={entry.name} fill={chartColors[(index + resultIndex) % chartColors.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value) => formatPercent(Number(value))} />
                </PieChart>
              </ResponsiveContainer>
              <span className="allocation-card__center">{t("allocation")}</span>
            </div>
            <div className="allocation-legend">
              {data.map((entry, index) => (
                <div key={entry.name}>
                  <span className="allocation-legend__swatch" style={{ background: chartColors[(index + resultIndex) % chartColors.length] }} />
                  <span className="allocation-legend__name">{entry.name}</span>
                  <strong>{formatPercent(entry.value)}</strong>
                </div>
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function AnalyticsPanels({ results, t }: { results: PortfolioResult[]; t: Translator }) {
  return (
    <div className="analytics-stack">
      {results.map((result) => (
        <article className="analytics-card" key={result.name}>
          <h3 title={result.display_name}>{result.display_name}</h3>
          {result.factor_analysis && (
            <div className="analytics-block">
              <h4>{t("factorRegression")}</h4>
              <div className="analytics-kpis">
                <Kpi label={t("factorModel")} value={result.factor_analysis.model} />
                <Kpi label={t("observations")} value={String(result.factor_analysis.observations)} />
                <Kpi label={t("annualizedAlpha")} value={formatPercent(result.factor_analysis.annualized_alpha)} />
                <Kpi label={t("rSquared")} value={formatPercent(result.factor_analysis.r_squared)} />
              </div>
              <div className="exposure-bars">
                {Object.entries(result.factor_analysis.betas).map(([name, value]) => <ExposureBar key={name} name={name} value={value} />)}
              </div>
            </div>
          )}
          {result.style_analysis && (
            <div className="analytics-block">
              <h4>{t("styleAnalysis")}</h4>
              <div className="analytics-kpis">
                <Kpi label={t("observations")} value={String(result.style_analysis.observations)} />
                <Kpi label={t("rSquared")} value={formatPercent(result.style_analysis.r_squared)} />
              </div>
              <div className="exposure-bars">
                {Object.entries(result.style_analysis.exposures).map(([name, value]) => <ExposureBar key={name} name={name.replace(/_/g, " ")} value={value} percent />)}
              </div>
              <p className="analytics-note">{result.style_analysis.note}</p>
            </div>
          )}
          {result.regime_analysis && (
            <div className="analytics-block">
              <h4>{t("regimePerformance")}</h4>
              <div className="table-scroll">
                <table className="metrics-table">
                  <thead><tr><th>{t("regime")}</th><th>{t("months")}</th><th>{t("annualizedReturn")}</th><th>{t("annualizedVolatility")}</th></tr></thead>
                  <tbody>{result.regime_analysis.regimes.map((regime) => (
                    <tr key={regime.name}><th>{regime.name}</th><td>{regime.months}</td><td>{formatPercent(regime.annualized_return)}</td><td>{formatPercent(regime.annualized_volatility)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function ExposureBar({ name, value, percent = false }: { name: string; value: number; percent?: boolean }) {
  const width = `${Math.min(Math.abs(value) * (percent ? 100 : 50), 100)}%`;
  return (
    <div className="exposure-row">
      <span>{name}</span>
      <div><i style={{ width }} className={value < 0 ? "negative" : ""} /></div>
      <strong>{percent ? formatPercent(value) : formatNumber(value)}</strong>
    </div>
  );
}

function ChartFrame({ children, results }: { children: React.ReactNode; results: PortfolioResult[] }) {
  return (
    <div className="chart-block">
      <div className="chart-frame">{children}</div>
      <ul className="chart-legend">
        {results.map((result, index) => (
          <li key={result.name} title={result.display_name}>
            <span className="chart-legend__swatch" style={{ "--series-color": chartColors[index] } as React.CSSProperties} />
            <span className="chart-legend__label">{result.display_name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ChartProps {
  data: Array<Record<string, string | number | null>>;
  results: PortfolioResult[];
}

function mergePerformanceSeries(results: PortfolioResult[]): Array<Record<string, string | number | null>> {
  const rows = new Map<string, Record<string, string | number | null>>();
  results.forEach((result, index) => {
    result.series.forEach((point) => {
      const row = rows.get(point.date) || { date: point.date };
      row[`s${index}_value`] = point.value;
      row[`s${index}_drawdown`] = point.drawdown;
      rows.set(point.date, row);
    });
  });
  return Array.from(rows.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function mergeAnnualReturns(results: PortfolioResult[]): Array<Record<string, string | number | null>> {
  const years = new Set(results.flatMap((result) => Object.keys(result.annual_returns)));
  return Array.from(years).sort().map((year) => {
    const row: Record<string, string | number | null> = { year };
    results.forEach((result, index) => { row[`s${index}`] = result.annual_returns[year] ?? null; });
    return row;
  });
}

function mergeIncome(results: PortfolioResult[]): Array<Record<string, string | number | null>> {
  const years = new Set(results.flatMap((result) => Object.keys(result.income_by_year)));
  return Array.from(years).sort().map((year) => {
    const row: Record<string, string | number | null> = { year };
    results.forEach((result, index) => { row[`s${index}`] = result.income_by_year[year] ?? null; });
    return row;
  });
}

function formatMetric(
  value: number | string | null | undefined,
  format: "money" | "percent" | "number",
  currency: string,
  locale: string,
): string {
  if (value === null || value === undefined) return "—";
  if (format === "money") return formatMoney(Number(value), currency, locale);
  if (format === "percent") return formatPercent(value);
  return formatNumber(value);
}

function compactMoney(value: number, currency: string, locale: string): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function dateLabel(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}
