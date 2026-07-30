from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise RuntimeError(f"Expected exactly one match in {path}, found {content.count(old)}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/app/data/yfinance_provider.py",
    "from app.data.corporate_actions import reconcile_corporate_actions\n",
    "from app.data.corporate_actions import reconcile_corporate_actions\n"
    "from app.data.price_quality import reconcile_ohlc_levels\n",
)

old_method = '''    def _download_fx_levels(
        self, source_currency: str, target_currency: str, start: date, end: date
    ) -> pd.Series:
        candidates = _fx_candidates(source_currency, target_currency)
        for ticker, invert in candidates:
            try:
                raw = yf.download(
                    ticker,
                    start=(start - timedelta(days=_FX_LOOKBACK_DAYS)).isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                    timeout=20,
                )
                if raw.empty:
                    continue
                close = raw["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close.index = pd.to_datetime(close.index).tz_localize(None)
                series = close.astype(float)
                if invert:
                    series = 1.0 / series
                series = series.replace([np.inf, -np.inf], np.nan).dropna()
                if series.notna().sum() > 1:
                    return series
            except Exception as exc:
                logger.warning("FX download failed for %s: %s", ticker, exc)
        raise ValueError(
            f"Unable to convert {source_currency} assets into {target_currency}; "
            "no Yahoo FX history was available"
        )
'''

new_method = '''    def _download_fx_levels(
        self, source_currency: str, target_currency: str, start: date, end: date
    ) -> pd.Series:
        candidates = _fx_candidates(source_currency, target_currency)
        usable: list[tuple[tuple[int, int, int, int], str, pd.Series]] = []
        for priority, (ticker, invert) in enumerate(candidates):
            try:
                raw = yf.download(
                    ticker,
                    start=(start - timedelta(days=_FX_LOOKBACK_DAYS)).isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    auto_adjust=True,
                    actions=False,
                    repair=False,
                    keepna=True,
                    progress=False,
                    threads=False,
                    timeout=20,
                )
                if raw.empty:
                    continue
                frame = _ticker_frame(raw, ticker, 1)
                if frame.empty:
                    frame = raw
                reconciliation = reconcile_ohlc_levels(frame, invert=invert)
                series = reconciliation.levels
                if series.notna().sum() <= 1:
                    continue
                gross = series / series.shift(1)
                material_transitions = int(
                    ((gross < (1.0 / 1.8)) | (gross > 1.8)).fillna(False).sum()
                )
                score = (
                    reconciliation.unresolved_count,
                    material_transitions,
                    reconciliation.correction_count,
                    priority,
                )
                usable.append((score, ticker, series))
                if reconciliation.correction_count:
                    logger.info(
                        "Reconciled %s impossible FX close observation(s) for %s",
                        reconciliation.correction_count,
                        ticker,
                    )
            except Exception as exc:
                logger.warning("FX download failed for %s: %s", ticker, exc)
        if usable:
            score, ticker, series = min(usable, key=lambda item: item[0])
            if score[0] or score[1]:
                logger.warning(
                    "Selected FX history %s with quality score unresolved=%s transitions=%s",
                    ticker,
                    score[0],
                    score[1],
                )
            return series
        raise ValueError(
            f"Unable to convert {source_currency} assets into {target_currency}; "
            "no Yahoo FX history was available"
        )
'''

replace_once("backend/app/data/yfinance_provider.py", old_method, new_method)

replace_once(
    "docs/METHODOLOGY.md",
    "匯率，系統會嘗試反向報價。\n\n系統先對齊「匯率水準」再計算區間報酬",
    "匯率，系統會嘗試反向報價。每個直接與反向候選報價都先以同日 OHLC 恆等關係校驗："
    "有效收盤價必須落在該日最低價與最高價之間。若資料源只把 Close 寫成錯誤尺度，"
    "但 Open／High／Low 與前後有效收盤價一致，系統會以時間加權對數內插重建收盤價，"
    "並限制在當日價格區間內；真實的大幅行情只要 OHLC 自洽就不會被改寫。候選報價"
    "完成相同正規化後，再依未解決欄位、重大跳變與修復次數排序選用，不依代碼、日期"
    "或固定匯率倍數。\n\n系統先對齊「匯率水準」再計算區間報酬",
)

for path in (
    "backend/app/__init__.py",
    "backend/pyproject.toml",
    "frontend/package.json",
    "frontend/package-lock.json",
):
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    if "0.6.5" not in content:
        raise RuntimeError(f"Expected version 0.6.5 in {path}")
    target.write_text(content.replace("0.6.5", "0.6.6"), encoding="utf-8")
