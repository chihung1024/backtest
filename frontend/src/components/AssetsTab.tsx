import { Minus, Plus, Trash2 } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import type { Translator } from "../i18n";
import type { ApiConnection, AssetRow, BacktestFormState } from "../types";
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

  function updateWeight(asset: AssetRow, portfolioIndex: number, value: number) {
    const weights = [...asset.weights];
    weights[portfolioIndex] = value;
    updateAsset(asset.id, { weights });
  }

  function addAsset() {
    if (model.assets.length >= 20) return;
    setModel((current) => ({
      ...current,
      assets: [
        ...current.assets,
        { id: crypto.randomUUID(), symbol: "", weights: [0, 0, 0] },
      ],
    }));
  }

  function removeAsset(id: string) {
    setModel((current) => ({
      ...current,
      assets: current.assets.length <= 1 ? current.assets : current.assets.filter((asset) => asset.id !== id),
    }));
  }

  function changePortfolioCount(delta: number) {
    setModel((current) => ({
      ...current,
      portfolioCount: Math.min(3, Math.max(1, current.portfolioCount + delta)),
    }));
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
            onChange={(benchmark) => setModel((current) => ({ ...current, benchmark }))}
          />
        </label>
        <div className="portfolio-count-actions">
          <button
            type="button"
            className="button button--subtle"
            onClick={() => changePortfolioCount(1)}
            disabled={model.portfolioCount >= 3}
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

      <div
        className="asset-grid"
        style={{ "--portfolio-count": model.portfolioCount } as React.CSSProperties}
      >
        <div className="asset-grid__header asset-grid__asset-label">{t("asset")}</div>
        {Array.from({ length: model.portfolioCount }, (_, index) => (
          <label className="asset-grid__header portfolio-name" key={index}>
            <span>{t("portfolio")} #{index + 1}</span>
            <input
              value={model.portfolioNames[index]}
              onChange={(event) => {
                const names = [...model.portfolioNames];
                names[index] = event.target.value;
                setModel((current) => ({ ...current, portfolioNames: names }));
              }}
              aria-label={`${t("portfolioName")} ${index + 1}`}
            />
          </label>
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
            onSymbol={(symbol) => updateAsset(asset.id, { symbol })}
            onWeight={(portfolioIndex, value) => updateWeight(asset, portfolioIndex, value)}
            onRemove={() => removeAsset(asset.id)}
          />
        ))}

        <div className="asset-grid__total-label">{t("total")}</div>
        {totals.map((total, index) => {
          const complete = Math.abs(total - 100) <= 0.05;
          return (
            <div className={`weight-total ${complete ? "weight-total--complete" : ""}`} key={index}>
              <strong>{total.toFixed(1)}%</strong>
              <span>{complete ? t("ready") : t("needsAdjustment")}</span>
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
  onRemove,
}: {
  asset: AssetRow;
  rowIndex: number;
  portfolioCount: number;
  connection: ApiConnection;
  t: Translator;
  onSymbol: (symbol: string) => void;
  onWeight: (portfolioIndex: number, value: number) => void;
  onRemove: () => void;
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
          onChange={onSymbol}
        />
      </div>
      {Array.from({ length: portfolioCount }, (_, portfolioIndex) => (
        <label
          className="weight-input input-suffix"
          data-label={`${t("portfolio")} ${portfolioIndex + 1}`}
          key={portfolioIndex}
        >
          <input
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={asset.weights[portfolioIndex] || ""}
            onChange={(event) => onWeight(portfolioIndex, Number(event.target.value))}
            aria-label={`${asset.symbol || `${t("asset")} ${rowIndex + 1}`} ${t("weight")} ${portfolioIndex + 1}`}
          />
          <span>%</span>
        </label>
      ))}
      <button type="button" className="icon-button asset-delete" onClick={onRemove} aria-label="Remove asset">
        <Trash2 size={16} />
      </button>
    </>
  );
}
