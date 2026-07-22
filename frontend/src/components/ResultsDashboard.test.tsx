import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { translator } from "../i18n";
import type { BacktestResponse, PortfolioResult } from "../types";
import { ResultsDashboard } from "./ResultsDashboard";

function result(name: string, values: number[]): PortfolioResult {
  return {
    name,
    display_name: `${name} · VT 100%`,
    metrics: { final_balance: values.at(-1) ?? 0 },
    series: values.map((value, index) => ({
      date: `2020-01-${String(index + 1).padStart(2, "0")}`,
      value,
      return_index: value,
      drawdown: 0,
      cumulative_income: 0,
    })),
    annual_returns: {},
    monthly_returns: [],
    income_by_year: {},
    target_allocation: { VT: 1 },
    final_allocation: { VT: 1 },
    factor_analysis: null,
    style_analysis: null,
    regime_analysis: null,
  };
}

function response(values: number[]): BacktestResponse {
  return {
    request_id: "test",
    generated_at: "2020-01-02T00:00:00Z",
    data_as_of: "2020-01-02",
    effective_start: "2020-01-01",
    effective_end: "2020-01-02",
    base_currency: "TWD",
    results: [result("投資組合 1", values)],
    benchmark: null,
    assets: [],
    warnings: [],
  };
}

describe("ResultsDashboard growth scale", () => {
  it("has no automatically detectable accessibility violations across visible result tabs", async () => {
    const { container } = render(
      <ResultsDashboard
        response={response([1_000_000, 1_100_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    for (const label of ["總覽", "資產成長", "回撤", "年度報酬", "月度報酬", "期末配置"]) {
      fireEvent.click(screen.getByRole("tab", { name: label }));
      const audit = await axe.run(container, {
        rules: { "color-contrast": { enabled: false } },
      });
      expect(audit.violations, label).toEqual([]);
    }
  });

  it("links result tabs to one panel and supports keyboard navigation", () => {
    render(
      <ResultsDashboard
        response={response([1_000_000, 1_100_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    const overview = screen.getByRole("tab", { name: "總覽" });
    const growth = screen.getByRole("tab", { name: "資產成長" });
    expect(overview).toHaveAttribute("aria-controls", "result-panel");
    expect(overview).toHaveAttribute("tabindex", "0");
    expect(growth).toHaveAttribute("tabindex", "-1");

    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(growth).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "result-growth-tab");
    expect(screen.getByRole("img", { name: "資產成長" })).toBeInTheDocument();
  });

  it("uses log scale by default and lets the user override it", () => {
    render(
      <ResultsDashboard
        response={response([1_000_000, 20_000_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "資產成長" }));

    expect(screen.getByRole("button", { name: "對數" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("對數尺度");

    fireEvent.click(screen.getByRole("button", { name: "線性" }));
    expect(screen.getByRole("button", { name: "線性" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("線性尺度");
  });

  it("disables log scale when the series includes zero", () => {
    render(
      <ResultsDashboard
        response={response([0, 1_000_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "資產成長" }));

    expect(screen.getByRole("button", { name: "對數" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "線性" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("資料含 0 或負值");
  });

  it("keeps long series labels outside the fixed chart frame", () => {
    const { container } = render(
      <ResultsDashboard
        response={response([1_000_000, 1_100_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "資產成長" }));

    expect(container.querySelector(".chart-legend")).toHaveTextContent("投資組合 1 · VT 100%");
    expect(container.querySelector(".chart-frame .chart-legend")).not.toBeInTheDocument();
  });

  it("shows the allocation-aware name throughout the results", () => {
    render(
      <ResultsDashboard
        response={response([1_000_000, 1_100_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    expect(screen.getAllByText("投資組合 1 · VT 100%").length).toBeGreaterThan(1);
  });
});
