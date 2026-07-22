import { fireEvent, render, screen } from "@testing-library/react";
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
