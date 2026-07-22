import { describe, expect, it } from "vitest";
import styles from "./styles.css?raw";
import { chartColors } from "./utils";

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = styles.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, "s"));
  expect(match, `Missing CSS rule: ${selector}`).not.toBeNull();
  return match?.[1] ?? "";
}

function themeTokens(block: string): Record<string, string> {
  return Object.fromEntries(
    Array.from(block.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/gi), (match) => [match[1], match[2]]),
  );
}

function luminance(hex: string): number {
  const channels = hex.slice(1).match(/.{2}/g)?.map((channel) => parseInt(channel, 16) / 255) ?? [];
  const linear = channels.map((channel) => channel <= 0.04045
    ? channel / 12.92
    : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(foreground: string, background: string): number {
  const a = luminance(foreground);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

describe("UI quality CSS contracts", () => {
  it("centers the iOS date value on both axes without pixel offsets", () => {
    const valueRule = rule(".date-input--centered::-webkit-date-and-time-value");
    const editRule = rule(".date-input--centered::-webkit-datetime-edit");

    for (const dateRule of [valueRule, editRule]) {
      expect(dateRule).toMatch(/height:\s*100%/);
      expect(dateRule).toMatch(/align-items:\s*center/);
      expect(dateRule).toMatch(/justify-content:\s*center/);
      expect(dateRule).toMatch(/text-align:\s*center/);
      expect(dateRule).not.toMatch(/transform|translate|top:/);
    }
  });

  it("keeps mobile controls, safe areas, and sticky layers readable", () => {
    expect(rule(".button")).toMatch(/min-height:\s*44px/);
    expect(styles).toMatch(/input,\s*select,\s*\.toggle\s*\{[^}]*min-height:\s*48px/s);
    expect(styles).toMatch(/\.mobile-status,\s*\.mobile-menu-trigger\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/s);
    expect(styles).toMatch(/\.modal \.icon-button\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/s);
    expect(styles).toMatch(/\.tooltip\s*\{[^}]*width:\s*44px[^}]*height:\s*44px/s);
    expect(styles).toContain("env(safe-area-inset-bottom)");
    expect(styles).toContain("scroll-margin-bottom");
    expect(styles).toMatch(/\.app-header\s*\{[^}]*background:[^}]*98%/s);
    expect(styles).toMatch(/\.run-bar\s*\{[^}]*background:[^}]*98%/s);
  });

  it("preserves reduced-motion, increased-contrast, and forced-color fallbacks", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("@media (prefers-contrast: more)");
    expect(styles).toContain("@media (forced-colors: active)");
  });

  it("keeps semantic text colors above the WCAG AA normal-text contrast threshold", () => {
    const blocks = Array.from(styles.matchAll(/:root(?:\[data-theme="dark"\])?\s*\{([^}]*)\}/g));
    expect(blocks).toHaveLength(2);
    const light = themeTokens(blocks[0][1]);
    const dark = themeTokens(blocks[1][1]);

    const pairs = [
      [light.primary, light.surface],
      [light.muted, light.surface],
      [light.subtle, light["surface-2"]],
      [light.danger, light["danger-soft"]],
      [light.warning, light["warning-soft"]],
      [light.success, light["primary-soft"]],
      [dark.primary, dark.surface],
      [dark.muted, dark.surface],
      [dark.subtle, dark.surface],
      [dark.danger, dark["danger-soft"]],
      [dark.warning, dark["warning-soft"]],
      [dark.success, dark.surface],
    ];

    for (const [foreground, background] of pairs) {
      expect(contrast(foreground, background), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }

    for (const color of chartColors) {
      expect(contrast(color, light.surface), `${color} chart series on light surface`).toBeGreaterThanOrEqual(3);
      expect(contrast(color, dark["surface-2"]), `${color} chart series on dark surface`).toBeGreaterThanOrEqual(3);
    }
  });
});
