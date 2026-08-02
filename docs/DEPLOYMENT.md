# GitHub Pages＋Vercel Hobby 部署指南

## 正式環境

- Web：`https://chihung1024.github.io/backtest/`
- API：`https://portfolio-backtest-api.vercel.app`
- Vercel Project：`portfolio-backtest-api`
- Vercel Team：`cchungs-projects`
- GitHub Repository：`chihung1024/backtest`
- Vercel Root Directory：`backend`
- Production Branch：`main`
- Plan：Hobby

此架構不需要 Google Cloud Billing，也**完全不需要自訂 Vercel 環境變數**。

## 1. Vercel 後端

Vercel 已連接 GitHub repository。每次 `main` 的 `backend/**` 變更都會自動建立 production deployment。

後端入口：

```text
backend/index.py
```

Vercel 設定：

```text
backend/vercel.json
```

FastAPI 本體仍位於：

```text
backend/app/main.py
```

### 零設定 production 行為

Vercel 自動提供 `VERCEL` 與 `VERCEL_GIT_COMMIT_SHA`，程式會：

- 自動將 Vercel 環境視為 production。
- 關閉 `/api/docs`。
- 在 `/health` 回傳目前 Git commit SHA。
- 使用預設 CORS：`https://chihung1024.github.io` 與 `http://localhost:5173`。
- 未設定 `BACKTEST_API_KEY` 時，只接受允許的瀏覽器 `Origin`。
- 無 Origin 或其他來源回傳 `403`。
- 一般 API 每 IP 每分鐘 20 次。
- 回測 API 每 IP 每分鐘 4 次。

因此不需要在 Vercel Dashboard 建立任何環境變數。

### 可選私人金鑰模式

日後若真的需要把 API 限定為個人金鑰，可在 Vercel 設定：

```text
BACKTEST_API_KEY=<至少 32 字元的隨機值>
```

設定後 API 會要求 `X-Backtest-Key`，前端需在「資料連線」輸入相同值。這不是目前正式架構的必要條件。

## 2. GitHub Pages 前端

`.github/workflows/pages.yml` 會將：

```text
VITE_API_BASE_URL=https://portfolio-backtest-api.vercel.app
```

寫入正式前端 build，再發布 `frontend/dist`。

一般重新整理會回到裝置適用的空白模型；API URL、語言與佈景只保存在本機瀏覽器。

## 3. CI 與 production acceptance

Pull request 執行：

- Python 3.12 lint／pytest／coverage
- Node 24 lint／test／production build
- Docker image build，作為可攜性回歸測試
- Vercel Preview build status

合併到 `main` 後，`.github/workflows/vercel-production-smoke.yml` 會：

1. 等待 `/health.deployment_sha` 等於該次 `main` commit SHA。
2. 驗證無 Origin 請求回傳 `403`。
3. 驗證 GitHub Pages Origin 回傳 `200` 與正確 CORS header。
4. 執行真實 `VT` 搜尋。
5. 執行一組真實 VT／TWD 回測。

只有完全相同版本通過真實驗收，才可視為 production 發布成功。

## 4. 成本邊界

本專案使用：

- GitHub Pages：公開 repository 靜態頁面。
- GitHub Actions：公開 repository CI／部署。
- Vercel Hobby：個人非商業 API。

不再使用：

- Google Cloud Run
- Cloud Build
- Artifact Registry
- Secret Manager
- Billing Budget API
- Workload Identity Federation

Vercel Hobby 達到免費額度上限時，服務可能被限制；不會讓已移除的 Google Cloud 專案繼續按量計費。

## 5. Google Cloud 清除程序

正式 Vercel production 與 GitHub Pages 驗收成功後，清除舊專案 `backtest-465701`。

### 5.1 先確認目前專案

```bash
export PROJECT_ID="backtest-465701"
gcloud config set project "$PROJECT_ID"
gcloud projects describe "$PROJECT_ID"
```

### 5.2 刪除 Cloud Run

```bash
gcloud run services delete portfolio-backtest-api \
  --region=asia-east1 \
  --project="$PROJECT_ID"
```

### 5.3 刪除 Artifact Registry

先列出所有 repository：

```bash
gcloud artifacts repositories list --project="$PROJECT_ID"
```

確認後逐一刪除，例如：

```bash
gcloud artifacts repositories delete cloud-run-source-deploy \
  --location=asia-east1 \
  --project="$PROJECT_ID"
```

實際名稱與 location 必須以列出結果為準。

### 5.4 刪除 Secret Manager secrets

```bash
gcloud secrets delete backtest-api-key --project="$PROJECT_ID"
gcloud secrets delete backtest-fred-api-key --project="$PROJECT_ID"
```

### 5.5 刪除服務帳號

```bash
gcloud iam service-accounts delete \
  backtest-deployer@backtest-465701.iam.gserviceaccount.com \
  --project="$PROJECT_ID"

gcloud iam service-accounts delete \
  backtest-runtime@backtest-465701.iam.gserviceaccount.com \
  --project="$PROJECT_ID"
```

### 5.6 刪除 Workload Identity Pool

```bash
gcloud iam workload-identity-pools delete github \
  --location=global \
  --project="$PROJECT_ID"
```

### 5.7 解除 Billing

這一步是停止未來 GCP 可計費服務的關鍵：

```bash
gcloud billing projects unlink "$PROJECT_ID"
```

解除前已發生的用量仍可能延遲出現在最後一張帳單。

### 5.8 刪除整個 Google Cloud project

在 Vercel production 穩定且資料不需保留後：

```bash
gcloud projects delete "$PROJECT_ID"
```

本專案沒有在 GCP 保存使用者資料庫；程式碼與發布紀錄保存在 GitHub。

## 6. 還原

### Vercel rollback

在 Vercel Dashboard 的 Deployments 選擇上一個 READY production deployment，執行 Promote／Rollback。

### GitHub 還原

使用 Git tag／Release 或 revert merge commit。Vercel 與 GitHub Pages 會依新的 `main` 自動重新部署。

不應重新啟用已刪除的 Cloud Run workflow；除非重新評估並接受 Google Cloud Billing。
