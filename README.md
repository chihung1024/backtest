# Portfolio Backtest Lab — Retired

本專案的功能已完整整合至 [`chihung1024/backteststock`](https://github.com/chihung1024/backteststock)。新的正式投資組合研究頁面為：

- Portfolio Research：`https://backteststock.chired.workers.dev/portfolio/`
- 正式 API：`https://backteststock.chired.workers.dev/api/v3/portfolio/*`

## 退役後行為

此 Draft PR 合併後：

- GitHub Pages 不再載入舊回測應用，只顯示遷移通知與新站連結。
- 舊 Vercel API 的 `/`、`/health` 與全部 `/api/v1/*` 端點統一回傳 `410 Gone`。
- `410` 回應包含 `legacy_project_retired`、新站網址與目前 Vercel Git SHA，供部署驗收與稽核。
- 舊程式碼暫時保留在 repository 歷史中，便於最後確認與回復；不再作為正式 runtime。

## 為何退役

Portfolio Backtest Lab 的主要功能已改由 BacktestStock 的單一獨立專頁與自有 Portfolio v3 API 提供，包括：

- 最多五組投資組合與二十列資產配置。
- TWD 每日估值、跨幣別 FX、公司行為與資料指紋稽核。
- 現金流、配息、交易成本、再平衡與槓桿帳本。
- CAGR、XIRR、Sharpe、Sortino、Calmar、VaR、CVaR、Alpha、Beta 與回撤。
- 因子、風格、環境與通膨分析。
- 完整全頁式結果儀表板、模型儲存、分享與匯出。

## Draft PR 安全邊界

在專案擁有者確認整合後版本前，本階段只建立並測試退役 Draft PR：

- 不合併至 `main`。
- 不部署 GitHub Pages 退役頁。
- 不讓舊 production API 回傳 410。
- 不停用或刪除 Vercel Project。
- 不封存或刪除此 repository。

最終下線、封存與刪除步驟見 [`docs/RETIREMENT.md`](docs/RETIREMENT.md)。
