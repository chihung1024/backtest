export type GrowthScaleMode = "auto" | "linear" | "log";
export type EffectiveGrowthScale = Exclude<GrowthScaleMode, "auto">;

export const AUTO_LOG_RATIO = 20;

export interface GrowthScaleConfig {
  effectiveMode: EffectiveGrowthScale;
  logAvailable: boolean;
  ratio: number;
  logDomain: [number, number] | null;
  logTicks: number[];
}

export function resolveGrowthScale(
  values: number[],
  requestedMode: GrowthScaleMode,
): GrowthScaleConfig {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return linearConfig(false, 1);

  let minimum = finite[0];
  let maximum = finite[0];
  finite.forEach((value) => {
    minimum = Math.min(minimum, value);
    maximum = Math.max(maximum, value);
  });
  const logAvailable = minimum > 0 && maximum > minimum;
  const ratio = logAvailable ? maximum / minimum : 1;
  const useLog = logAvailable && (
    requestedMode === "log" || (requestedMode === "auto" && ratio >= AUTO_LOG_RATIO)
  );

  if (!useLog) return linearConfig(logAvailable, ratio);

  const logDomain: [number, number] = [niceLogFloor(minimum), niceLogCeil(maximum)];
  if (logDomain[0] === logDomain[1]) logDomain[1] *= 10;
  return {
    effectiveMode: "log",
    logAvailable,
    ratio,
    logDomain,
    logTicks: createLogTicks(logDomain),
  };
}

function linearConfig(logAvailable: boolean, ratio: number): GrowthScaleConfig {
  return {
    effectiveMode: "linear",
    logAvailable,
    ratio,
    logDomain: null,
    logTicks: [],
  };
}

function niceLogFloor(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  if (normalized >= 5) return 5 * magnitude;
  if (normalized >= 2) return 2 * magnitude;
  return magnitude;
}

function niceLogCeil(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  if (normalized <= 1) return magnitude;
  if (normalized <= 2) return 2 * magnitude;
  if (normalized <= 5) return 5 * magnitude;
  return 10 * magnitude;
}

function createLogTicks([minimum, maximum]: [number, number]): number[] {
  const candidates: number[] = [];
  const firstExponent = Math.floor(Math.log10(minimum));
  const lastExponent = Math.ceil(Math.log10(maximum));

  for (let exponent = firstExponent; exponent <= lastExponent; exponent += 1) {
    const magnitude = 10 ** exponent;
    [1, 2, 5].forEach((factor) => {
      const tick = factor * magnitude;
      if (tick >= minimum && tick <= maximum) candidates.push(tick);
    });
  }

  if (candidates.length <= 8) return candidates;
  const powers = candidates.filter((tick) => isPowerOfTen(tick));
  const reduced = Array.from(new Set([minimum, ...powers, maximum])).sort((a, b) => a - b);
  if (reduced.length <= 8) return reduced;

  return Array.from({ length: 8 }, (_, index) => {
    const candidateIndex = Math.round(index * (reduced.length - 1) / 7);
    return reduced[candidateIndex];
  }).filter((tick, index, ticks) => tick !== ticks[index - 1]);
}

function isPowerOfTen(value: number): boolean {
  const exponent = Math.log10(value);
  return Math.abs(exponent - Math.round(exponent)) < 1e-10;
}
