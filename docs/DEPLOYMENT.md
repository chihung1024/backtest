# 免費資源部署指南

目標網址：

- Web：`https://chihung1024.github.io/backtest/`
- API：`https://portfolio-backtest-api-454423251671.asia-east1.run.app`

GitHub Pages 與 Actions 對公開倉庫可用免費額度；Cloud Run、Cloud Build、Artifact Registry 與 Secret Manager 仍需啟用 Google Cloud Billing，但低流量個人使用通常可落在免費額度附近。請務必在 Google Cloud 設定預算通知；「預算通知」不會自動停止服務。

目前正式環境使用 Google Cloud 專案 `backtest-465701`（專案編號
`454423251671`）、`asia-east1` 區域與 Cloud Run 服務
`portfolio-backtest-api`。Billing 已建立每月 TWD 150 預算，於 50%、90%、
100% 發送通知。下列公開資源識別碼會保存在 workflow；真正金鑰只保存在
Secret Manager。

## 1. GitHub Pages

1. 合併功能分支到 `main`。
2. 到 GitHub 倉庫 `Settings → Pages`，把 Source 設為 `GitHub Actions`。
3. `.github/workflows/pages.yml` 會建置並發布 `frontend/dist`。
4. `.github/workflows/pages.yml` 已設定正式 API URL；API URL 變更時修改該檔並
   重新執行 workflow。

API 金鑰不要放進 `VITE_*` 變數，因為前端建置內容是公開的。第一次開站時從「資料連線」輸入金鑰，它只會存進該瀏覽器的 `localStorage`。

## 2. 建立 Google Cloud 專案

正式專案已建好。需要稽核或災難復原時，先安裝並登入 `gcloud`，再設定：

```bash
export PROJECT_ID="backtest-465701"
export REGION="asia-east1"
export REPO="chihung1024/backtest"
gcloud auth login
gcloud config set project "$PROJECT_ID"
```

在 Google Cloud Console 將 Billing 帳戶連到此專案，然後啟用 API：

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  billingbudgets.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  serviceusage.googleapis.com \
  sts.googleapis.com
```

取得專案編號：

```bash
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
```

## 3. 建立專用服務帳號

```bash
gcloud iam service-accounts create backtest-deployer \
  --display-name="GitHub deployer"
gcloud iam service-accounts create backtest-runtime \
  --display-name="Portfolio backtest runtime"

export DEPLOY_SA="backtest-deployer@$PROJECT_ID.iam.gserviceaccount.com"
export RUNTIME_SA="backtest-runtime@$PROJECT_ID.iam.gserviceaccount.com"
```

部署者依 Google 的 source deploy 文件取得必要角色：

```bash
for ROLE in roles/run.sourceDeveloper roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$DEPLOY_SA" \
    --role="$ROLE"
done

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member="serviceAccount:$DEPLOY_SA" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/run.builder"
```

IAM 變更可能需數分鐘生效。

## 4. 以 Secret Manager 保存金鑰

正式 API key 已建立。若需讓新瀏覽器連線，可由有權限的管理者在
[Secret Manager](https://console.cloud.google.com/security/secret-manager/secret/backtest-api-key/versions?project=backtest-465701)
查看最新版，或在受信任的 shell 執行：

```bash
gcloud secrets versions access latest \
  --secret=backtest-api-key \
  --project=backtest-465701
```

不要把輸出加入 GitHub、前端環境變數、畫面截圖或聊天訊息。輪替時以下指令會
互動讀取並新增 secret 版本，避免把值直接寫入 shell 歷史：

```bash
read -rsp "Backtest API key: " BACKTEST_KEY; echo
printf %s "$BACKTEST_KEY" | gcloud secrets versions add \
  backtest-api-key --data-file=-
unset BACKTEST_KEY

read -rsp "FRED API key: " FRED_KEY; echo
printf %s "$FRED_KEY" | gcloud secrets versions add \
  backtest-fred-api-key --data-file=-
unset FRED_KEY
```

`backtest-fred-api-key` 目前是 `not-configured` 預留值；核心行情與投資組合回測不受
影響，但通膨與景氣環境分析需先申請免費 FRED API key 並新增 secret 版本。

Runtime 需要讀取兩個 secret；部署者需要在部署時驗證 secret 參照：

```bash
for SECRET in backtest-api-key backtest-fred-api-key; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:$RUNTIME_SA" \
    --role="roles/secretmanager.secretAccessor"
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:$DEPLOY_SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

更新金鑰時新增版本即可，不需改 workflow：

