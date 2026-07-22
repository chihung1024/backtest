import { describe, expect, it } from "vitest";
import { freshDefaultState } from "./defaults";
import { buildRequest, validateModel } from "./utils";

describe("portfolio request builder", () => {
  it("only sends active assets and portfolios", () => {
    const model = freshDefaultState();
    model.portfolioCount = 2;
    model.portfolioNames = ["Core", "Growth", "Defensive"];
    model.assets[0].weights = [80, 25, 0];
    model.assets[1].weights = [20, 75, 0];
    const request = buildRequest(model);
    expect(request.portfolios).toHaveLength(2);
    expect(request.portfolios[0].assets).toEqual([
      { symbol: "VT", weight: 80 },
      { symbol: "BND", weight: 20 },
    ]);
    expect(request.portfolios[1].assets[0]).toEqual({ symbol: "VT", weight: 25 });
    expect(request.base_currency).toBe("TWD");
  });

  it("reports incomplete weights", () => {
    const model = freshDefaultState();
    model.assets[0].weights[0] = 50;
    const errors = validateModel(model);
    expect(errors.some((error) => error.includes("70.00%"))).toBe(true);
  });

  it("rejects duplicate symbols inside a portfolio", () => {
    const model = freshDefaultState();
    model.assets[1].symbol = "VT";
    const errors = validateModel(model);
    expect(errors.some((error) => error.includes("重複代碼"))).toBe(true);
  });
});
