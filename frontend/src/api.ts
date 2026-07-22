import type {
  ApiConnection,
  AssetSearchResult,
  BacktestRequest,
  BacktestResponse,
} from "./types";

export async function checkHealth(connection: ApiConnection): Promise<boolean> {
  const base = cleanBase(connection.baseUrl);
  const response = await fetch(`${base}/health`, {
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) return false;
  const auth = await fetch(`${base}/api/v1/auth/check`, {
    headers: authHeaders(connection),
    signal: AbortSignal.timeout(10_000),
  });
  return auth.ok;
}

export async function searchAssets(
  connection: ApiConnection,
  query: string,
): Promise<AssetSearchResult[]> {
  const response = await fetch(
    `${cleanBase(connection.baseUrl)}/api/v1/assets/search?q=${encodeURIComponent(query)}`,
    { headers: authHeaders(connection), signal: AbortSignal.timeout(20_000) },
  );
  return parseResponse<AssetSearchResult[]>(response);
}

export async function runBacktest(
  connection: ApiConnection,
  request: BacktestRequest,
): Promise<BacktestResponse> {
  const response = await fetch(`${cleanBase(connection.baseUrl)}/api/v1/backtests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(connection) },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(120_000),
  });
  return parseResponse<BacktestResponse>(response);
}

function cleanBase(value: string): string {
  return value.trim().replace(/\/$/, "");
}

function authHeaders(connection: ApiConnection): Record<string, string> {
  return connection.accessKey ? { "X-Backtest-Key": connection.accessKey } : {};
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({ detail: response.statusText }));
  if (!response.ok) {
    const detail = payload?.detail;
    if (Array.isArray(detail)) {
      throw new Error(detail.map((item) => item.msg || JSON.stringify(item)).join("；"));
    }
    throw new Error(typeof detail === "string" ? detail : `HTTP ${response.status}`);
  }
  return payload as T;
}
