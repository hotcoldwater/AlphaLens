import type { BacktestResult, OHLCVBar, StrategyDraft } from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getBacktest(backtestId: string): Promise<BacktestResult> {
  const response = await fetch(`${apiBase}/api/v1/backtests/${encodeURIComponent(backtestId)}/result`);
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
    throw new Error(payload?.message ?? payload?.detail ?? "요청을 처리하지 못했습니다.");
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
  return request(`/api/v1/strategy-drafts/${encodeURIComponent(draftId)}/confirm`, { method: "POST" });
}

export function runDraftBacktest(draftId: string, data: OHLCVBar[]): Promise<BacktestResult> {
  return request(`/api/v1/strategy-drafts/${encodeURIComponent(draftId)}/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
}
