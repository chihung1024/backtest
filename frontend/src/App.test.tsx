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
    vi.unstubAllGlobals();
  });

  it("renders the configuration workflow", () => {
    render(<App />);
    expect(screen.getAllByText("投資組合回測實驗室").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /投資組合資產/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /執行回測/ })).toBeInTheDocument();
  });

  it("switches to the portfolio assets grid", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: /投資組合資產/ }));
    expect(screen.getAllByDisplayValue("VT")).toHaveLength(2);
    expect(screen.getByDisplayValue("BND")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
  });
});
