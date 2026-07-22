import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = "";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the configuration workflow", () => {
    render(<App />);
    expect(screen.getAllByText("投資組合回測實驗室").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /投資組合資產/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /執行回測/ })).toBeInTheDocument();
  });

  it("has no automatically detectable accessibility violations in the main workflow", async () => {
    const { container } = render(<App />);
    const audit = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(audit.violations).toEqual([]);
  });

  it("has no automatically detectable accessibility violations in assets and connection flows", async () => {
    const { container } = render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));
    let audit = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(audit.violations).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "資料連線" }));
    audit = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(audit.violations).toEqual([]);
  });

  it("marks both date fields with the constrained mobile control", () => {
    render(<App />);

    expect(screen.getByLabelText("開始日期")).toHaveClass("date-input", "date-input--centered");
    expect(screen.getByLabelText("結束日期")).toHaveClass("date-input", "date-input--centered");
  });

  it("links configuration tabs to their panel and supports arrow-key navigation", () => {
    render(<App />);

    const settingsTab = screen.getByRole("tab", { name: /回測設定/ });
    const assetsTab = screen.getByRole("tab", { name: /投資組合資產/ });
    const panel = screen.getByRole("tabpanel");
    expect(settingsTab).toHaveAttribute("aria-controls", "configuration-panel");
    expect(settingsTab).toHaveAttribute("tabindex", "0");
    expect(assetsTab).toHaveAttribute("tabindex", "-1");
    expect(panel).toHaveAttribute("aria-labelledby", "configuration-settings-tab");

    settingsTab.focus();
    fireEvent.keyDown(settingsTab, { key: "ArrowRight" });
    expect(assetsTab).toHaveFocus();
    expect(assetsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "configuration-assets-tab");
  });

  it("traps focus in the connection dialog, closes on Escape, and restores focus", () => {
    render(<App />);

    const connectionButton = screen.getByRole("button", { name: "資料連線" });
    connectionButton.focus();
    fireEvent.click(connectionButton);

    const dialog = screen.getByRole("dialog", { name: "資料連線" });
    const apiUrl = screen.getByLabelText("API 網址");
    const close = within(dialog).getByRole("button", { name: "關閉" });
    const save = within(dialog).getByRole("button", { name: "儲存" });
    expect(apiUrl).toHaveFocus();
    expect(dialog).toHaveAttribute("aria-describedby", "connection-description");

    save.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(connectionButton).toHaveFocus();
  });

  it("keeps every phone header action in one accessible menu", () => {
    render(<App />);

    const trigger = screen.getByRole("button", { name: "更多操作" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);

    const menu = screen.getByRole("menu", { name: "更多操作" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(within(menu).getByRole("menuitem", { name: "複製分享網址" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "恢復空白預設" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "English" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "資料連線" })).toBeInTheDocument();

    fireEvent.click(within(menu).getByRole("menuitem", { name: "深色模式" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.queryByRole("menu", { name: "更多操作" })).not.toBeInTheDocument();
  });

  it("returns focus to the phone menu trigger when Escape closes the menu", () => {
    render(<App />);

    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);
    const share = within(screen.getByRole("menu")).getByRole("menuitem", { name: "複製分享網址" });
    share.focus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("shows five blank portfolios and six blank asset rows on desktop", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));
    expect(screen.getByLabelText("投資組合名稱 5")).toHaveValue("");
    expect(screen.getAllByPlaceholderText("股票／ETF 代碼")).toHaveLength(6);
    expect(screen.getAllByPlaceholderText("股票／ETF 代碼").every((input) => input.getAttribute("value") === "")).toBe(true);
    expect(screen.getAllByText("0.0%")).toHaveLength(5);
    expect(screen.getAllByText("未使用")).toHaveLength(5);
  });

  it("starts with two portfolios on mobile and can add up to five", () => {
    vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
      matches: query === "(max-width: 760px)",
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }));

    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));
    expect(screen.getByLabelText("投資組合名稱 2")).toBeInTheDocument();
    expect(screen.queryByLabelText("投資組合名稱 3")).not.toBeInTheDocument();

    const add = screen.getByRole("button", { name: /新增比較組合/ });
    fireEvent.click(add);
    fireEvent.click(add);
    fireEvent.click(add);
    expect(screen.getByLabelText("投資組合名稱 5")).toBeInTheDocument();
    expect(add).toBeDisabled();
  });

  it("clears a portfolio column or asset row with one click", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));

    const firstTicker = screen.getAllByPlaceholderText("股票／ETF 代碼")[0];
    fireEvent.change(firstTicker, { target: { value: "VT" } });
    const firstWeight = screen.getByLabelText("VT 權重 1");
    const firstName = screen.getByLabelText("投資組合名稱 1");
    fireEvent.change(firstWeight, { target: { value: "100" } });
    fireEvent.change(firstName, { target: { value: "核心" } });

    fireEvent.click(screen.getByRole("button", { name: "清空此投資組合 1" }));
    expect(firstName).toHaveValue("");
    expect(firstWeight).toHaveValue(null);
    expect(firstTicker).toHaveValue("VT");

    fireEvent.change(firstWeight, { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "清空此資產列 1" }));
    expect(firstTicker).toHaveValue("");
    expect(firstWeight).toHaveValue(null);
  });

  it("shows the exact portfolio total and clears a removed column before it can return", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));

    const fifthName = screen.getByLabelText("投資組合名稱 5");
    const fifthWeight = screen.getByLabelText("資產 1 權重 5");
    fireEvent.change(fifthName, { target: { value: "暫存名稱" } });
    fireEvent.change(fifthWeight, { target: { value: "99.6" } });
    expect(screen.getByLabelText("合計 99.6%")).toHaveTextContent("99.6%");

    fireEvent.click(screen.getByRole("button", { name: /移除最後一組/ }));
    fireEvent.click(screen.getByRole("button", { name: /新增比較組合/ }));
    expect(screen.getByLabelText("投資組合名稱 5")).toHaveValue("");
    expect(screen.getByLabelText("資產 1 權重 5")).toHaveValue(null);
  });

  it("keeps an explicit zero valid in the field but resets edits after a regular reload", () => {
    const firstRender = render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));

    const firstTicker = screen.getAllByPlaceholderText("股票／ETF 代碼")[0];
    const firstWeight = screen.getByLabelText("資產 1 權重 1");
    fireEvent.change(firstTicker, { target: { value: "VT" } });
    fireEvent.change(firstWeight, { target: { value: "0" } });
    expect(firstTicker).toHaveValue("VT");
    expect(firstWeight).toHaveValue(0);

    firstRender.unmount();
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));
    expect(screen.getAllByPlaceholderText("股票／ETF 代碼")[0]).toHaveValue("");
    expect(screen.getByLabelText("資產 1 權重 1")).toHaveValue(null);
  });
});
