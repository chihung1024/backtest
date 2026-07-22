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

每組投資組合權重須合計為 100%，容許 0.05 個百分點的浮點誤差。單次最多三組投資組合、每組二十個資產；伺服器另限制所有唯一代碼合計不超過 64 個。

## 錯誤格式

- `401`：存取金鑰錯誤。
- `422`：模型、權重、日期或資料不可用。
- `429`：超過每分鐘速率限制。
- `502`：上游 Yahoo Finance 暫時失敗。

FastAPI 驗證錯誤的 `detail` 是陣列；業務與資料錯誤的 `detail` 是文字。前端已將兩種格式轉成可讀訊息。
