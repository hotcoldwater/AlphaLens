import type {
  BacktestExplanation,
  BacktestResult,
  BacktestRunSummary,
  MarketDataFetchResult,
  OHLCVBar,
  Strategy,
  StrategyDraft,
  StrategyLibraryItem,
  StrategyVersion,
} from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getBacktest(backtestId: string): Promise<BacktestResult> {
  const response = await fetch(
    `${apiBase}/api/v1/backtests/${encodeURIComponent(backtestId)}/result`,
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.message ?? "백테스트 결과를 불러오지 못했습니다.");
  }
  return response.json() as Promise<BacktestResult>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.message ?? payload?.detail ?? "요청을 처리하지 못했습니다.",
    );
  }
  return response.json() as Promise<T>;
}

export function parseStrategy(rawInput: string): Promise<StrategyDraft> {
  return request("/api/v1/strategy-drafts/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_input: rawInput }),
  });
}

export function confirmDraft(draftId: string): Promise<unknown> {
  return request(
    `/api/v1/strategy-drafts/${encodeURIComponent(draftId)}/confirm`,
    { method: "POST" },
  );
}

export function updateDraft(
  draftId: string,
  strategy: Strategy,
): Promise<StrategyDraft> {
  return request(`/api/v1/strategy-drafts/${encodeURIComponent(draftId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ strategy }),
  });
}

export function runDraftBacktest(
  draftId: string,
  requestBody: { data?: OHLCVBar[]; data_by_symbol?: Record<string, OHLCVBar[]> },
): Promise<BacktestResult> {
  return request(
    `/api/v1/strategy-drafts/${encodeURIComponent(draftId)}/backtest`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    },
  );
}

export function fetchDailyOhlcv(requestBody: {
  provider: "FMP" | "KRX";
  symbol: string;
  start_date: string;
  end_date: string;
  adjusted_price: boolean;
}): Promise<MarketDataFetchResult> {
  return request("/api/v1/market-data/daily-ohlcv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });
}

export function explainBacktest(
  backtestId: string,
): Promise<BacktestExplanation> {
  return request(
    `/api/v1/backtests/${encodeURIComponent(backtestId)}/explanation`,
    { method: "POST" },
  );
}

export async function getStrategyLibrary(): Promise<StrategyLibraryItem[]> {
  const response = await request<{ strategies: StrategyLibraryItem[] }>(
    "/api/v1/strategies",
  );
  return response.strategies;
}

export async function getStrategyVersions(
  strategyId: string,
): Promise<StrategyVersion[]> {
  const response = await request<{ versions: StrategyVersion[] }>(
    `/api/v1/strategies/${encodeURIComponent(strategyId)}/versions`,
  );
  return response.versions;
}

export function cloneStrategyVersion(
  strategyId: string,
  version: number,
): Promise<StrategyDraft> {
  return request(
    `/api/v1/strategies/${encodeURIComponent(strategyId)}/versions/${version}/clone`,
    { method: "POST" },
  );
}

export async function getStrategyBacktests(
  strategyId: string,
): Promise<BacktestRunSummary[]> {
  const response = await request<{ runs: BacktestRunSummary[] }>(
    `/api/v1/strategies/${encodeURIComponent(strategyId)}/backtests`,
  );
  return response.runs;
}
