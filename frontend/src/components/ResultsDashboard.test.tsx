import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { translator } from "../i18n";
import type { BacktestResponse, PortfolioResult } from "../types";
import { ResultsDashboard } from "./ResultsDashboard";

function result(name: string, values: number[]): PortfolioResult {
  return {
    name,
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
  it("shows the automatic log decision and lets the user override it", () => {
    render(
      <ResultsDashboard
        response={response([1_000_000, 20_000_000])}
        t={translator("zh-TW")}
        locale="zh-TW"
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "資產成長" }));

    expect(screen.getByRole("button", { name: "自動" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("目前採對數尺度");

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
    expect(screen.getByRole("status")).toHaveTextContent("資料含 0 或負值");
  });
});
