const NEW_PORTFOLIO_URL = "https://backteststock.chired.workers.dev/portfolio/";
const NEW_REPOSITORY_URL = "https://github.com/chihung1024/backteststock";

export default function App() {
  return (
    <div className="retirement-shell">
      <header className="retirement-header">
        <a className="retirement-brand" href={NEW_PORTFOLIO_URL}>
          <span className="retirement-mark" aria-hidden="true">B</span>
          <span>
            <strong>Portfolio Backtest Lab</strong>
            <small>Legacy project retirement</small>
          </span>
        </a>
      </header>

      <main id="main-content" className="retirement-main">
        <section className="retirement-card" aria-labelledby="retirement-title">
          <p className="retirement-status">此舊專案已完成整合</p>
          <h1 id="retirement-title">投資組合回測已移至 BacktestStock</h1>
          <p className="retirement-lead">
            原 Portfolio Backtest Lab 的配置、現金流、再平衡、槓桿、進階分析、資料稽核、分享與匯出功能，
            已完整整合至單一獨立的 Portfolio Research 專頁。
          </p>

          <div className="retirement-actions">
            <a className="retirement-primary" href={NEW_PORTFOLIO_URL}>
              前往新的投資組合研究專頁
            </a>
            <a className="retirement-secondary" href={NEW_REPOSITORY_URL}>
              查看整合後原始碼
            </a>
          </div>

          <div className="retirement-grid" aria-label="遷移內容">
            <article>
              <span>新正式路徑</span>
              <strong>/portfolio/</strong>
              <p>可直接開啟、重新整理與分享，不再使用彈出視窗。</p>
            </article>
            <article>
              <span>正式 API</span>
              <strong>/api/v3/portfolio/*</strong>
              <p>由 BacktestStock 自有 Portfolio Ledger、TWD 估值與資料稽核契約提供。</p>
            </article>
            <article>
              <span>舊專案狀態</span>
              <strong>停止提供回測服務</strong>
              <p>舊網址僅保留遷移說明；舊 API 端點會回傳 410 Gone。</p>
            </article>
          </div>

          <aside className="retirement-note" aria-labelledby="bookmark-title">
            <h2 id="bookmark-title">請更新書籤</h2>
            <p>
              舊分享網址與瀏覽器內的舊版設定不會自動傳送到新站。請在確認新模型後，重新建立分享網址或匯入模型 JSON。
            </p>
          </aside>
        </section>
      </main>

      <footer className="retirement-footer">
        <p>此頁面只提供遷移資訊，不執行投資組合計算。</p>
      </footer>
    </div>
  );
}
