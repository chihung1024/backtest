import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const NEW_PORTFOLIO_URL = "https://backteststock.chired.workers.dev/portfolio/";
const NEW_REPOSITORY_URL = "https://github.com/chihung1024/backteststock";

describe("Legacy retirement page", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the completed migration and the canonical destination", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "投資組合回測已移至 BacktestStock" }),
    ).toBeInTheDocument();
    expect(screen.getByText("此舊專案已完成整合")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "前往新的投資組合研究專頁" }),
    ).toHaveAttribute("href", NEW_PORTFOLIO_URL);
    expect(
      screen.getByRole("link", { name: "查看整合後原始碼" }),
    ).toHaveAttribute("href", NEW_REPOSITORY_URL);
  });

  it("contains no runnable backtest, connection dialog, or configuration tabs", () => {
    render(<App />);

    expect(screen.queryByRole("button", { name: /執行回測/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /資料連線/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.getByText("此頁面只提供遷移資訊，不執行投資組合計算。")).toBeInTheDocument();
  });

  it("does not issue any network request while rendering", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains the replacement route, API, and legacy service state", () => {
    render(<App />);

    expect(screen.getByText("/portfolio/")).toBeInTheDocument();
    expect(screen.getByText("/api/v3/portfolio/*")).toBeInTheDocument();
    expect(screen.getByText("停止提供回測服務")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "請更新書籤" })).toBeInTheDocument();
  });

  it("has no automatically detectable accessibility violations", async () => {
    const { container } = render(<App />);
    const audit = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(audit.violations).toEqual([]);
  });
});
