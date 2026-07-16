import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import {
  cloneStrategyVersion,
  confirmDraft,
  explainBacktest,
  fetchDailyOhlcv,
  getBacktest,
  getStrategyBacktests,
  getStrategyLibrary,
  getStrategyVersions,
  parseStrategy,
  runDraftBacktest,
  updateDraft,
} from "./api";
import type {
  BacktestExplanation,
  BacktestResult,
  BacktestRunSummary,
  Condition,
  EquityPoint,
  OHLCVBar,
  Strategy,
  StrategyDraft,
  StrategyLibraryItem,
  StrategyVersion,
} from "./types";

const won = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  maximumFractionDigits: 1,
});
const examplePrompt =
  "삼성전자를 2018년부터 테스트해줘. 20일 SMA가 60일 SMA를 상향 돌파하면 매수하고 하향 돌파하면 매도해.";

function formatMoney(value: number, currency = "KRW") {
  return currency === "KRW"
    ? `${won.format(value)} KRW`
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(value);
}

function makeDemoData(): OHLCVBar[] {
  const start = new Date("2024-01-02T00:00:00Z");
  let previous = 70000;
  return Array.from({ length: 220 }, (_, index) => {
    const date = new Date(start);
    date.setUTCDate(start.getUTCDate() + index);
    const wave = Math.sin(index / 11) * 1300 + Math.sin(index / 29) * 1700;
    const close = Math.round(70000 + wave + index * 9);
    const open = Math.round(previous + Math.sin(index * 1.7) * 280);
    previous = close;
    return {
      date: date.toISOString().slice(0, 10),
      open,
      high: Math.max(open, close) + 420,
      low: Math.min(open, close) - 420,
      close,
      volume: 800000 + index * 1100,
    };
  });
}

function parseCsv(text: string): OHLCVBar[] {
  const [header, ...rows] = text.trim().split(/\r?\n/);
  const columns = header.split(",").map((value) => value.trim().toLowerCase());
  const required = ["date", "open", "high", "low", "close", "volume"];
  if (required.some((name) => !columns.includes(name)))
    throw new Error(
      "CSV 헤더는 date, open, high, low, close, volume 순서를 포함해야 합니다.",
    );
  const indexes = Object.fromEntries(
    required.map((name) => [name, columns.indexOf(name)]),
  );
  const data = rows.filter(Boolean).map((row, rowIndex) => {
    const values = row.split(",").map((value) => value.trim());
    const bar = Object.fromEntries(
      required.map((name) => [
        name,
        name === "date" ? values[indexes[name]] : Number(values[indexes[name]]),
      ]),
    ) as unknown as OHLCVBar;
    if (
      !bar.date ||
      required
        .slice(1)
        .some((name) => !Number.isFinite(bar[name as keyof OHLCVBar] as number))
    )
      throw new Error(`${rowIndex + 2}번째 행의 값을 확인하세요.`);
    return bar;
  });
  if (!data.length) throw new Error("CSV에 가격 데이터가 없습니다.");
  return data;
}

function operandLabel(operand: Condition["left"]) {
  return operand.type === "VALUE"
    ? String(operand.value)
    : `${operand.indicator} ${operand.period ?? ""}`.trim();
}
function conditionLabel(condition: Condition) {
  return `${operandLabel(condition.left)} ${condition.operator.replace("CROSS_ABOVE", "상향 돌파").replace("CROSS_BELOW", "하향 돌파")} ${operandLabel(condition.right)}`;
}

