export type Trade = {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  quantity: number;
  entry_cost: number;
  exit_cost: number;
  pnl: number;
  return_rate: number;
  holding_days: number;
};

export type EquityPoint = { date: string; equity: number };

export type BacktestResult = {
  backtest_id: string;
  status: string;
  currency: string;
  data_version: string;
  data_start_date: string | null;
  data_end_date: string | null;
  data_points: number;
  benchmark_name: string;
  benchmark_total_return: number;
  benchmark_max_drawdown: number;
  benchmark_equity_curve: EquityPoint[];
  initial_cash: number;
  final_equity: number;
  total_return: number;
  cagr: number;
  max_drawdown: number;
  volatility: number;
  sharpe_ratio: number;
  win_rate: number;
  average_trade_return: number;
  average_holding_days: number;
  total_cost: number;
  trade_count: number;
  trades: Trade[];
  equity_curve: EquityPoint[];
};

export type BacktestExplanation = {
  summary: string;
  strengths: string[];
  risks: string[];
  observations: string[];
  disclaimer: string;
};

export type OHLCVBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type MarketDataFetchResult = {
  provider: string;
  symbol: string;
  adjustment: string;
  data_version: string;
  data_start_date: string;
  data_end_date: string;
  data_points: number;
  data: OHLCVBar[];
};

export type IndicatorReference = {
  type: "INDICATOR";
  indicator: string;
  period?: number | null;
};

export type ValueReference = {
  type: "VALUE";
  value: number;
};

export type Condition = {
  left: IndicatorReference | ValueReference;
  operator: string;
  right: IndicatorReference | ValueReference;
};

export type SingleStockStrategy = {
  strategy_type: "SINGLE_STOCK";
  strategy_name: string;
  market: string;
  universe: { type: string; symbols: string[] };
  period: { start_date: string; end_date: string };
  data: { timeframe: string; adjusted_price: boolean };
  entry_rules: { logic: string; conditions: Condition[] };
  exit_rules: { logic: string; conditions: Condition[] };
  position_sizing: { method: string; value: number | null };
  risk_management: {
    stop_loss: number | null;
    take_profit: number | null;
    maximum_holding_days: number | null;
  };
  execution: { signal_time: string; execution_time: string };
  costs: { commission_rate: number; slippage_rate: number; tax_rate: number };
  capital: { initial_cash: number; currency: string };
  benchmark: string | null;
};

export type RegimeSwitchStrategy = {
  strategy_type: "REGIME_SWITCH";
  strategy_name: string;
  market: string;
  universe: { type: "REGIME_SWITCH"; symbols: [string, string] };
  period: { start_date: string; end_date: string };
  data: { timeframe: string; adjusted_price: boolean };
  default_symbol: string;
  switch_rule: {
    signal_symbol: string;
    condition: Condition;
    target_symbol: string;
  };
  execution: { signal_time: string; execution_time: string };
  costs: { commission_rate: number; slippage_rate: number; tax_rate: number };
  capital: { initial_cash: number; currency: string };
  benchmark: string | null;
};

export type AllocationRebalanceStrategy = {
  strategy_type: "ALLOCATION_REBALANCE";
  strategy_name: string;
  market: string;
  universe: { type: "ALLOCATION_REBALANCE"; symbols: string[] };
  period: { start_date: string; end_date: string };
  data: { timeframe: string; adjusted_price: boolean };
  target_allocations: { symbol: string; weight: number }[];
  rebalance: { frequency: "MONTHLY" };
  execution: { signal_time: string; execution_time: string };
  costs: { commission_rate: number; slippage_rate: number; tax_rate: number };
  capital: { initial_cash: number; currency: string };
  benchmark: string | null;
};

export type Strategy = SingleStockStrategy | RegimeSwitchStrategy | AllocationRebalanceStrategy;

export type StrategyDraft = {
  draft_id: string;
  status: string;
  raw_input: string;
  strategy: Strategy;
  missing_fields: string[];
  assumptions: string[];
  warnings: string[];
  needs_confirmation: boolean;
  needs_clarification: boolean;
};

export type StrategyVersion = {
  strategy_id: string;
  version: number;
  draft_id: string;
  confirmed_at: string;
  strategy: Strategy;
};

export type StrategyLibraryItem = {
  strategy_id: string;
  latest_version: number;
  confirmed_at: string;
  strategy: Strategy;
};

export type BacktestRunSummary = {
  backtest_id: string;
  status: string;
  strategy_version: number | null;
  currency: string;
  created_at: string;
  data_version: string;
  data_start_date: string | null;
  data_end_date: string | null;
  data_points: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  final_equity: number;
  trade_count: number;
};
