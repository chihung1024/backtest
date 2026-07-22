import { beforeEach, describe, expect, it } from "vitest";
import { freshDefaultState } from "./defaults";
import { createShareUrl, loadConnection, loadModel, saveConnection } from "./storage";

describe("browser persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = "";
  });

  it("starts from blank defaults and removes stale saved models on a regular load", () => {
    const stale = freshDefaultState(3);
    stale.portfolioNames[0] = "Old saved model";
    stale.assets[0].symbol = "VT";
    stale.assets[0].weights[0] = 100;
    localStorage.setItem("portfolio-lab:model:v2", JSON.stringify(stale));

    const loaded = loadModel();

    expect(loaded.portfolioCount).toBe(5);
    expect(loaded.portfolioNames).toEqual(["", "", "", "", ""]);
    expect(loaded.assets.every((asset) => asset.symbol === "")).toBe(true);
    expect(localStorage.getItem("portfolio-lab:model:v2")).toBeNull();
  });

  it("round-trips a unicode model through a share URL", () => {
    const model = freshDefaultState();
    model.portfolioNames[0] = "台灣核心策略";
    model.assets[0].symbol = "0050.TW";
    model.assets[0].weights[0] = 100;
    const url = createShareUrl(model);
    window.location.hash = new URL(url).hash;

    expect(loadModel().portfolioNames[0]).toBe("台灣核心策略");
    expect(loadModel().assets[0].weights[0]).toBe(100);
  });

  it("does not restore legacy models and keeps daily TWD defaults", () => {
    const legacy = freshDefaultState();
    localStorage.setItem(
      "portfolio-lab:model:v1",
      JSON.stringify({ ...legacy, baseCurrency: "USD", outputFrequency: "monthly" }),
    );

    const restored = loadModel();

    expect(restored.baseCurrency).toBe("TWD");
    expect(restored.outputFrequency).toBe("daily");
    expect(restored.assets.every((asset) => asset.symbol === "")).toBe(true);
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
