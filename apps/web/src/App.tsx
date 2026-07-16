import { ChangeEvent, FormEvent, useState } from "react";
import { confirmDraft, getBacktest, parseStrategy, runDraftBacktest, updateDraft } from "./api";
import type { BacktestResult, Condition, EquityPoint, OHLCVBar, Strategy, StrategyDraft } from "./types";

const won = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("ko-KR", { style: "percent", maximumFractionDigits: 1 });
const examplePrompt = "삼성전자를 2018년부터 테스트해줘. 20일 SMA가 60일 SMA를 상향 돌파하면 매수하고 하향 돌파하면 매도해.";

function formatWon(value: number) { return `${won.format(value)} KRW`; }

function makeDemoData(): OHLCVBar[] {
  const start = new Date("2024-01-02T00:00:00Z");
  let previous = 70000;
  return Array.from({ length: 220 }, (_, index) => {
    const date = new Date(start); date.setUTCDate(start.getUTCDate() + index);
    const wave = Math.sin(index / 11) * 1300 + Math.sin(index / 29) * 1700;
    const close = Math.round(70000 + wave + index * 9);
    const open = Math.round(previous + Math.sin(index * 1.7) * 280);
    previous = close;
    return { date: date.toISOString().slice(0, 10), open, high: Math.max(open, close) + 420, low: Math.min(open, close) - 420, close, volume: 800000 + index * 1100 };
  });
}

function parseCsv(text: string): OHLCVBar[] {
  const [header, ...rows] = text.trim().split(/\r?\n/);
  const columns = header.split(",").map((value) => value.trim().toLowerCase());
  const required = ["date", "open", "high", "low", "close", "volume"];
  if (required.some((name) => !columns.includes(name))) throw new Error("CSV 헤더는 date, open, high, low, close, volume 순서를 포함해야 합니다.");
  const indexes = Object.fromEntries(required.map((name) => [name, columns.indexOf(name)]));
  const data = rows.filter(Boolean).map((row, rowIndex) => {
    const values = row.split(",").map((value) => value.trim());
    const bar = Object.fromEntries(required.map((name) => [name, name === "date" ? values[indexes[name]] : Number(values[indexes[name]])])) as unknown as OHLCVBar;
    if (!bar.date || required.slice(1).some((name) => !Number.isFinite(bar[name as keyof OHLCVBar] as number))) throw new Error(`${rowIndex + 2}번째 행의 값을 확인하세요.`);
    return bar;
  });
  if (!data.length) throw new Error("CSV에 가격 데이터가 없습니다.");
  return data;
}

function operandLabel(operand: Condition["left"]) { return operand.type === "VALUE" ? String(operand.value) : `${operand.indicator} ${operand.period ?? ""}`.trim(); }
function conditionLabel(condition: Condition) { return `${operandLabel(condition.left)} ${condition.operator.replace("CROSS_ABOVE", "상향 돌파").replace("CROSS_BELOW", "하향 돌파")} ${operandLabel(condition.right)}`; }

