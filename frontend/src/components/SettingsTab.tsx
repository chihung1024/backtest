import type { Dispatch, SetStateAction } from "react";
import type { Translator } from "../i18n";
import type { BacktestFormState } from "../types";
import { Field, SectionHeading, Toggle } from "./FormControls";

export function SettingsTab({
  model,
  setModel,
  t,
}: {
  model: BacktestFormState;
  setModel: Dispatch<SetStateAction<BacktestFormState>>;
  t: Translator;
}) {
  const patch = (values: Partial<BacktestFormState>) =>
    setModel((current) => ({ ...current, ...values }));

  return (
    <div className="settings-layout">
      <section className="settings-section">
        <SectionHeading title={t("timePeriod")} />
        <div className="form-grid">
          <Field label={t("startDate")}>
            <input
              type="date"
              value={model.startDate}
              onChange={(event) => patch({ startDate: event.target.value })}
            />
          </Field>
          <Field label={t("endDate")}>
            <input
              type="date"
              value={model.endDate}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(event) => patch({ endDate: event.target.value })}
            />
          </Field>
          <Field label={t("initialAmount")}>
            <input
              type="number"
              min="1"
              step="1000"
              value={model.initialAmount}
              onChange={(event) => patch({ initialAmount: Number(event.target.value) })}
            />
          </Field>
          <Field label={t("baseCurrency")}>
            <select
              value={model.baseCurrency}
              onChange={(event) => patch({ baseCurrency: event.target.value })}
            >
              <option value="TWD">TWD · 新台幣</option>
              <option value="USD">USD · US Dollar</option>
              <option value="JPY">JPY · 日本円</option>
              <option value="EUR">EUR · Euro</option>
              <option value="HKD">HKD · 港幣</option>
            </select>
          </Field>
          <Field label={t("outputFrequency")}>
            <select
              value={model.outputFrequency}
              onChange={(event) => patch({ outputFrequency: event.target.value as BacktestFormState["outputFrequency"] })}
            >
              <option value="monthly">{t("monthly")}</option>
              <option value="weekly">{t("weekly")}</option>
              <option value="daily">{t("daily")}</option>
            </select>
          </Field>
          <div className="field field--toggle">
            <span className="field__label">{t("includeYtd")}</span>
            <Toggle checked={model.includeYtd} onChange={(includeYtd) => patch({ includeYtd })} label={model.includeYtd ? "Yes" : "No"} />
          </div>
        </div>
      </section>

      <section className="settings-section">
        <SectionHeading title={t("cashflows")} />
        <div className="form-grid">
          <Field label={t("cashflowType")}>
            <select
              value={model.cashflowType}
              onChange={(event) => {
                const type = event.target.value as BacktestFormState["cashflowType"];
                patch({ cashflowType: type, cashflowFrequency: type === "none" ? "none" : model.cashflowFrequency === "none" ? "monthly" : model.cashflowFrequency });
              }}
            >
              <option value="none">{t("none")}</option>
              <option value="fixed">{t("fixedAmount")}</option>
              <option value="percent">{t("percentEquity")}</option>
            </select>
          </Field>
          {model.cashflowType !== "none" && (
            <>
              <Field label={t("amount")}>
                <div className="input-suffix">
                  <input
                    type="number"
                    step={model.cashflowType === "percent" ? "0.1" : "100"}
                    value={model.cashflowAmount}
                    onChange={(event) => patch({ cashflowAmount: Number(event.target.value) })}
                  />
                  <span>{model.cashflowType === "percent" ? "%" : model.baseCurrency}</span>
                </div>
              </Field>
              <Field label={t("frequency")}>
                <select
                  value={model.cashflowFrequency}
                  onChange={(event) => patch({ cashflowFrequency: event.target.value as BacktestFormState["cashflowFrequency"] })}
                >
                  <option value="monthly">{t("monthly")}</option>
                  <option value="quarterly">{t("quarterly")}</option>
                  <option value="annual">{t("annually")}</option>
                </select>
              </Field>
              <Field label={t("timing")}>
                <select
                  value={model.cashflowTiming}
                  onChange={(event) => patch({ cashflowTiming: event.target.value as "beginning" | "end" })}
                >
                  <option value="beginning">{t("beginning")}</option>
                  <option value="end">{t("end")}</option>
                </select>
              </Field>
              <Field label={t("annualGrowth")}>
                <div className="input-suffix">
                  <input
                    type="number"
                    step="0.1"
                    value={model.cashflowGrowthRate}
                    onChange={(event) => patch({ cashflowGrowthRate: Number(event.target.value) })}
                  />
                  <span>%</span>
                </div>
              </Field>
            </>
          )}
        </div>
      </section>

      <section className="settings-section">
        <SectionHeading title={t("rebalancing")} />
        <div className="form-grid">
          <Field label={t("frequency")}>
            <select
              value={model.rebalanceFrequency}
              onChange={(event) => patch({ rebalanceFrequency: event.target.value as BacktestFormState["rebalanceFrequency"] })}
            >
              <option value="none">{t("rebalanceNone")}</option>
              <option value="monthly">{t("monthly")}</option>
              <option value="quarterly">{t("quarterly")}</option>
              <option value="semiannual">{t("semiannual")}</option>
              <option value="annual">{t("annually")}</option>
            </select>
          </Field>
          <Field label={t("threshold")} hint={t("thresholdHint")}>
            <div className="input-suffix">
              <input
                type="number"
                min="0.1"
                max="100"
                step="0.1"
                value={model.rebalanceThreshold ?? ""}
                placeholder="—"
                onChange={(event) => patch({ rebalanceThreshold: event.target.value === "" ? null : Number(event.target.value) })}
              />
              <span>%</span>
            </div>
          </Field>
        </div>
      </section>

      <section className="settings-section">
        <SectionHeading title={t("leverage")} />
        <div className="form-grid">
          <Field label={t("leverage")}>
            <select
              value={model.leverageType}
              onChange={(event) => patch({ leverageType: event.target.value as BacktestFormState["leverageType"] })}
            >
              <option value="none">{t("leverageNone")}</option>
              <option value="fixed_ratio">{t("fixedRatio")}</option>
              <option value="fixed_debt">{t("fixedDebt")}</option>
            </select>
          </Field>
          {model.leverageType === "fixed_ratio" && (
            <Field label={t("leverageRatio")}>
              <div className="input-suffix">
                <input
                  type="number"
                  min="1.01"
                  max="5"
                  step="0.1"
                  value={model.leverageRatio}
                  onChange={(event) => patch({ leverageRatio: Number(event.target.value) })}
                />
                <span>×</span>
              </div>
            </Field>
          )}
          {model.leverageType === "fixed_debt" && (
            <Field label={t("debtAmount")}>
              <input
                type="number"
                min="0"
                step="1000"
                value={model.debtAmount}
                onChange={(event) => patch({ debtAmount: Number(event.target.value) })}
              />
            </Field>
          )}
          {model.leverageType !== "none" && (
            <>
              <Field label={t("interestRate")}>
                <div className="input-suffix">
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={model.interestRate}
                    onChange={(event) => patch({ interestRate: Number(event.target.value) })}
                  />
                  <span>%</span>
                </div>
              </Field>
              <Field label={t("maintenanceMargin")}>
                <div className="input-suffix">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={model.maintenanceMargin}
                    onChange={(event) => patch({ maintenanceMargin: Number(event.target.value) })}
                  />
                  <span>%</span>
                </div>
              </Field>
            </>
          )}
        </div>
      </section>

      <section className="settings-section">
        <SectionHeading title={t("dividendsAndCosts")} />
        <div className="toggle-grid">
          <Toggle checked={model.reinvestDividends} onChange={(reinvestDividends) => patch({ reinvestDividends })} label={t("reinvestDividends")} />
          <Toggle checked={model.displayIncome} onChange={(displayIncome) => patch({ displayIncome })} label={t("displayIncome")} />
        </div>
        <div className="form-grid form-grid--spaced">
          <Field label={t("transactionCost")}>
            <div className="input-suffix">
              <input
                type="number"
                min="0"
                step="0.1"
                value={model.transactionCostBps}
                onChange={(event) => patch({ transactionCostBps: Number(event.target.value) })}
              />
              <span>bps</span>
            </div>
          </Field>
        </div>
      </section>

      <section className="settings-section settings-section--wide">
        <SectionHeading title={t("advancedAnalysis")} />
        <div className="toggle-grid toggle-grid--three">
          <Toggle checked={model.styleAnalysis} onChange={(styleAnalysis) => patch({ styleAnalysis })} label={t("styleAnalysis")} />
          <Toggle checked={model.factorRegression} onChange={(factorRegression) => patch({ factorRegression })} label={t("factorRegression")} />
          <Toggle checked={model.inflationAdjusted} onChange={(inflationAdjusted) => patch({ inflationAdjusted })} label={t("inflationAdjusted")} />
        </div>
        <div className="form-grid form-grid--spaced">
          <Field label={t("regimePerformance")}>
            <select
              value={model.regime}
              onChange={(event) => patch({ regime: event.target.value as BacktestFormState["regime"] })}
            >
              <option value="none">{t("none")}</option>
              <option value="market">{t("marketTrend")}</option>
              <option value="volatility">{t("volatility")}</option>
              <option value="inflation">{t("inflation")}</option>
              <option value="business_cycle">{t("businessCycle")}</option>
            </select>
          </Field>
          <Field label={t("riskFreeRate")}>
            <div className="input-suffix">
              <input
                type="number"
                step="0.1"
                value={model.riskFreeRate}
                onChange={(event) => patch({ riskFreeRate: Number(event.target.value) })}
              />
              <span>%</span>
            </div>
          </Field>
        </div>
      </section>
    </div>
  );
}
