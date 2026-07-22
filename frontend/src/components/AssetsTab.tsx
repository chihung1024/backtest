import { Eraser, Minus, Plus, Trash2 } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { blankAsset, blankWeights, MAX_PORTFOLIOS } from "../defaults";
import type { Translator } from "../i18n";
import type { ApiConnection, AssetRow, BacktestFormState, WeightValue } from "../types";
import { TickerInput } from "./TickerInput";

export function AssetsTab({
  model,
  setModel,
  connection,
  t,
}: {
  model: BacktestFormState;
  setModel: Dispatch<SetStateAction<BacktestFormState>>;
  connection: ApiConnection;
  t: Translator;
}) {
  const totals = Array.from({ length: model.portfolioCount }, (_, index) =>
    model.assets.reduce((sum, asset) => sum + Number(asset.weights[index] || 0), 0),
  );

  function updateAsset(id: string, values: Partial<AssetRow>) {
    setModel((current) => ({
      ...current,
      assets: current.assets.map((asset) => (asset.id === id ? { ...asset, ...values } : asset)),
    }));
  }

  function updateWeight(asset: AssetRow, portfolioIndex: number, value: WeightValue) {
    const weights = [...asset.weights];
    weights[portfolioIndex] = value;
    updateAsset(asset.id, { weights });
  }

  function addAsset() {
    if (model.assets.length >= 20) return;
    setModel((current) => ({
      ...current,
      assets: [...current.assets, blankAsset()],
    }));
  }

  function removeAsset(id: string) {
    setModel((current) => ({
      ...current,
      assets: current.assets.length <= 1 ? current.assets : current.assets.filter((asset) => asset.id !== id),
    }));
  }

  function changePortfolioCount(delta: number) {
    setModel((current) => {
      const portfolioCount = Math.min(MAX_PORTFOLIOS, Math.max(1, current.portfolioCount + delta));
      if (portfolioCount >= current.portfolioCount) return { ...current, portfolioCount };

      return {
        ...current,
        portfolioCount,
        portfolioNames: current.portfolioNames.map((name, index) => index >= portfolioCount ? "" : name),
        assets: current.assets.map((asset) => ({
          ...asset,
          weights: asset.weights.map((weight, index) => index >= portfolioCount ? "" : weight),
        })),
      };
    });
  }

  function clearAsset(id: string) {
    updateAsset(id, { symbol: "", weights: blankWeights() });
  }

  function clearPortfolio(portfolioIndex: number) {
    setModel((current) => {
      const names = Array.from(
        { length: MAX_PORTFOLIOS },
        (_, index) => index === portfolioIndex ? "" : (current.portfolioNames[index] ?? ""),
      );
      return {
        ...current,
        portfolioNames: names,
        assets: current.assets.map((asset) => ({
          ...asset,
          weights: Array.from(
            { length: MAX_PORTFOLIOS },
            (_, index) => index === portfolioIndex ? "" : (asset.weights[index] ?? ""),
          ),
        })),
      };
    });
  }

  return (
    <div className="assets-tab">
      <div className="asset-toolbar">
        <label className="field benchmark-field">
          <span className="field__label">{t("benchmark")}</span>
          <TickerInput
            value={model.benchmark}
            connection={connection}
            placeholder={t("benchmarkPlaceholder")}
            searchLabel={t("searchTicker")}
            clearLabel={t("clearInput")}
            onChange={(benchmark) => setModel((current) => ({ ...current, benchmark }))}
          />
        </label>
        <div className="portfolio-count-actions">
          <button
            type="button"
            className="button button--subtle"
            onClick={() => changePortfolioCount(1)}
            disabled={model.portfolioCount >= MAX_PORTFOLIOS}
          >
            <Plus size={16} />{t("addPortfolio")}
          </button>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => changePortfolioCount(-1)}
            disabled={model.portfolioCount <= 1}
          >
            <Minus size={16} />{t("removePortfolio")}
          </button>
        </div>
      </div>

      <p className="weight-rule-hint">{t("weightRuleHint")}</p>

      <div
        className="asset-grid"
        style={{ "--portfolio-count": model.portfolioCount } as React.CSSProperties}
      >
        <div className="asset-grid__header asset-grid__asset-label">{t("asset")}</div>
        {Array.from({ length: model.portfolioCount }, (_, index) => (
          <div className="asset-grid__header portfolio-name" key={index}>
            <div className="portfolio-name__heading">
              <span className="portfolio-name__identity">
                <span>{t("portfolio")} #{index + 1}</span>
                <span
                  className={`portfolio-total-badge ${Math.abs(totals[index] - 100) <= 0.05 ? "portfolio-total-badge--complete" : ""} ${totals[index] <= 0.05 ? "portfolio-total-badge--empty" : ""}`}
                  aria-label={`${t("total")} ${totals[index].toFixed(1)}%`}
                >
                  {formatTotal(totals[index])}
                </span>
              </span>
              <button
                type="button"
                className="icon-button clear-button"
                onClick={() => clearPortfolio(index)}
                aria-label={`${t("clearPortfolio")} ${index + 1}`}
                title={t("clearPortfolio")}
              >
                <Eraser size={15} /><span className="mobile-action-label">{t("clearPortfolio")}</span>
              </button>
            </div>
            <input
              value={model.portfolioNames[index] ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setModel((current) => {
                  const names = [...current.portfolioNames];
                  names[index] = value;
                  return { ...current, portfolioNames: names };
                });
              }}
              aria-label={`${t("portfolioName")} ${index + 1}`}
            />
          </div>
        ))}
        <div className="asset-grid__header asset-grid__action" />

        {model.assets.map((asset, rowIndex) => (
          <AssetGridRow
            key={asset.id}
            asset={asset}
            rowIndex={rowIndex}
            portfolioCount={model.portfolioCount}
            connection={connection}
            t={t}
            canRemove={model.assets.length > 1}
            onSymbol={(symbol) => updateAsset(asset.id, { symbol })}
            onWeight={(portfolioIndex, value) => updateWeight(asset, portfolioIndex, value)}
            onClear={() => clearAsset(asset.id)}
            onRemove={() => removeAsset(asset.id)}
          />
        ))}

        <div className="asset-grid__total-label">{t("total")}</div>
        {totals.map((total, index) => {
          const complete = Math.abs(total - 100) <= 0.05;
          const empty = total <= 0.05;
          return (
            <div
              className={`weight-total ${complete ? "weight-total--complete" : ""} ${empty ? "weight-total--empty" : ""}`}
              key={index}
            >
              <strong>{total.toFixed(1)}%</strong>
              <span>{empty ? t("notUsed") : complete ? t("ready") : t("needsAdjustment")}</span>
            </div>
          );
        })}
        <div />
      </div>

      <button
        type="button"
        className="button button--dashed"
        onClick={addAsset}
        disabled={model.assets.length >= 20}
      >
        <Plus size={17} />{t("addAsset")} <span>{model.assets.length}/20</span>
      </button>
    </div>
  );
}

