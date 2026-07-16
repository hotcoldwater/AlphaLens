import type { BacktestResult } from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getBacktest(backtestId: string): Promise<BacktestResult> {
  const response = await fetch(`${apiBase}/api/v1/backtests/${encodeURIComponent(backtestId)}/result`);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.message ?? "백테스트 결과를 불러오지 못했습니다.");
  }
  return response.json() as Promise<BacktestResult>;
}
