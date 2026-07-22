# API 使用說明

本機開發模式可在 `http://localhost:8000/api/docs` 使用互動式 OpenAPI 文件。正式環境預設關閉文件頁面，但端點與資料模型相同。

## 健康檢查

```http
GET /health
```

不需要金鑰，Cloud Run 與前端用它檢查服務狀態。

## 驗證個人金鑰

```http
GET /api/v1/auth/check
X-Backtest-Key: your-personal-key
```

前端的連線狀態與「測試連線」會先檢查健康端點，再以此端點確認金鑰有效。

## 搜尋標的

```http
GET /api/v1/assets/search?q=2330&limit=8
X-Backtest-Key: your-personal-key
```

純數字台股會優先提供 `.TW` 與 `.TWO` 候選，再合併 Yahoo Finance 搜尋結果。

## 執行回測

```http
POST /api/v1/backtests
Content-Type: application/json
X-Backtest-Key: your-personal-key
```

最小請求：

```json
{
  "portfolios": [
    {
      "name": "全球股債",
      "assets": [
        {"symbol": "VT", "weight": 80},
        {"symbol": "BND", "weight": 20}
      ]
    }
  ],
  "benchmark": "VT",
  "start_date": "2016-01-01",
  "end_date": "2026-07-22",
  "initial_amount": 1000000,
  "base_currency": "TWD"
}
```

送至 API 的每組投資組合權重須合計為 100%，容許 0.05 個百分點的浮點誤差。前端會忽略空白或 0% 的組合。單次最多五組投資組合、每組二十個資產；伺服器另限制所有唯一代碼合計不超過 64 個。

`base_currency` 可省略，預設且只接受 `TWD`；傳入其他幣別會回傳 `422`，避免前端或
舊客戶端意外產生非台幣結果。`output_frequency` 預設為 `daily`，也可選 `weekly` 或
`monthly` 以縮減曲線資料量；這個欄位只影響 `series` 的呈現點位，績效與風險指標
仍以完整每日序列計算。

回應頂層 `base_currency` 固定為 `TWD`，所有金額與績效序列均已逐日換算為台幣。
`assets[].currency` 是 Yahoo 回傳的標的原始報價幣別，讓使用者能稽核換算來源。
每個 `results[]` 會同時回傳原始 `name`、統一供介面與 CSV 使用的 `display_name`、
回測設定的 `target_allocation` 與期末漂移後的 `final_allocation`。`display_name` 依
`target_allocation` 由大到小列出最多三個標的及比例；基準名稱則維持
`Benchmark · TICKER`，避免重複標示。

`assets` 除了有效日期、原始報價幣別與觀察值數量，也包含企業行動稽核欄位：

| 欄位 | 說明 |
|---|---|
| `dividend_events` | Yahoo 普通／特別現金股利事件數 |
| `capital_gain_events` | 基金資本利得配發事件數 |
| `split_events` | 拆股與反向拆股事件數 |
| `repaired_observations` | yfinance `repair=True` 修復的價格列數 |
| `split_corrections` | 本站偵測並修正的殘留拆股跳變數 |

若 `repaired_observations` 或 `split_corrections` 大於零，`warnings` 也會留下可見提醒。

## 錯誤格式

- `401`：存取金鑰錯誤。
- `422`：模型、權重、日期或資料不可用。
- `429`：超過每分鐘速率限制。
- `502`：上游 Yahoo Finance 暫時失敗。

FastAPI 驗證錯誤的 `detail` 是陣列；業務與資料錯誤的 `detail` 是文字。前端已將兩種格式轉成可讀訊息。