function AssetGridRow({
  asset,
  rowIndex,
  portfolioCount,
  connection,
  t,
  onSymbol,
  onWeight,
  onClear,
  onRemove,
  canRemove,
}: {
  asset: AssetRow;
  rowIndex: number;
  portfolioCount: number;
  connection: ApiConnection;
  t: Translator;
  onSymbol: (symbol: string) => void;
  onWeight: (portfolioIndex: number, value: WeightValue) => void;
  onClear: () => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  return (
    <>
      <div className="asset-symbol-cell" data-label={`${t("asset")} ${rowIndex + 1}`}>
        <span className="asset-index">{rowIndex + 1}</span>
        <TickerInput
          value={asset.symbol}
          connection={connection}
          placeholder={t("ticker")}
          searchLabel={t("searchTicker")}
          clearLabel={t("clearInput")}
          onChange={onSymbol}
        />
      </div>
      {Array.from({ length: portfolioCount }, (_, portfolioIndex) => (
        <label className="weight-input" key={portfolioIndex}>
          <span className="weight-input__label">{t("portfolio")} #{portfolioIndex + 1}</span>
          <span className="weight-input__control input-suffix">
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={asset.weights[portfolioIndex] ?? ""}
              onChange={(event) => onWeight(
                portfolioIndex,
                event.target.value === "" ? "" : Number(event.target.value),
              )}
              aria-label={`${asset.symbol || `${t("asset")} ${rowIndex + 1}`} ${t("weight")} ${portfolioIndex + 1}`}
            />
            <span>%</span>
          </span>
        </label>
      ))}
      <div className="asset-row-actions">
        <button
          type="button"
          className="icon-button asset-clear"
          onClick={onClear}
          aria-label={`${t("clearAssetRow")} ${rowIndex + 1}`}
          title={t("clearAssetRow")}
        >
          <Eraser size={16} /><span className="mobile-action-label">{t("clearAssetRow")}</span>
        </button>
        <button
          type="button"
          className="icon-button asset-delete"
          onClick={onRemove}
          disabled={!canRemove}
          aria-label={`${t("removeAssetRow")} ${rowIndex + 1}`}
          title={t("removeAssetRow")}
        >
          <Trash2 size={16} /><span className="mobile-action-label">{t("removeAssetRow")}</span>
        </button>
      </div>
    </>
  );
}

function formatTotal(total: number): string {
  return total <= 0.05 ? "0%" : `${total.toFixed(1)}%`;
}
