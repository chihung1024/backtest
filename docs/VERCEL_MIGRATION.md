# Google Cloud → Vercel Hobby 遷移紀錄

本文件記錄 `chihung1024/backtest` 後端由 Google Cloud Run 遷移至 Vercel Hobby 的決策與完成狀態。日常部署與 GCP 清除步驟以 [`DEPLOYMENT.md`](DEPLOYMENT.md) 為準。

## 目標

- 保留 GitHub Pages 前端與完整 FastAPI 回測功能。
- 不再依賴 Cloud Run、Cloud Build、Artifact Registry 或 Secret Manager。
- 不要求使用者理解或設定 Vercel 環境變數。
- GCP 清除後解除 `backtest-465701` Billing，避免未來按量費用。

## 正式架構

- Web：`https://chihung1024.github.io/backtest/`
- API：`https://portfolio-backtest-api.vercel.app`
- Vercel Project：`portfolio-backtest-api`
- Root Directory：`backend`
- Production Branch：`main`
- Plan：Hobby

## 零設定安全模式

正式環境不需要自訂環境變數：

1. Vercel 由系統變數自動被辨識為 production。
2. `/api/docs` 在 production 關閉。
3. `/health` 回傳 `VERCEL_GIT_COMMIT_SHA`，供發布驗收比對。
4. 未設定 `BACKTEST_API_KEY` 時，`/api/v1/*` 只接受：
   - `https://chihung1024.github.io`
   - `http://localhost:5173`
5. 無 Origin 或其他來源回傳 `403`。
6. 一般 API 每 IP 每分鐘 20 次；回測 API 每 IP 每分鐘 4 次。
7. 若日後設定 `BACKTEST_API_KEY`，仍可切回 `X-Backtest-Key` 私人模式。

## 已完成的 repository 變更

- 新增 Vercel FastAPI entrypoint 與 `vercel.json`。
- GitHub Pages API URL 改為 Vercel production。
- 刪除 Cloud Run deployment workflow。
- 刪除 GCP Billing Budget workflow。
- 新增 Vercel production acceptance workflow。
- 更新 README、API、架構與部署文件。
- 新增無 Origin／允許 Origin／錯誤 Origin 的回歸測試。

## Production acceptance

合併到 `main` 後，GitHub Actions 會等待 Vercel `/health.deployment_sha` 等於該次 main commit，再執行：

- 無 Origin 必須回傳 `403`。
- GitHub Pages Origin 必須回傳 `200` 與正確 CORS header。
- 真實 VT 搜尋。
- 真實 VT／TWD 回測。

這避免誤把上一版 production 當成新版本驗收。

## GCP 收尾

Vercel production 與 GitHub Pages 驗收成功後，依 [`DEPLOYMENT.md`](DEPLOYMENT.md) 清除：

- Cloud Run service
- Artifact Registry repositories／images
- Secret Manager secrets
- 部署與 runtime service accounts
- Workload Identity Pool／Provider
- Billing link
- 最後刪除 `backtest-465701` project

解除 Billing 前已發生的用量仍可能延遲出現在最後一張帳單。