function Chart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return <div className="empty-chart">자산곡선 데이터가 없습니다.</div>;
  const values = points.map((point) => point.equity); const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
  const path = points.map((point, index) => { const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100; const y = 88 - ((point.equity - min) / span) * 72; return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`; }).join(" ");
  const last = points.at(-1)!;
  return <div className="chart-wrap"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="전략 자산곡선"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#d97842" stopOpacity="0.42" /><stop offset="100%" stopColor="#d97842" stopOpacity="0" /></linearGradient></defs><path d={`${path} L100,100 L0,100 Z`} fill="url(#area)" /><path d={path} fill="none" stroke="#d97842" strokeWidth="1.8" vectorEffect="non-scaling-stroke" /></svg><div className="chart-meta"><span>{points[0].date}</span><strong>{formatWon(last.equity)}</strong><span>{last.date}</span></div></div>;
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warm" | "cool" }) { return <article className={`metric ${tone ?? ""}`}><span>{label}</span><strong>{value}</strong></article>; }

function ResultView({ result, restart }: { result: BacktestResult; restart: () => void }) {
  const returnTone = result.total_return >= 0 ? "warm" : "cool";
  return <main className="result-shell"><button className="text-button" onClick={restart}>새 전략 만들기</button><section className="hero"><div><p className="eyebrow">ALPHALENS / BACKTEST RESULT</p><h1>전략이 남긴<br />시간의 궤적.</h1><p className="hero-copy">확정된 규칙으로 계산된 결과입니다. AI 해석과 수익률 계산은 분리되어 있습니다.</p></div><div className="run-stamp"><span>RUN STATUS</span><strong>{result.status}</strong><small>{result.backtest_id}</small></div></section><section className="metrics-grid"><Metric label="누적 수익률" value={percent.format(result.total_return)} tone={returnTone} /><Metric label="최종 자산" value={formatWon(result.final_equity)} /><Metric label="CAGR" value={percent.format(result.cagr)} /><Metric label="최대 낙폭" value={percent.format(result.max_drawdown)} tone="cool" /></section><section className="content-grid"><article className="panel equity-panel"><div className="panel-head"><div><span className="panel-kicker">EQUITY CURVE</span><h2>자산곡선</h2></div><span>초기 자산 {formatWon(result.initial_cash)}</span></div><Chart points={result.equity_curve} /></article><article className="panel profile-panel"><span className="panel-kicker">STRATEGY PROFILE</span><h2>성과의 질</h2><dl><div><dt>샤프지수</dt><dd>{result.sharpe_ratio.toFixed(2)}</dd></div><div><dt>연환산 변동성</dt><dd>{percent.format(result.volatility)}</dd></div><div><dt>승률</dt><dd>{percent.format(result.win_rate)}</dd></div><div><dt>평균 보유기간</dt><dd>{result.average_holding_days.toFixed(1)}일</dd></div><div><dt>총 거래비용</dt><dd>{formatWon(result.total_cost)}</dd></div><div><dt>거래 횟수</dt><dd>{result.trade_count}회</dd></div></dl></article></section><section className="panel trades-panel"><div className="panel-head"><div><span className="panel-kicker">TRADE LEDGER</span><h2>거래 내역</h2></div><span>{result.trades.length}개의 완료 거래</span></div><div className="table-wrap"><table><thead><tr><th>진입</th><th>청산</th><th>수량</th><th>보유</th><th>손익</th><th>수익률</th></tr></thead><tbody>{result.trades.map((trade) => <tr key={`${trade.entry_date}-${trade.exit_date}`}><td>{trade.entry_date}<small>{formatWon(trade.entry_price)}</small></td><td>{trade.exit_date}<small>{formatWon(trade.exit_price)}</small></td><td>{won.format(trade.quantity)}</td><td>{trade.holding_days}일</td><td className={trade.pnl >= 0 ? "positive" : "negative"}>{formatWon(trade.pnl)}</td><td className={trade.return_rate >= 0 ? "positive" : "negative"}>{percent.format(trade.return_rate)}</td></tr>)}</tbody></table></div></section></main>;
}

function DraftView({ draft, onBack, onRun, onUpdate }: { draft: StrategyDraft; onBack: () => void; onRun: (data: OHLCVBar[]) => Promise<void>; onUpdate: (strategy: Strategy) => Promise<void> }) {
  const [data, setData] = useState<OHLCVBar[]>(makeDemoData);
  const [source, setSource] = useState("데모 데이터 220일"); const [error, setError] = useState(""); const [running, setRunning] = useState(false);
  const [editing, setEditing] = useState(false); const [strategyText, setStrategyText] = useState(() => JSON.stringify(draft.strategy, null, 2)); const [saving, setSaving] = useState(false);
  async function selectCsv(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; try { const next = parseCsv(await file.text()); setData(next); setSource(`${file.name} · ${next.length}개 캔들`); setError(""); } catch (caught) { setError(caught instanceof Error ? caught.message : "CSV를 읽지 못했습니다."); } }
  async function submit() { setRunning(true); setError(""); try { await onRun(data); } catch (caught) { setError(caught instanceof Error ? caught.message : "백테스트를 실행하지 못했습니다."); setRunning(false); } }
  async function saveStrategy() { setSaving(true); setError(""); try { const strategy = JSON.parse(strategyText) as Strategy; await onUpdate(strategy); setEditing(false); } catch (caught) { setError(caught instanceof Error ? caught.message : "전략을 저장하지 못했습니다."); } finally { setSaving(false); } }
  function cancelEdit() { setStrategyText(JSON.stringify(draft.strategy, null, 2)); setEditing(false); setError(""); }
  return <main className="workflow-shell"><button className="text-button" onClick={onBack}>다시 입력하기</button><section className="workflow-hero"><p className="eyebrow">02 / REVIEW & RUN</p><h1>규칙을 확인하고,<br />실행합니다.</h1><p>AI가 만든 초안은 백테스트 전에 반드시 확인합니다. 계산은 확정된 구조화 규칙만 사용합니다.</p></section><section className="draft-grid"><article className="paper-card strategy-card"><div className="draft-heading"><span className="panel-kicker">STRATEGY DRAFT</span><button className="edit-button" onClick={() => setEditing(true)}>초안 수정</button></div><h2>{draft.strategy.strategy_name}</h2><p className="strategy-meta">{draft.strategy.market} · {draft.strategy.universe.symbols.join(", ")} · {draft.strategy.period.start_date} ~ {draft.strategy.period.end_date}</p><div className="rule-block"><span>매수 조건</span>{draft.strategy.entry_rules.conditions.map((condition, index) => <strong key={index}>{conditionLabel(condition)}</strong>)}</div><div className="rule-block exit"><span>매도 조건</span>{draft.strategy.exit_rules.conditions.map((condition, index) => <strong key={index}>{conditionLabel(condition)}</strong>)}</div><p className="capital-line">초기 자본 <strong>{formatWon(draft.strategy.capital.initial_cash)}</strong></p></article><aside className="notes-card"><span className="panel-kicker">CHECK BEFORE RUN</span><h2>확인 사항</h2>{draft.assumptions.length > 0 && <><h3>적용한 가정</h3><ul>{draft.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></>}{draft.warnings.length > 0 && <><h3>주의</h3><ul className="warnings">{draft.warnings.map((item) => <li key={item}>{item}</li>)}</ul></>}{draft.missing_fields.length > 0 && <p className="missing">추가로 정할 수 있는 항목: {draft.missing_fields.join(", ")}</p>}</aside></section>{editing && <section className="editor-card"><div><span className="panel-kicker">EDIT STRATEGY</span><h2>전략 초안 수정</h2><p>기간, 초기자본, 조건, 거래비용 등을 JSON으로 수정하세요. 저장 시 서버가 Schema 규칙을 다시 검증합니다.</p></div><textarea aria-label="전략 JSON" value={strategyText} onChange={(event) => setStrategyText(event.target.value)} spellCheck="false" /><div className="editor-actions"><button className="cancel-button" onClick={cancelEdit} disabled={saving}>취소</button><button className="save-button" onClick={saveStrategy} disabled={saving}>{saving ? "검증 및 저장 중..." : "변경 검증 후 저장"}</button></div></section>}<section className="data-card"><div><span className="panel-kicker">MARKET DATA</span><h2>검증용 가격 데이터</h2><p><strong>{source}</strong><br />CSV는 `date,open,high,low,close,volume` 헤더가 필요합니다. SMA 60 전략에는 최소 61개 이상의 캔들이 필요합니다.</p></div><label className="file-button">CSV 선택<input type="file" accept=".csv,text/csv" onChange={selectCsv} /></label></section>{error && <p className="error workflow-error">{error}</p>}<button className="run-button" onClick={submit} disabled={running || editing}>{running ? "전략 확정 및 실행 중..." : editing ? "수정을 저장한 뒤 실행하세요" : `${data.length}개 캔들로 전략 확정 및 실행`}</button></main>;
}

export default function App() {
  const initialId = new URLSearchParams(window.location.search).get("backtestId") ?? "";
  const [existingId, setExistingId] = useState(initialId);
  const [rawInput, setRawInput] = useState(examplePrompt); const [draft, setDraft] = useState<StrategyDraft | null>(null); const [result, setResult] = useState<BacktestResult | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  async function createDraft(event: FormEvent) { event.preventDefault(); if (!rawInput.trim()) return; setLoading(true); setError(""); try { setDraft(await parseStrategy(rawInput.trim())); } catch (caught) { setError(caught instanceof Error ? caught.message : "전략을 해석하지 못했습니다."); } finally { setLoading(false); } }
  async function execute(data: OHLCVBar[]) { if (!draft) return; await confirmDraft(draft.draft_id); const next = await runDraftBacktest(draft.draft_id, data); setResult(next); window.history.replaceState(null, "", `?backtestId=${next.backtest_id}`); }
  async function saveDraft(strategy: Strategy) { if (!draft) return; setDraft(await updateDraft(draft.draft_id, strategy)); }
  async function loadExisting(event: FormEvent) { event.preventDefault(); if (!existingId.trim()) return; setLoading(true); try { setResult(await getBacktest(existingId.trim())); } catch (caught) { setError(caught instanceof Error ? caught.message : "결과를 불러오지 못했습니다."); } finally { setLoading(false); } }
  function reset() { setDraft(null); setResult(null); setError(""); window.history.replaceState(null, "", window.location.pathname); }
  if (result) return <ResultView result={result} restart={reset} />;
  if (draft) return <DraftView draft={draft} onBack={reset} onRun={execute} onUpdate={saveDraft} />;
  return <main className="landing"><section className="landing-card"><p className="eyebrow">ALPHALENS / STRATEGY DESK</p><h1>생각한 규칙을<br />검증 가능한<br />전략으로.</h1><p>자연어로 투자 규칙을 입력하면 AI가 제한된 전략 스키마로 정리합니다. 실제 수익률 계산은 규칙 기반 엔진이 담당합니다.</p><form onSubmit={createDraft}><label htmlFor="strategy-input">STRATEGY IDEA</label><textarea id="strategy-input" value={rawInput} onChange={(event) => setRawInput(event.target.value)} /><button className="primary-button" disabled={loading}>{loading ? "전략 해석 중..." : "전략 초안 만들기"}</button></form>{error && <p className="error">{error}</p>}<form className="existing-run" onSubmit={loadExisting}><label htmlFor="existing-run">이미 실행한 결과가 있나요?</label><div><input id="existing-run" value={existingId} onChange={(event) => setExistingId(event.target.value)} placeholder="백테스트 ID" /><button disabled={loading}>불러오기</button></div></form></section></main>;
}
