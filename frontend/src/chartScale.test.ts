import { describe, expect, it } from "vitest";
import { AUTO_LOG_RATIO, resolveGrowthScale } from "./chartScale";

describe("growth chart scale", () => {
  it("automatically uses log scale for a large positive range", () => {
    const config = resolveGrowthScale([1_000_000, 20_000_000, 140_000_000], "auto");

    expect(config.effectiveMode).toBe("log");
    expect(config.ratio).toBe(140);
    expect(config.logDomain).toEqual([1_000_000, 200_000_000]);
    expect(config.logTicks).toContain(100_000_000);
  });

  it("keeps linear scale when the range is below the automatic threshold", () => {
    const config = resolveGrowthScale([1_000_000, 1_500_000, 2_000_000], "auto");

    expect(config.effectiveMode).toBe("linear");
    expect(config.ratio).toBeLessThan(AUTO_LOG_RATIO);
  });

  it("switches at the documented 20-times automatic threshold", () => {
    expect(resolveGrowthScale([1_000_000, 19_999_999], "auto").effectiveMode).toBe("linear");
    expect(resolveGrowthScale([1_000_000, 20_000_000], "auto").effectiveMode).toBe("log");
  });

  it("honors a manual linear selection for a large range", () => {
    expect(resolveGrowthScale([1, 1_000], "linear").effectiveMode).toBe("linear");
  });

  it("honors a manual log selection for a valid positive range", () => {
    expect(resolveGrowthScale([100, 200], "log").effectiveMode).toBe("log");
  });

  it("falls back to linear when zero or negative values make log invalid", () => {
    const zero = resolveGrowthScale([0, 100, 1_000], "log");
    const negative = resolveGrowthScale([-10, 100, 1_000], "auto");

    expect(zero).toMatchObject({ effectiveMode: "linear", logAvailable: false });
    expect(negative).toMatchObject({ effectiveMode: "linear", logAvailable: false });
  });
});