```bash
printf %s "new-value" | gcloud secrets versions add backtest-api-key --data-file=-
```

## 5. 建立 GitHub OIDC 信任

此流程不建立或下載長效 JSON 私鑰。

```bash
gcloud iam workload-identity-pools create github \
  --location=global \
  --display-name="GitHub Actions"

export WIF_POOL="$(gcloud iam workload-identity-pools describe github \
  --location=global --format='value(name)')"

gcloud iam workload-identity-pools providers create-oidc backtest \
  --location=global \
  --workload-identity-pool=github \
  --display-name="chihung1024/backtest" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_id == '1308276686' && assertion.repository_owner_id == '104315542' && assertion.ref == 'refs/heads/main'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$WIF_POOL/attribute.repository_id/1308276686"

export WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe backtest \
  --location=global \
  --workload-identity-pool=github \
  --format='value(name)')"
echo "$WIF_PROVIDER"
```

## 6. GitHub Actions 部署識別碼

下列值已寫在 `.github/workflows/cloud-run.yml`，不需要 GitHub Actions Variables：

| 名稱 | 值 |
|---|---|
| `GCP_PROJECT_ID` | `backtest-465701` |
| `GCP_REGION` | `asia-east1` |
| `GCP_CLOUD_RUN_SERVICE` | `portfolio-backtest-api` |
| `GCP_WIF_PROVIDER` | `projects/454423251671/locations/global/workloadIdentityPools/github/providers/backtest` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `backtest-deployer@backtest-465701.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | `backtest-runtime@backtest-465701.iam.gserviceaccount.com` |
| `GCP_API_KEY_SECRET` | `backtest-api-key` |
| `GCP_FRED_API_KEY_SECRET` | `backtest-fred-api-key` |

這些是資源識別碼，不是秘密；真正金鑰只存在 Secret Manager。

## 7. 第一次部署與公開呼叫

合併 backend 或 Cloud Run workflow 變更到 `main` 後會自動部署，也可在 GitHub
Actions 手動執行 `Deploy API to Cloud Run`。服務允許公開 HTTPS 呼叫，`/health`
不需金鑰；搜尋與回測端點仍受應用層 `X-Backtest-Key` 保護：

```bash
gcloud run services add-iam-policy-binding portfolio-backtest-api \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"

gcloud run services describe portfolio-backtest-api \
  --region="$REGION" \
  --format='value(status.url)'
```

驗證：

```bash
curl "https://YOUR-SERVICE.run.app/health"
curl -H "X-Backtest-Key: YOUR_KEY" \
  "https://YOUR-SERVICE.run.app/api/v1/assets/search?q=VT"
```

## 8. 成本與維運保護

- Cloud Run 已限制最多兩個執行個體、每個 512 MiB，閒置時縮到零。
- Billing 已建立每月 TWD 150 預算與 50%、90%、100% 通知；預算不會自動停機。
- 定期查看 Cloud Run request count、錯誤率與 p95 latency。
- 若發現異常流量，先移除 `allUsers` 的 `roles/run.invoker`，再輪替 `backtest-api-key`。
- Artifact Registry 會保留 source deploy 映像；可設定清理政策保留最近版本以避免儲存費累積。

## 常見問題

### OIDC 顯示 403

確認 workflow 由 `chihung1024/backtest` 的 `main` 分支執行、WIF provider 使用專案
編號而非專案 ID，並等待 IAM 傳播至少五分鐘。OIDC 條件刻意使用不可重新命名的
repository／owner 數字 ID，避免同名 repository 被冒用。

### Pages 可開啟但顯示未連線

確認 workflow 內的 `VITE_API_BASE_URL` 正確後重新建置 Pages；也可直接在網站的
「資料連線」覆寫 URL。API key 必須由使用者在瀏覽器輸入。

全新 repository 第一次發布前，owner 必須到 `Settings → Pages`，將
`Build and deployment → Source` 設為 `GitHub Actions`。這是 GitHub 的一次性
管理權限要求；一般 workflow token 即使具備 `pages: write` 也可能無法建立
Pages site。完成後，後續建置與發布都由 workflow 自動執行。

### Yahoo Finance 暫時失敗

稍後重試，確認代碼與日期有效。這個服務刻意不以付費資料源自動兜底，以免產生未預期成本。
容器映像會一併安裝 yfinance `repair=True` 所需的 SciPy，並為非 root runtime
預先建立可寫入的 `/tmp/.cache/py-yfinance`；不要在精簡映像中移除這兩項設定。
