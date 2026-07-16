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
