import { FormEvent, useState } from "react";
import { getBacktest } from "./api";
import type { BacktestResult, EquityPoint } from "./types";

const won = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("ko-KR", { style: "percent", maximumFractionDigits: 1 });

function formatWon(value: number) {
  return `${won.format(value)} KRW`;
}

function Chart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return <div className="empty-chart">자산곡선 데이터가 없습니다.</div>;
  const values = points.map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const path = points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 88 - ((point.equity - min) / span) * 72;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const last = points.at(-1)!;
  return (
    <div className="chart-wrap">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="전략 자산곡선">
        <defs>
          <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#d97842" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#d97842" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L100,100 L0,100 Z`} fill="url(#area)" />
        <path d={path} fill="none" stroke="#d97842" strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="chart-meta"><span>{points[0].date}</span><strong>{formatWon(last.equity)}</strong><span>{last.date}</span></div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warm" | "cool" }) {
  return <article className={`metric ${tone ?? ""}`}><span>{label}</span><strong>{value}</strong></article>;
}

function ResultView({ result }: { result: BacktestResult }) {
  const returnTone = result.total_return >= 0 ? "warm" : "cool";
  return (
    <main className="result-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">ALPHALENS / BACKTEST RESULT</p>
          <h1>전략이 남긴<br />시간의 궤적.</h1>
          <p className="hero-copy">확정된 규칙으로 계산된 결과입니다. AI 해석과 수익률 계산은 분리되어 있습니다.</p>
        </div>
        <div className="run-stamp"><span>RUN STATUS</span><strong>{result.status}</strong><small>{result.backtest_id}</small></div>
      </section>

      <section className="metrics-grid">
        <Metric label="누적 수익률" value={percent.format(result.total_return)} tone={returnTone} />
        <Metric label="최종 자산" value={formatWon(result.final_equity)} />
        <Metric label="CAGR" value={percent.format(result.cagr)} />
        <Metric label="최대 낙폭" value={percent.format(result.max_drawdown)} tone="cool" />
      </section>

      <section className="content-grid">
        <article className="panel equity-panel"><div className="panel-head"><div><span className="panel-kicker">EQUITY CURVE</span><h2>자산곡선</h2></div><span>초기 자산 {formatWon(result.initial_cash)}</span></div><Chart points={result.equity_curve} /></article>
        <article className="panel profile-panel"><span className="panel-kicker">STRATEGY PROFILE</span><h2>성과의 질</h2><dl><div><dt>샤프지수</dt><dd>{result.sharpe_ratio.toFixed(2)}</dd></div><div><dt>연환산 변동성</dt><dd>{percent.format(result.volatility)}</dd></div><div><dt>승률</dt><dd>{percent.format(result.win_rate)}</dd></div><div><dt>평균 보유기간</dt><dd>{result.average_holding_days.toFixed(1)}일</dd></div><div><dt>총 거래비용</dt><dd>{formatWon(result.total_cost)}</dd></div><div><dt>거래 횟수</dt><dd>{result.trade_count}회</dd></div></dl></article>
      </section>

      <section className="panel trades-panel"><div className="panel-head"><div><span className="panel-kicker">TRADE LEDGER</span><h2>거래 내역</h2></div><span>{result.trades.length}개의 완료 거래</span></div><div className="table-wrap"><table><thead><tr><th>진입</th><th>청산</th><th>수량</th><th>보유</th><th>손익</th><th>수익률</th></tr></thead><tbody>{result.trades.map((trade) => <tr key={`${trade.entry_date}-${trade.exit_date}`}><td>{trade.entry_date}<small>{formatWon(trade.entry_price)}</small></td><td>{trade.exit_date}<small>{formatWon(trade.exit_price)}</small></td><td>{won.format(trade.quantity)}</td><td>{trade.holding_days}일</td><td className={trade.pnl >= 0 ? "positive" : "negative"}>{formatWon(trade.pnl)}</td><td className={trade.return_rate >= 0 ? "positive" : "negative"}>{percent.format(trade.return_rate)}</td></tr>)}</tbody></table></div></section>
    </main>
  );
}

export default function App() {
  const [backtestId, setBacktestId] = useState(new URLSearchParams(window.location.search).get("backtestId") ?? "");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function load(event: FormEvent) {
    event.preventDefault();
    if (!backtestId.trim()) return;
    setLoading(true); setError("");
    try { setResult(await getBacktest(backtestId.trim())); }
    catch (caught) { setResult(null); setError(caught instanceof Error ? caught.message : "알 수 없는 오류가 발생했습니다."); }
    finally { setLoading(false); }
  }
  if (result) return <ResultView result={result} />;
  return <main className="landing"><section className="landing-card"><p className="eyebrow">ALPHALENS / RESULT DESK</p><h1>검증된 결과만<br />한눈에.</h1><p>백테스트 실행 ID를 입력하면 성과, 자산곡선, 거래 내역을 불러옵니다.</p><form onSubmit={load}><label htmlFor="backtest-id">BACKTEST ID</label><div><input id="backtest-id" value={backtestId} onChange={(event) => setBacktestId(event.target.value)} placeholder="예: 4e8f..." /><button disabled={loading}>{loading ? "불러오는 중" : "결과 보기"}</button></div></form>{error && <p className="error">{error}</p>}</section></main>;
}
