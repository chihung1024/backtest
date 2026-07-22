# 免費資源部署指南

目標網址：

- Web：`https://chihung1024.github.io/backtest/`
- API：Google Cloud Run 配發的 `https://...run.app`

GitHub Pages 與 Actions 對公開倉庫可用免費額度；Cloud Run、Cloud Build、Artifact Registry 與 Secret Manager 仍需啟用 Google Cloud Billing，但低流量個人使用通常可落在免費額度附近。請務必在 Google Cloud 設定預算通知；「預算通知」不會自動停止服務。

## 1. GitHub Pages

1. 合併功能分支到 `main`。
2. 到 GitHub 倉庫 `Settings → Pages`，把 Source 設為 `GitHub Actions`。
3. `.github/workflows/pages.yml` 會建置並發布 `frontend/dist`。
4. Cloud Run 完成後，在 `Settings → Secrets and variables → Actions → Variables` 新增：

   - `VITE_API_BASE_URL`：Cloud Run API 完整網址，不要結尾斜線。

5. 在 Actions 手動重跑 `Deploy web to GitHub Pages`，讓預設 API 網址寫入靜態檔。

API 金鑰不要放進 `VITE_*` 變數，因為前端建置內容是公開的。第一次開站時從「資料連線」輸入金鑰，它只會存進該瀏覽器的 `localStorage`。

## 2. 建立 Google Cloud 專案

先安裝並登入 `gcloud`，再於本機 shell 設定下列值。專案 ID 必須全球唯一：

```bash
export PROJECT_ID="your-unique-project-id"
export REGION="asia-east1"
export REPO="chihung1024/backtest"
gcloud auth login
gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"
```

在 Google Cloud Console 將 Billing 帳戶連到此專案，然後啟用 API：

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
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

先自行產生一組高熵 API 金鑰，並申請免費 FRED API key。以下指令會互動讀取，不會把值直接寫在 shell 歷史中：

```bash
read -rsp "Backtest API key: " BACKTEST_KEY; echo
printf %s "$BACKTEST_KEY" | gcloud secrets create backtest-api-key --data-file=-
unset BACKTEST_KEY

read -rsp "FRED API key: " FRED_KEY; echo
printf %s "$FRED_KEY" | gcloud secrets create backtest-fred-api-key --data-file=-
unset FRED_KEY
```

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
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository == 'chihung1024/backtest'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$WIF_POOL/attribute.repository/$REPO"

export WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe backtest \
  --location=global \
  --workload-identity-pool=github \
  --format='value(name)')"
echo "$WIF_PROVIDER"
```

## 6. 設定 GitHub Actions Variables

到 `Settings → Secrets and variables → Actions → Variables` 新增：

| 名稱 | 值 |
|---|---|
| `GCP_PROJECT_ID` | `$PROJECT_ID` 的實際值 |
| `GCP_REGION` | `asia-east1` |
| `GCP_CLOUD_RUN_SERVICE` | `portfolio-backtest-api` |
| `GCP_WIF_PROVIDER` | 上一步輸出的完整 provider 名稱 |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `backtest-deployer@PROJECT_ID.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | `backtest-runtime@PROJECT_ID.iam.gserviceaccount.com` |
| `GCP_API_KEY_SECRET` | `backtest-api-key` |
| `GCP_FRED_API_KEY_SECRET` | `backtest-fred-api-key` |

這些是資源識別碼，不是秘密；真正金鑰只存在 Secret Manager。

## 7. 第一次部署與公開呼叫

在 GitHub Actions 手動執行 `Deploy API to Cloud Run`。成功後，先允許公開網路呼叫；實際回測仍受應用層 API key 保護：

```bash
gcloud run services add-iam-policy-binding portfolio-backtest-api \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"

gcloud run services describe portfolio-backtest-api \
  --region="$REGION" \
  --format='value(status.url)'
```

把輸出的 URL 填入 GitHub `VITE_API_BASE_URL`，重跑 Pages workflow。驗證：

```bash
curl "https://YOUR-SERVICE.run.app/health"
curl -H "X-Backtest-Key: YOUR_KEY" \
  "https://YOUR-SERVICE.run.app/api/v1/assets/search?q=VT"
```

## 8. 成本與維運保護

- Cloud Run 已限制最多兩個執行個體、每個 512 MiB，閒置時縮到零。
- 在 Billing 建立低額度月預算與 50%、90%、100% 通知。
- 定期查看 Cloud Run request count、錯誤率與 p95 latency。
- 若發現異常流量，先移除 `allUsers` 的 `roles/run.invoker`，再輪替 `backtest-api-key`。
- Artifact Registry 會保留 source deploy 映像；可設定清理政策保留最近版本以避免儲存費累積。

## 常見問題

### Cloud Run workflow 顯示 skipped

表示上表的 GitHub Variables 尚未全部建立。變數名稱需完全相同。

### OIDC 顯示 403

確認 repository attribute 是 `chihung1024/backtest`、WIF provider 使用專案編號而非專案 ID，並等待 IAM 傳播至少五分鐘。

### Pages 可開啟但顯示未連線

確認 `VITE_API_BASE_URL` 已設定後重新建置 Pages；也可直接在網站的「資料連線」覆寫 URL。API key 必須由使用者在瀏覽器輸入。

### Yahoo Finance 暫時失敗

稍後重試，確認代碼與日期有效。這個服務刻意不以付費資料源自動兜底，以免產生未預期成本。
