import { describe, expect, it } from "vitest";
import { freshDefaultState } from "./defaults";
import { buildRequest, validateModel } from "./utils";

describe("portfolio request builder", () => {
  it("only sends completed portfolios and active assets", () => {
    const model = freshDefaultState(5);
    model.portfolioNames[0] = "Core";
    model.portfolioNames[2] = "Taiwan";
    model.assets[0].symbol = "vt";
    model.assets[1].symbol = "BND";
    model.assets[2].symbol = "0050.tw";
    model.assets[0].weights = [80, "", "", "", ""];
    model.assets[1].weights = [20, 0, "", "", ""];
    model.assets[2].weights = ["", "", 100, "", ""];
    const request = buildRequest(model);
    expect(request.portfolios).toHaveLength(2);
    expect(request.portfolios[0].assets).toEqual([
      { symbol: "VT", weight: 80 },
      { symbol: "BND", weight: 20 },
    ]);
    expect(request.portfolios[1]).toEqual({
      name: "Taiwan",
      assets: [{ symbol: "0050.TW", weight: 100 }],
    });
    expect(request.base_currency).toBe("TWD");
    expect(request.output_frequency).toBe("daily");
  });

  it("reports incomplete weights", () => {
    const model = freshDefaultState(5);
    model.assets[0].symbol = "VT";
    model.assets[0].weights[0] = 70;
    const errors = validateModel(model);
    expect(errors.some((error) => error.includes("70.00%"))).toBe(true);
  });

  it("accepts blank and zero portfolios when another portfolio is complete", () => {
    const model = freshDefaultState(5);
    model.assets[0].symbol = "VT";
    model.assets[0].weights = [100, 0, "", "", ""];

    expect(validateModel(model)).toEqual([]);
    expect(buildRequest(model).portfolios).toHaveLength(1);
  });

  it("requires at least one completed portfolio", () => {
    const errors = validateModel(freshDefaultState(5));
    expect(errors).toContain("至少需要一組權重合計 100% 的投資組合");
  });

  it("rejects a positive weight without a ticker", () => {
    const model = freshDefaultState(5);
    model.assets[0].weights[0] = 100;

    expect(validateModel(model).some((error) => error.includes("尚未填寫資產代碼"))).toBe(true);
  });

  it("rejects duplicate symbols inside a portfolio", () => {
    const model = freshDefaultState(5);
    model.assets[0].symbol = "VT";
    model.assets[1].symbol = "vt";
    model.assets[0].weights[0] = 50;
    model.assets[1].weights[0] = 50;
    const errors = validateModel(model);
    expect(errors.some((error) => error.includes("重複代碼"))).toBe(true);
  });
});
