# Google Cloud → Vercel Hobby 遷移手冊

本文件將 `chihung1024/backtest` 的 FastAPI 後端由 Google Cloud Run 遷移至 Vercel Hobby。目標是保留 GitHub Pages 前端與完整回測功能，同時在驗收後移除 `backtest-465701` 的所有可計費資源並解除 Billing。

## 安全切換原則

1. 先建立 Vercel Preview／Production，Cloud Run 暫時保留。
2. 完成真實搜尋、跨幣別與完整回測驗收。
3. 將 GitHub Pages 的 `VITE_API_BASE_URL` 切換至 Vercel。
4. 觀察正式前端不再呼叫 Cloud Run。
5. 停用 Cloud Run 與 GCP 自動部署。
6. 刪除 Artifact Registry、Secret Manager 等可計費資源。
7. 解除 `backtest-465701` 的 Billing；穩定後刪除整個 project。

## Vercel 專案設定

從 Vercel Dashboard 匯入 GitHub repository `chihung1024/backtest`：

- Plan：Hobby
- Root Directory：`backend`
- Framework Preset：FastAPI（自動偵測）
- Production Branch：`main`
- Function Region：東京或新加坡附近區域

Vercel 會由根目錄 `index.py` 載入 `app.main:app`，並依 `pyproject.toml` 安裝 Python 3.12 與執行依賴。`vercel.json` 將最大執行時間設為方案允許的 300 秒，並排除測試與容器開發檔案。

## Vercel 環境變數

Production 與 Preview 均設定：

```text
BACKTEST_ENVIRONMENT=production
BACKTEST_CORS_ORIGINS=https://chihung1024.github.io
BACKTEST_CACHE_TTL_SECONDS=21600
BACKTEST_API_KEY=<新產生、至少 32 bytes 的隨機值>
BACKTEST_FRED_API_KEY=<有使用 FRED 時才設定>
```

不要複製舊 Cloud Run API key；遷移時應輪替新值。API key 不得加入 Git、PR、Issue、workflow output 或截圖。

## Vercel 驗收

依序驗證：

1. `GET /health` 回傳 HTTP 200。
2. 未提供或提供錯誤 `X-Backtest-Key` 時，受保護端點回傳 401。
3. `GET /api/v1/assets/search?q=SPY` 正常。
4. `GET /api/v1/assets/search?q=0050.TW` 正常。
5. 單一美股投組回測正常。
6. 台股＋美股跨幣別回測正常。
7. 五組投組、十年以上期間與企業行動修復正常。
8. Production deployment 的 bundle 未超過 Vercel Python function 限制。
9. Vercel Usage 中 Active CPU、記憶體與傳輸量符合 Hobby 額度。

## 正式前端切換

Vercel Production 驗收後，將 `.github/workflows/pages.yml` 內：

```yaml
VITE_API_BASE_URL: https://portfolio-backtest-api-454423251671.asia-east1.run.app
```

改成實際 Vercel Production URL，重新部署 GitHub Pages。確認瀏覽器 Network 面板與正式功能均不再呼叫 `run.app`。

## 停用 repository 內的 GCP 部署

正式前端完成切換後刪除：

- `.github/workflows/cloud-run.yml`
- `.github/workflows/billing-budget.yml`

並更新 `README.md`、`docs/DEPLOYMENT.md`，移除 Cloud Run 為正式後端的描述。

## GCP 可計費資源清理

在 Google Cloud Console 或 `gcloud` 中確認 project 是 `backtest-465701` 後執行：

```bash
gcloud run services delete portfolio-backtest-api \
  --region=asia-east1 \
  --project=backtest-465701

gcloud artifacts repositories list \
  --project=backtest-465701

# 確認實際 repository 與 location 後刪除
gcloud artifacts repositories delete <repository> \
  --location=<location> \
  --project=backtest-465701

gcloud secrets delete backtest-api-key --project=backtest-465701
gcloud secrets delete backtest-fred-api-key --project=backtest-465701

gcloud billing projects unlink backtest-465701
```

接著刪除不再需要的服務帳號與 Workload Identity Pool／Provider。穩定觀察後刪除整個 `backtest-465701` project。

## 完成標準

- GitHub Pages 只呼叫 Vercel Production API。
- Vercel Production 通過完整真實回測驗收。
- Cloud Run service 不存在。
- Artifact Registry 沒有此專案留下的 image／layer。
- Secret Manager 不存在此專案 secrets。
- GitHub 不再包含 GCP 自動部署 workflow。
- `backtest-465701` 已解除 Billing。
- Billing Reports 在延遲入帳期後不再增加新費用。
