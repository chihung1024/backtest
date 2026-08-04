import { describe, expect, it } from "vitest";
import styles from "./styles.css?raw";

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

describe("Retirement page UI quality CSS contracts", () => {
  it("keeps destination links large enough for touch and keyboard users", () => {
    const actions = rule(".retirement-actions a");
    expect(actions).toMatch(/min-height:\s*48px/);
    expect(actions).toMatch(/display:\s*inline-flex/);
    expect(actions).toMatch(/align-items:\s*center/);
    expect(actions).toMatch(/justify-content:\s*center/);
    expect(rule(":focus-visible")).toMatch(/outline:\s*3px solid/);
  });

  it("keeps safe areas and the 320px to 390px mobile layout readable", () => {
    expect(styles).toContain("env(safe-area-inset-left)");
    expect(styles).toContain("env(safe-area-inset-right)");
    expect(styles).toContain("env(safe-area-inset-bottom)");
    expect(styles).toContain("@media (max-width: 760px)");
    expect(styles).toMatch(/@media \(max-width: 760px\)[\s\S]*\.retirement-grid\s*\{[^}]*grid-template-columns:\s*1fr/);
    expect(styles).toMatch(/@media \(max-width: 760px\)[\s\S]*\.retirement-actions a\s*\{[^}]*width:\s*100%/);
    expect(rule("html")).toMatch(/min-width:\s*320px/);
  });

  it("preserves reduced-motion, increased-contrast, and forced-color fallbacks", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("@media (prefers-contrast: more)");
    expect(styles).toContain("@media (forced-colors: active)");
  });

  it("keeps retirement text colors above WCAG AA normal-text contrast", () => {
    const root = styles.match(/:root\s*\{([^}]*)\}/s);
    expect(root).not.toBeNull();
    const tokens = themeTokens(root?.[1] ?? "");
    const pairs = [
      [tokens.ink, tokens.surface],
      [tokens.muted, tokens.surface],
      [tokens["accent-dark"], tokens.surface],
      [tokens.warning, tokens["warning-soft"]],
    ];

    for (const [foreground, background] of pairs) {
      expect(contrast(foreground, background), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });
});
