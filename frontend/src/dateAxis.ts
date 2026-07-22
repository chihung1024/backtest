export type DateTickGranularity = "day" | "month" | "year";

export interface DateAxisConfig {
  ticks: string[];
  granularity: DateTickGranularity;
  formatTick: (value: string) => string;
}

const DAY_MS = 86_400_000;
const SHORT_RANGE_DAYS = 92;
const MONTH_RANGE_DAYS = 731;
const DEFAULT_MAX_TICKS = 9;

export function resolveDateAxis(
  values: string[],
  locale: string,
  maxTicks = DEFAULT_MAX_TICKS,
): DateAxisConfig {
  const dates = Array.from(new Set(values.filter(isIsoDate))).sort();
  const first = dates[0];
  const last = dates.at(-1);
  if (!first || !last) {
    return { ticks: [], granularity: "year", formatTick: (value) => value };
  }

  const spanDays = Math.max((parseDate(last).getTime() - parseDate(first).getTime()) / DAY_MS, 0);
  const granularity: DateTickGranularity = spanDays <= SHORT_RANGE_DAYS
    ? "day"
    : spanDays <= MONTH_RANGE_DAYS
      ? "month"
      : "year";
  const candidates = firstDatePerBucket(dates, granularity);
  const ticks = limitTicks(candidates, Math.max(Math.floor(maxTicks), 2));
  const crossesYear = first.slice(0, 4) !== last.slice(0, 4);
  const formatter = new Intl.DateTimeFormat(locale, dateFormat(granularity, crossesYear, spanDays));

  return {
    ticks,
    granularity,
    formatTick: (value) => isIsoDate(value) ? formatter.format(parseDate(value)) : value,
  };
}

function firstDatePerBucket(
  dates: string[],
  granularity: DateTickGranularity,
): string[] {
  if (granularity === "day") return dates;
  const length = granularity === "month" ? 7 : 4;
  const firstByBucket = new Map<string, string>();
  dates.forEach((date) => {
    const bucket = date.slice(0, length);
    if (!firstByBucket.has(bucket)) firstByBucket.set(bucket, date);
  });
  return Array.from(firstByBucket.values());
}

function limitTicks(values: string[], maxTicks: number): string[] {
  if (values.length <= maxTicks) return values;
  const step = Math.ceil(values.length / maxTicks);
  const selected = values.filter((_, index) => index % step === 0);
  const last = values.at(-1);
  if (last && selected.at(-1) !== last) selected.push(last);
  return selected;
}

function dateFormat(
  granularity: DateTickGranularity,
  crossesYear: boolean,
  spanDays: number,
): Intl.DateTimeFormatOptions {
  const timeZone = "UTC";
  if (granularity === "year") return { year: "numeric", timeZone };
  if (granularity === "month") return { year: "numeric", month: "2-digit", timeZone };
  return crossesYear || spanDays > 31
    ? { year: "2-digit", month: "numeric", day: "numeric", timeZone }
    : { month: "numeric", day: "numeric", timeZone };
}

function isIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(parseDate(value).getTime());
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}