function linePath(points: EquityPoint[], min: number, span: number) {
  return points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 88 - ((point.equity - min) / span) * 72;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function Chart({
  points,
  benchmarkPoints = [],
  currency,
}: {
  points: EquityPoint[];
  benchmarkPoints?: EquityPoint[];
  currency: string;
}) {
  if (!points.length)
    return <div className="empty-chart">자산곡선 데이터가 없습니다.</div>;
  const values = [...points, ...benchmarkPoints].map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const path = linePath(points, min, span);
  const benchmarkPath = benchmarkPoints.length
    ? linePath(benchmarkPoints, min, span)
    : "";
  const last = points.at(-1)!;
  return (
    <div className="chart-wrap">
      <div className="chart-legend">
        <span>
          <i className="strategy-dot" />
          전략
        </span>
        {benchmarkPath && (
          <span>
            <i className="benchmark-dot" />
            Buy & Hold
          </span>
        )}
      </div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label="전략과 Buy and Hold 자산곡선"
      >
        <defs>
          <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#d97842" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#d97842" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L100,100 L0,100 Z`} fill="url(#area)" />
        <path
          d={benchmarkPath}
          fill="none"
          stroke="#41747e"
          strokeWidth="1.3"
          strokeDasharray="4 3"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={path}
          fill="none"
          stroke="#d97842"
          strokeWidth="1.8"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="chart-meta">
        <span>{points[0].date}</span>
        <strong>{formatMoney(last.equity, currency)}</strong>
        <span>{last.date}</span>
      </div>
    </div>
  );
}

function DrawdownChart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return null;
  let peak = points[0].equity;
  const drawdowns = points.map((point) => {
    peak = Math.max(peak, point.equity);
    return { ...point, equity: point.equity / peak - 1 };
  });
  const path = drawdowns
    .map((point, index) => {
      const x =
        drawdowns.length === 1 ? 50 : (index / (drawdowns.length - 1)) * 100;
      const y =
        12 +
        (Math.abs(point.equity) /
          Math.max(...drawdowns.map((item) => Math.abs(item.equity)), 0.001)) *
          76;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const lowest = Math.min(...drawdowns.map((point) => point.equity));
  return (
    <div className="drawdown-wrap">
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label="전략 낙폭"
      >
        <path d={`${path} L100,0 L0,0 Z`} fill="#41747e" fillOpacity=".2" />
        <path
          d={path}
          fill="none"
          stroke="#41747e"
          strokeWidth="1.6"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="chart-meta">
        <span>최대 낙폭</span>
        <strong>{percent.format(lowest)}</strong>
        <span>0%</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "warm" | "cool";
}) {
  return (
    <article className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function ResultView({
  result,
  restart,
  openLibrary,
}: {
  result: BacktestResult;
  restart: () => void;
  openLibrary: () => void;
}) {
  const returnTone = result.total_return >= 0 ? "warm" : "cool";
  const [explanation, setExplanation] = useState<BacktestExplanation | null>(
    null,
  );
  const [explaining, setExplaining] = useState(false);
  const [explanationError, setExplanationError] = useState("");
  async function loadExplanation() {
    setExplaining(true);
    setExplanationError("");
    try {
      setExplanation(await explainBacktest(result.backtest_id));
    } catch (caught) {
      setExplanationError(
        caught instanceof Error
          ? caught.message
          : "AI 설명을 불러오지 못했습니다.",
      );
    } finally {
      setExplaining(false);
    }
  }
  return (
    <main className="result-shell">
      <div className="top-actions">
        <button className="text-button" onClick={restart}>
          새 전략 만들기
        </button>
        <button className="text-button" onClick={openLibrary}>
          전략 보관함
        </button>
      </div>
      <section className="hero">
        <div>
          <p className="eyebrow">ALPHALENS / BACKTEST RESULT</p>
          <h1>
            전략이 남긴
            <br />
            시간의 궤적.
          </h1>
          <p className="hero-copy">
            확정된 규칙으로 계산된 결과입니다. AI 해석과 수익률 계산은 분리되어
            있습니다.
          </p>
        </div>
        <div className="run-stamp">
          <span>RUN STATUS</span>
          <strong>{result.status}</strong>
          <small>{result.backtest_id}</small>
        </div>
      </section>
      <section className="metrics-grid">
        <Metric
          label="누적 수익률"
          value={percent.format(result.total_return)}
          tone={returnTone}
        />
        <Metric
          label="최종 자산"
          value={formatMoney(result.final_equity, result.currency)}
        />
        <Metric label="CAGR" value={percent.format(result.cagr)} />
        <Metric
          label="최대 낙폭"
          value={percent.format(result.max_drawdown)}
          tone="cool"
        />
      </section>
      <section className="content-grid">
        <article className="panel equity-panel">
          <div className="panel-head">
            <div>
              <span className="panel-kicker">EQUITY CURVE</span>
              <h2>자산곡선 비교</h2>
            </div>
            <span>
              초기 자산 {formatMoney(result.initial_cash, result.currency)}
            </span>
          </div>
          <Chart
            points={result.equity_curve}
            benchmarkPoints={result.benchmark_equity_curve}
            currency={result.currency}
          />
        </article>
        <article className="panel profile-panel">
          <span className="panel-kicker">STRATEGY PROFILE</span>
          <h2>성과의 질</h2>
          <dl>
            <div>
              <dt>샤프지수</dt>
              <dd>{result.sharpe_ratio.toFixed(2)}</dd>
            </div>
            <div>
              <dt>연환산 변동성</dt>
              <dd>{percent.format(result.volatility)}</dd>
            </div>
            <div>
              <dt>승률</dt>
              <dd>{percent.format(result.win_rate)}</dd>
            </div>
            <div>
              <dt>평균 보유기간</dt>
              <dd>{result.average_holding_days.toFixed(1)}일</dd>
            </div>
            <div>
              <dt>총 거래비용</dt>
              <dd>{formatMoney(result.total_cost, result.currency)}</dd>
            </div>
            <div>
              <dt>거래 횟수</dt>
              <dd>{result.trade_count}회</dd>
            </div>
          </dl>
        </article>
      </section>
      <section className="comparison-grid">
        <article className="panel drawdown-panel">
          <span className="panel-kicker">DRAWDOWN</span>
          <h2>낙폭의 깊이</h2>
          <DrawdownChart points={result.equity_curve} />
        </article>
        <article className="panel benchmark-panel">
          <span className="panel-kicker">REFERENCE</span>
          <h2>Buy & Hold 비교</h2>
          <p>
            동일 OHLCV 데이터의 종가 기준 보유 성과입니다. 별도 지수 데이터가
            아닙니다.
          </p>
          <dl>
            <div>
              <dt>기준 수익률</dt>
              <dd>{percent.format(result.benchmark_total_return)}</dd>
            </div>
            <div>
              <dt>기준 최대 낙폭</dt>
              <dd>{percent.format(result.benchmark_max_drawdown)}</dd>
            </div>
            <div>
              <dt>초과 수익률</dt>
              <dd>
                {percent.format(
                  result.total_return - result.benchmark_total_return,
                )}
              </dd>
            </div>
          </dl>
        </article>
      </section>
      <section className="panel explanation-panel">
        <div className="panel-head">
          <div>
            <span className="panel-kicker">AI INTERPRETATION</span>
            <h2>결과 해석</h2>
          </div>
          {!explanation && (
            <button
              className="explain-button"
              onClick={loadExplanation}
              disabled={explaining}
            >
              {explaining ? "AI가 결과를 읽는 중..." : "AI 해석 보기"}
            </button>
          )}
        </div>
        {explanation ? (
          <>
            <p className="explanation-summary">{explanation.summary}</p>
            <div className="explanation-columns">
              <div>
                <h3>관찰</h3>
                <ul>
                  {explanation.observations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>강점</h3>
                <ul>
                  {explanation.strengths.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>위험</h3>
                <ul>
                  {explanation.risks.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
            <p className="disclaimer">{explanation.disclaimer}</p>
          </>
        ) : (
          <p className="explanation-placeholder">
            AI는 저장된 성과 지표만 설명합니다. 계산값과 거래 규칙은 변경하지
            않습니다.
          </p>
        )}
        {explanationError && <p className="error">{explanationError}</p>}
      </section>
      <section className="panel data-version-panel">
        <span className="panel-kicker">REPRODUCIBILITY</span>
        <h2>실행 데이터 버전</h2>
        <p>
          {result.data_start_date} ~ {result.data_end_date} ·{" "}
          {result.data_points}개 캔들
        </p>
        <code>{result.data_version}</code>
      </section>
      <section className="panel trades-panel">
        <div className="panel-head">
          <div>
            <span className="panel-kicker">TRADE LEDGER</span>
            <h2>거래 내역</h2>
          </div>
          <span>{result.trades.length}개의 완료 거래</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>진입</th>
                <th>청산</th>
                <th>수량</th>
                <th>보유</th>
                <th>손익</th>
                <th>수익률</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((trade) => (
                <tr key={`${trade.entry_date}-${trade.exit_date}`}>
                  <td>
                    {trade.entry_date}
                    <small>{formatMoney(trade.entry_price, result.currency)}</small>
                  </td>
                  <td>
                    {trade.exit_date}
                    <small>{formatMoney(trade.exit_price, result.currency)}</small>
                  </td>
                  <td>{won.format(trade.quantity)}</td>
                  <td>{trade.holding_days}일</td>
                  <td className={trade.pnl >= 0 ? "positive" : "negative"}>
                    {formatMoney(trade.pnl, result.currency)}
                  </td>
                  <td
                    className={trade.return_rate >= 0 ? "positive" : "negative"}
                  >
                    {percent.format(trade.return_rate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function LibraryView({
  close,
  onClone,
}: {
  close: () => void;
  onClone: (draft: StrategyDraft) => void;
}) {
  const [strategies, setStrategies] = useState<StrategyLibraryItem[]>([]);
  const [versions, setVersions] = useState<StrategyVersion[]>([]);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cloningVersion, setCloningVersion] = useState("");
  useEffect(() => {
    getStrategyLibrary()
      .then(setStrategies)
      .catch((caught) =>
        setError(
          caught instanceof Error
            ? caught.message
            : "전략 목록을 불러오지 못했습니다.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  async function selectStrategy(strategyId: string) {
    setSelectedId(strategyId);
    setVersions([]);
    setRuns([]);
    setError("");
    try {
      const [nextVersions, nextRuns] = await Promise.all([
        getStrategyVersions(strategyId),
        getStrategyBacktests(strategyId),
      ]);
      setVersions(nextVersions);
      setRuns(nextRuns);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "전략 기록을 불러오지 못했습니다.",
      );
    }
  }
  async function clone(version: StrategyVersion) {
    const key = `${version.strategy_id}-${version.version}`;
    setCloningVersion(key);
    setError("");
    try {
      onClone(await cloneStrategyVersion(version.strategy_id, version.version));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "전략을 복제하지 못했습니다.",
      );
    } finally {
      setCloningVersion("");
    }
  }
  return (
    <main className="library-shell">
      <div className="top-actions">
        <button className="text-button" onClick={close}>
          새 전략 만들기
        </button>
      </div>
      <section className="library-hero">
        <p className="eyebrow">ALPHALENS / STRATEGY LIBRARY</p>
        <h1>
          확정한 규칙을
          <br />
          다시 꺼내봅니다.
        </h1>
        <p>
          확정된 전략과 버전 이력만 보관합니다. 버전을 복제해 수정·확정하면 같은
          전략의 다음 버전으로 저장하고 결과를 비교할 수 있습니다.
        </p>
      </section>
      {loading ? (
        <p>전략 보관함을 불러오는 중입니다.</p>
      ) : (
        <section className="library-grid">
          <div className="library-list">
            {strategies.length === 0 ? (
              <article className="empty-library">
                아직 확정된 전략이 없습니다.
              </article>
            ) : (
              strategies.map((item) => (
                <button
                  key={item.strategy_id}
                  className={`library-card ${selectedId === item.strategy_id ? "selected" : ""}`}
                  onClick={() => selectStrategy(item.strategy_id)}
                >
                  <span>VERSION {item.latest_version}</span>
                  <strong>{item.strategy.strategy_name}</strong>
                  <small>
                    {item.strategy.universe.symbols.join(", ")} ·{" "}
                    {item.strategy.market}
                  </small>
                  <small>
                    {new Date(item.confirmed_at).toLocaleDateString("ko-KR")}{" "}
                    확정
                  </small>
                </button>
              ))
            )}
          </div>
          <aside className="version-panel">
            {selectedId ? (
              <>
                <span className="panel-kicker">VERSION HISTORY</span>
                <h2>전략 이력</h2>
                {versions.map((version) => (
                  <article key={version.draft_id} className="version-card">
                    <span>
                      V{version.version} ·{" "}
                      {new Date(version.confirmed_at).toLocaleString("ko-KR")}
                    </span>
                    <strong>{version.strategy.strategy_name}</strong>
                    <p>
                      {version.strategy.entry_rules.conditions
                        .map(conditionLabel)
                        .join(" / ")}
                    </p>
                    <p>
                      {version.strategy.exit_rules.conditions
                        .map(conditionLabel)
                        .join(" / ")}
                    </p>
                    <button
                      className="clone-button"
                      onClick={() => clone(version)}
                      disabled={
                        cloningVersion ===
                        `${version.strategy_id}-${version.version}`
                      }
                    >
                      {cloningVersion ===
                      `${version.strategy_id}-${version.version}`
                        ? "복제 중..."
                        : "다음 버전으로 복제"}
                    </button>
                  </article>
                ))}
                <section className="run-comparison">
                  <span className="panel-kicker">RUN COMPARISON</span>
                  <h3>실행 결과 비교</h3>
                  {runs.length === 0 ? (
                    <p>
                      이 전략으로 저장된 실행 결과가 없습니다. 다음 버전을
                      실행하면 여기에 비교 기록이 쌓입니다.
                    </p>
                  ) : (
                    <div className="comparison-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>실행 시점</th>
                            <th>수익률</th>
                            <th>MDD</th>
                            <th>샤프</th>
                            <th>최종 자산</th>
                            <th>거래</th>
                          </tr>
                        </thead>
                        <tbody>
                          {runs.map((run) => (
                            <tr key={run.backtest_id}>
                              <td>
                                {new Date(run.created_at).toLocaleDateString(
                                  "ko-KR",
                                )}
                                <small>
                                  V{run.strategy_version ?? "-"} ·{" "}
                                  {run.data_points}개
                                </small>
                              </td>
                              <td
                                className={
                                  run.total_return >= 0
                                    ? "positive"
                                    : "negative"
                                }
                              >
                                {percent.format(run.total_return)}
                              </td>
                              <td className="negative">
                                {percent.format(run.max_drawdown)}
                              </td>
                              <td>{run.sharpe_ratio.toFixed(2)}</td>
                              <td>
                                {formatMoney(run.final_equity, run.currency)}
                              </td>
                              <td>{run.trade_count}회</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            ) : (
              <p className="empty-version">
                왼쪽에서 전략을 선택하면 확정 버전과 실행 결과를 표시합니다.
              </p>
            )}
          </aside>
        </section>
      )}
      {error && <p className="error">{error}</p>}
    </main>
  );
}

function DraftView({
  draft,
  onBack,
  onRun,
  onUpdate,
}: {
  draft: StrategyDraft;
  onBack: () => void;
  onRun: (data: OHLCVBar[]) => Promise<void>;
  onUpdate: (strategy: Strategy) => Promise<void>;
}) {
  const [data, setData] = useState<OHLCVBar[]>(makeDemoData);
  const [source, setSource] = useState("데모 데이터 220일");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [fmpSymbol, setFmpSymbol] = useState(
    () => draft.strategy.universe.symbols[0] ?? "",
  );
  const [loadingFmp, setLoadingFmp] = useState(false);
  const [editing, setEditing] = useState(false);
  const [strategyText, setStrategyText] = useState(() =>
    JSON.stringify(draft.strategy, null, 2),
  );
  const [saving, setSaving] = useState(false);
  async function selectCsv(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const next = parseCsv(await file.text());
      setData(next);
      setSource(`${file.name} · ${next.length}개 캔들`);
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "CSV를 읽지 못했습니다.",
      );
    }
  }
  async function loadFmp() {
    const symbol = fmpSymbol.trim().toUpperCase();
    if (!symbol) {
      setError("FMP 종목코드를 입력하세요. 예: AAPL, NVDA, MSFT");
      return;
    }
    setLoadingFmp(true);
    setError("");
    try {
      const result = await fetchDailyOhlcv({
        provider: "FMP",
        symbol,
        start_date: draft.strategy.period.start_date,
        end_date: draft.strategy.period.end_date,
        adjusted_price: draft.strategy.data.adjusted_price,
      });
      setData(result.data);
      setSource(
        `FMP · ${result.symbol} · ${result.data_points}개 캔들 · ${result.adjustment}`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "FMP 데이터를 불러오지 못했습니다.",
      );
    } finally {
      setLoadingFmp(false);
    }
  }
  async function submit() {
    setRunning(true);
    setError("");
    try {
      await onRun(data);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "백테스트를 실행하지 못했습니다.",
      );
      setRunning(false);
    }
  }
  async function saveStrategy() {
    setSaving(true);
    setError("");
    try {
      const strategy = JSON.parse(strategyText) as Strategy;
      await onUpdate(strategy);
      setEditing(false);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "전략을 저장하지 못했습니다.",
      );
    } finally {
      setSaving(false);
    }
  }
  function cancelEdit() {
    setStrategyText(JSON.stringify(draft.strategy, null, 2));
    setEditing(false);
    setError("");
  }
  return (
    <main className="workflow-shell">
      <button className="text-button" onClick={onBack}>
        다시 입력하기
      </button>
      <section className="workflow-hero">
        <p className="eyebrow">02 / REVIEW & RUN</p>
        <h1>
          규칙을 확인하고,
          <br />
          실행합니다.
        </h1>
        <p>
          AI가 만든 초안은 백테스트 전에 반드시 확인합니다. 계산은 확정된 구조화
          규칙만 사용합니다.
        </p>
      </section>
      <section className="draft-grid">
        <article className="paper-card strategy-card">
          <div className="draft-heading">
            <span className="panel-kicker">STRATEGY DRAFT</span>
            <button className="edit-button" onClick={() => setEditing(true)}>
              초안 수정
            </button>
          </div>
          <h2>{draft.strategy.strategy_name}</h2>
          <p className="strategy-meta">
            {draft.strategy.market} ·{" "}
            {draft.strategy.universe.symbols.join(", ")} ·{" "}
            {draft.strategy.period.start_date} ~{" "}
            {draft.strategy.period.end_date}
          </p>
          <div className="rule-block">
            <span>매수 조건</span>
            {draft.strategy.entry_rules.conditions.map((condition, index) => (
              <strong key={index}>{conditionLabel(condition)}</strong>
            ))}
          </div>
          <div className="rule-block exit">
            <span>매도 조건</span>
            {draft.strategy.exit_rules.conditions.map((condition, index) => (
              <strong key={index}>{conditionLabel(condition)}</strong>
            ))}
          </div>
          <p className="capital-line">
            초기 자본{" "}
            <strong>
              {formatMoney(
                draft.strategy.capital.initial_cash,
                draft.strategy.capital.currency,
              )}
            </strong>
          </p>
        </article>
        <aside className="notes-card">
          <span className="panel-kicker">CHECK BEFORE RUN</span>
          <h2>확인 사항</h2>
          {draft.assumptions.length > 0 && (
            <>
              <h3>적용한 가정</h3>
              <ul>
                {draft.assumptions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {draft.warnings.length > 0 && (
            <>
              <h3>주의</h3>
              <ul className="warnings">
                {draft.warnings.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {draft.missing_fields.length > 0 && (
            <p className="missing">
              추가로 정할 수 있는 항목: {draft.missing_fields.join(", ")}
            </p>
          )}
        </aside>
      </section>
      {editing && (
        <section className="editor-card">
          <div>
            <span className="panel-kicker">EDIT STRATEGY</span>
            <h2>전략 초안 수정</h2>
            <p>
              기간, 초기자본, 조건, 거래비용 등을 JSON으로 수정하세요. 저장 시
              서버가 Schema 규칙을 다시 검증합니다.
            </p>
          </div>
          <textarea
            aria-label="전략 JSON"
            value={strategyText}
            onChange={(event) => setStrategyText(event.target.value)}
            spellCheck="false"
          />
          <div className="editor-actions">
            <button
              className="cancel-button"
              onClick={cancelEdit}
              disabled={saving}
            >
              취소
            </button>
            <button
              className="save-button"
              onClick={saveStrategy}
              disabled={saving}
            >
              {saving ? "검증 및 저장 중..." : "변경 검증 후 저장"}
            </button>
          </div>
        </section>
      )}
      <section className="data-card">
        <div>
          <span className="panel-kicker">MARKET DATA</span>
          <h2>가격 데이터 선택</h2>
          <p>
            <strong>{source}</strong>
            <br />
            FMP는 현재 NASDAQ 등 미국 주식 일봉 조회에 사용합니다. KRX 데이터는
            승인 뒤 추가됩니다. CSV는 `date,open,high,low,close,volume` 헤더가
            필요합니다.
          </p>
        </div>
        <div className="data-actions">
          <div className="fmp-loader">
            <input
              aria-label="FMP 종목코드"
              value={fmpSymbol}
              onChange={(event) => setFmpSymbol(event.target.value)}
              placeholder="FMP 종목코드 예: NVDA"
            />
            <button
              className="fmp-button"
              onClick={loadFmp}
              disabled={loadingFmp}
            >
              {loadingFmp ? "FMP 조회 중..." : "FMP에서 불러오기"}
            </button>
          </div>
          <label className="file-button">
            CSV 선택
            <input type="file" accept=".csv,text/csv" onChange={selectCsv} />
          </label>
        </div>
      </section>
      {error && <p className="error workflow-error">{error}</p>}
      <button
        className="run-button"
        onClick={submit}
        disabled={running || editing}
      >
        {running
          ? "전략 확정 및 실행 중..."
          : editing
            ? "수정을 저장한 뒤 실행하세요"
            : `${data.length}개 캔들로 전략 확정 및 실행`}
      </button>
    </main>
  );
}

export default function App() {
  const initialId =
    new URLSearchParams(window.location.search).get("backtestId") ?? "";
  const [existingId, setExistingId] = useState(initialId);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [rawInput, setRawInput] = useState(examplePrompt);
  const [draft, setDraft] = useState<StrategyDraft | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function createDraft(event: FormEvent) {
    event.preventDefault();
    if (!rawInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      setDraft(await parseStrategy(rawInput.trim()));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "전략을 해석하지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }
  async function execute(data: OHLCVBar[]) {
    if (!draft) return;
    await confirmDraft(draft.draft_id);
    const next = await runDraftBacktest(draft.draft_id, data);
    setResult(next);
    window.history.replaceState(null, "", `?backtestId=${next.backtest_id}`);
  }
  async function saveDraft(strategy: Strategy) {
    if (!draft) return;
    setDraft(await updateDraft(draft.draft_id, strategy));
  }
  async function loadExisting(event: FormEvent) {
    event.preventDefault();
    if (!existingId.trim()) return;
    setLoading(true);
    try {
      setResult(await getBacktest(existingId.trim()));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "결과를 불러오지 못했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }
  function reset() {
    setDraft(null);
    setResult(null);
    setError("");
    window.history.replaceState(null, "", window.location.pathname);
  }
  if (libraryOpen)
    return (
      <LibraryView
        close={() => setLibraryOpen(false)}
        onClone={(nextDraft) => {
          setDraft(nextDraft);
          setLibraryOpen(false);
        }}
      />
    );
  if (result)
    return (
      <ResultView
        result={result}
        restart={reset}
        openLibrary={() => setLibraryOpen(true)}
      />
    );
  if (draft)
    return (
      <DraftView
        draft={draft}
        onBack={reset}
        onRun={execute}
        onUpdate={saveDraft}
      />
    );
  return (
    <main className="landing">
      <section className="landing-card">
        <div className="landing-actions">
          <p className="eyebrow">ALPHALENS / STRATEGY DESK</p>
          <button className="text-button" onClick={() => setLibraryOpen(true)}>
            전략 보관함
          </button>
        </div>
        <h1>
          생각한 규칙을
          <br />
          검증 가능한
          <br />
          전략으로.
        </h1>
        <p>
          자연어로 투자 규칙을 입력하면 AI가 제한된 전략 스키마로 정리합니다.
          실제 수익률 계산은 규칙 기반 엔진이 담당합니다.
        </p>
        <form onSubmit={createDraft}>
          <label htmlFor="strategy-input">STRATEGY IDEA</label>
          <textarea
            id="strategy-input"
            value={rawInput}
            onChange={(event) => setRawInput(event.target.value)}
          />
          <button className="primary-button" disabled={loading}>
            {loading ? "전략 해석 중..." : "전략 초안 만들기"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
        <form className="existing-run" onSubmit={loadExisting}>
          <label htmlFor="existing-run">이미 실행한 결과가 있나요?</label>
          <div>
            <input
              id="existing-run"
              value={existingId}
              onChange={(event) => setExistingId(event.target.value)}
              placeholder="백테스트 ID"
            />
            <button disabled={loading}>불러오기</button>
          </div>
        </form>
      </section>
    </main>
  );
}
