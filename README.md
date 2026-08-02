# Portfolio Backtest Lab

一套面向美股、台股與跨幣別資產的個人投資組合回測網站。介面參考 Portfolio Visualizer 的 Portfolio Performance 工作流，以 `yfinance` 為主要行情來源，並保留透明、可測試的計算核心。

- Web：`https://chihung1024.github.io/backtest/`
- API：`https://portfolio-backtest-api.vercel.app`

> 本專案僅供個人研究與教育，不構成投資建議。Yahoo Finance 資料的使用仍受 Yahoo 與 yfinance 的使用條款限制。

## 功能

- 同時比較最多五組投資組合，每組最多二十項資產；空白或 0% 的組合會自動略過。
- 美股代碼、`.TW`／`.TWO` 台股與純數字台股代碼搜尋。
- 拆股／反向拆股、普通與特別股利、基金資本利得配發修復與稽核。
- 依 Yahoo 實際報價幣別，將美股、港股、日股與其他市場逐日換算為 TWD 後統一估值。
- 固定或比例現金流、投入時點、年成長率與 XIRR。
- 每月／季／半年／年與偏離門檻再平衡。
- 股息再投入或保留現金、股息收入、交易成本與槓桿利息。
- 時間加權報酬、CAGR、Sharpe、Sortino、Calmar、VaR、CVaR、回撤、Alpha、Beta。
- 年度長條圖、月報酬熱圖、收入與期末配置。
- Fama–French 因子回歸、報酬式風格分析與市場／波動／通膨／景氣環境分析。
- 繁體中文／英文、深色模式、CSV／JSON 匯出與無伺服器分享網址。

## 架構

```text
frontend/   React、TypeScript、Vite、Recharts；由 GitHub Pages 託管
backend/    FastAPI、yfinance、pandas、NumPy；由 Vercel Hobby Python Function 執行
docs/       架構、計算方法、API 與部署手冊
.github/    CI、GitHub Pages、Vercel production acceptance
```

正式環境**完全不需要自訂環境變數**：

- Vercel 會自動被辨識為 production。
- CORS 預設只允許本機與 `https://chihung1024.github.io`。
- 未設定 API key 時，API 只接受允許清單中的瀏覽器 `Origin`；無 Origin 或其他來源會回傳 `403`。
- 一般 API 每 IP 每分鐘 20 次，回測端點每 IP 每分鐘 4 次。
- Vercel Hobby 超過免費額度時服務會受限，不會轉成 Google Cloud 按量計費。

## 本機啟動

需要 Python 3.12 與 Node.js 24。

### API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API 健康檢查為 `http://localhost:8000/health`，開發文件為 `http://localhost:8000/api/docs`。

### Web

另開一個 shell：

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

開啟 `http://localhost:5173`。也可直接在專案根目錄執行 `docker compose up --build`。

## 品質檢查

```bash
cd backend
ruff check app tests
pytest --cov=app

cd ../frontend
npm run lint
npm test
npm run build
```

測試使用固定合成行情，不依賴 Yahoo Finance 當下是否可用。合併到 `main` 後，Vercel 會部署 production API，GitHub Actions 會等待相同 commit SHA 上線，再執行真實健康檢查、Origin 授權、標的搜尋與回測驗收。

## 部署

- 前端：GitHub Pages workflow。
- 後端：Vercel Git Integration，Project Root Directory 為 `backend`。
- Project：`portfolio-backtest-api`。
- Production domain：`portfolio-backtest-api.vercel.app`。
- 不再使用 Google Cloud Run、Cloud Build、Artifact Registry 或 Secret Manager。

完整設定、驗收、GCP 清除與還原流程見 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。

## 文件

- [系統架構與安全邊界](docs/ARCHITECTURE.md)
- [回測計算方法與限制](docs/METHODOLOGY.md)
- [API 使用說明](docs/API.md)
- [UI 品質標準與發版閘門](docs/UI_QUALITY.md)
- [GitHub Pages＋Vercel Hobby 部署](docs/DEPLOYMENT.md)
- [版本封存與還原](docs/RELEASES.md)
