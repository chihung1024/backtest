# Portfolio Backtest Lab

一套面向美股、台股與跨幣別資產的個人投資組合回測網站。介面參考 Portfolio Visualizer 的 Portfolio Performance 工作流，以 `yfinance` 為主要行情來源，並保留透明、可測試的計算核心。

線上網站：[https://chihung1024.github.io/backtest/](https://chihung1024.github.io/backtest/)

正式 API：[https://portfolio-backtest-api-454423251671.asia-east1.run.app](https://portfolio-backtest-api-454423251671.asia-east1.run.app)

> 本專案僅供個人研究與教育，不構成投資建議。Yahoo Finance 資料的使用仍受 Yahoo 與 yfinance 的使用條款限制。

## 功能

- 同時比較最多三組投資組合，每組最多二十項資產。
- 美股代碼、`.TW`／`.TWO` 台股與純數字台股代碼搜尋。
- 拆股／反向拆股、普通與特別股利、基金資本利得配發修復與稽核。
- USD、TWD 與其他 ISO 幣別的 Yahoo Finance 外匯報酬換算。
- 固定或比例現金流、投入時點、年成長率與 XIRR。
- 每月／季／半年／年與偏離門檻再平衡。
- 股息再投入或保留現金、股息收入、交易成本與槓桿利息。
- 時間加權報酬、CAGR、Sharpe、Sortino、Calmar、VaR、CVaR、回撤、Alpha、Beta。
- 年度長條圖、月報酬熱圖、資產成長、回撤、收入與期末配置。
- Fama–French 因子回歸、報酬式風格分析與市場／波動／通膨／景氣環境分析。
- 繁體中文／英文、響應式介面、深色模式、CSV／JSON 匯出與無伺服器分享網址。
- 瀏覽器本機保存模型與個人 API 連線，不需要會員資料庫。

## 架構

```text
frontend/   React、TypeScript、Vite、Recharts；由 GitHub Pages 託管
backend/    FastAPI、yfinance、pandas、NumPy；由 Google Cloud Run 執行
docs/       架構、計算方法、API 與逐步部署手冊
.github/    CI、GitHub Pages、Cloud Run 與 Dependabot 自動化
```

詳細設計請參閱[系統架構](docs/ARCHITECTURE.md)與[回測方法](docs/METHODOLOGY.md)。

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

測試使用固定合成行情，不依賴 Yahoo Finance 當下是否可用。GitHub Actions 也會建置正式 Docker image，避免只在開發環境可執行。

## 部署

合併到 `main` 後，GitHub Pages workflow 會發布前端，Cloud Run workflow 會透過短效 OIDC 身分自動部署 API；不保存 Google Cloud 服務帳號私鑰。正式資源識別碼可公開並已寫入 workflow，API 與 FRED 金鑰只存在 Google Secret Manager。完整設定、金鑰輪替與成本保護請參閱[免費資源部署指南](docs/DEPLOYMENT.md)。

## 文件

- [系統架構與安全邊界](docs/ARCHITECTURE.md)
- [回測計算方法與限制](docs/METHODOLOGY.md)
- [API 使用說明](docs/API.md)
- [GitHub Pages＋Cloud Run 部署](docs/DEPLOYMENT.md)
- [版本封存與還原](docs/RELEASES.md)
