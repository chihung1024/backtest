import { beforeEach, describe, expect, it } from "vitest";
import { freshDefaultState } from "./defaults";
import { createShareUrl, loadConnection, loadModel, saveConnection, saveModel } from "./storage";

describe("browser persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = "";
  });

  it("restores saved portfolio names instead of replacing them with defaults", () => {
    const model = freshDefaultState();
    model.portfolioNames = ["Core", "Income", "Defensive"];
    saveModel(model);

    expect(loadModel().portfolioNames).toEqual(["Core", "Income", "Defensive"]);
  });

  it("round-trips a unicode model through a share URL", () => {
    const model = freshDefaultState();
    model.portfolioNames[0] = "台灣核心策略";
    const url = createShareUrl(model);
    window.location.hash = new URL(url).hash;

    expect(loadModel().portfolioNames[0]).toBe("台灣核心策略");
  });

  it("migrates legacy models to daily TWD valuation", () => {
    const legacy = freshDefaultState();
    localStorage.setItem(
      "portfolio-lab:model:v1",
      JSON.stringify({ ...legacy, baseCurrency: "USD", outputFrequency: "monthly" }),
    );

    const restored = loadModel();

    expect(restored.baseCurrency).toBe("TWD");
    expect(restored.outputFrequency).toBe("daily");
  });

  it("stores the API key locally but never in a shared model URL", () => {
    saveConnection({ baseUrl: "https://api.example.test/", accessKey: "very-secret" });
    expect(loadConnection()).toEqual({
      baseUrl: "https://api.example.test",
      accessKey: "very-secret",
    });

    expect(createShareUrl(freshDefaultState())).not.toContain("very-secret");
  });
});
