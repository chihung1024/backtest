import { describe, expect, it } from "vitest";
import { resolveDateAxis } from "./dateAxis";

describe("dynamic date axis", () => {
  it("shows each year once for a multi-year backtest", () => {
    const axis = resolveDateAxis([
      "2023-01-03",
      "2023-06-30",
      "2024-01-02",
      "2024-12-31",
      "2025-01-02",
      "2025-12-31",
      "2026-01-02",
      "2026-07-20",
    ], "zh-TW");

    expect(axis.granularity).toBe("year");
    expect(axis.ticks.map(axis.formatTick)).toEqual(["2023年", "2024年", "2025年", "2026年"]);
  });

  it("uses year-month labels and limits their density for a medium range", () => {
    const dates = Array.from({ length: 18 }, (_, index) => {
      const date = new Date(Date.UTC(2024, index, 1));
      return date.toISOString().slice(0, 10);
    });
    const axis = resolveDateAxis(dates, "en", 7);

    expect(axis.granularity).toBe("month");
    expect(axis.ticks.length).toBeLessThanOrEqual(7);
    expect(axis.formatTick(axis.ticks[0])).toMatch(/2024/);
    expect(axis.formatTick(axis.ticks.at(-1) ?? "")).toMatch(/2025/);
  });

  it("uses month-day labels for a short daily range", () => {
    const axis = resolveDateAxis([
      "2026-07-01",
      "2026-07-02",
      "2026-07-03",
      "2026-07-04",
      "2026-07-05",
    ], "en");

    expect(axis.granularity).toBe("day");
    expect(axis.ticks.map(axis.formatTick)).toEqual(["7/1", "7/2", "7/3", "7/4", "7/5"]);
  });

  it("ignores invalid and duplicate dates", () => {
    const axis = resolveDateAxis(["bad", "2026-01-02", "2026-01-02"], "en");

    expect(axis.ticks).toEqual(["2026-01-02"]);
  });
});
