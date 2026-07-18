# AlphaLens

자연어로 투자 전략을 설명하면 AI가 이를 구조화된 백테스트 전략으로 변환하고, 사용자의 최종 확인을 받은 뒤 과거 주가 데이터로 백테스트를 실행하는 서비스입니다.

---

## 1. 프로젝트 목표

사용자는 Python 코드나 백테스트 라이브러리를 직접 다루지 않고도 채팅으로 투자 전략을 입력할 수 있습니다.

예시:

```text
삼성전자를 2015년부터 테스트하고 싶어.
20일 이동평균선이 60일 이동평균선을 위로 돌파하면 매수하고,
아래로 돌파하면 전량 매도해.
초기 투자금은 1,000만 원으로 해줘.
```

서비스는 이를 바로 실행하지 않고 다음 순서로 처리합니다.

```text
사용자 자연어 입력
→ AI 전략 해석
→ 전략 JSON 생성
→ 누락·모순·지원 여부 검증
→ 사용자에게 전략 요약 표시
→ 사용자 최종 확인
→ 백테스트 실행
→ 결과 저장
→ 성과지표·차트·거래내역·AI 해설 제공
```

핵심 원칙:

> AI는 전략을 해석하고 결과를 설명하지만, 실제 수익률 계산은 검증된 Python 백테스트 엔진만 수행한다.

---

## 2. 참고 프로젝트

구조 설계 시 아래 프로젝트를 참고합니다.

- Repository: `team-muscle-market/MuscleMarket`
- URL: https://github.com/team-muscle-market/MuscleMarket

참고할 핵심 구조:

```text
controller
domain
dto
enums
exceptions
repository
service
config
```

MuscleMarket의 AI 추천 기능은 다음 흐름으로 구성되어 있습니다.

```text
Controller
→ Recommendation Service
→ AI API Client
→ Repository 조회
→ DTO 반환
```

본 프로젝트에서는 이를 다음과 같이 확장합니다.

```text
Chat Route
→ Strategy Parser Service
→ OpenAI Client
→ Strategy Validator Service
→ 사용자 확인
→ Strategy Compiler Service
→ Backtest Worker
→ Backtest Engine
→ Result Repository
→ Result Response
```

MuscleMarket처럼 계층별 역할은 명확히 분리하되, AI 응답에서 문자열이나 정규표현식으로 값을 추출하지 않습니다.

전략은 반드시 JSON Schema 기반 구조화 출력으로 생성합니다.

---

## 3. MVP 범위

### 지원 대상

- 한국 주식
- 단일 종목
- 일봉 데이터
- 현물 매수 후 매도
- 공매도 미지원
- 단일 통화 KRW

### 지원 지표

- 시가
- 고가
- 저가
- 종가
- 거래량
- SMA
- EMA
- RSI
- 일간 수익률
- N일 수익률
- N일 최고가
- N일 최저가
- 거래량 이동평균

### 교차자산 신호 (단일 종목 전략)

단일 종목 전략의 매수·매도 조건은 기본적으로 거래 종목 자신의 데이터로 평가되지만, 조건의 지표에 `symbol`을 지정하면 KOSPI 등 다른 종목·지수를 신호로 사용할 수 있습니다. 신호 종목의 가격 데이터는 실행 전에 별도로 제공해야 하며, 조건이 신호 종목을 지정했는데 실행 요청에 해당 데이터가 없으면 거부됩니다. `pykrx`는 개별 종목만 지원하므로 KOSPI(`^KS11`)·KOSDAQ(`^KQ11`) 같은 지수 신호 종목은 화면에서 종목별로 별도 공급원(Yahoo Finance 등)을 선택해 조회합니다.

### 지원 연산자

```text
GREATER_THAN
GREATER_THAN_OR_EQUAL
LESS_THAN
LESS_THAN_OR_EQUAL
CROSS_ABOVE
CROSS_BELOW
EQUAL
```

### 지원 조건 조합

```text
AND
OR
```

### 지원 포지션 크기

- 가용 현금 전액
- 전체 자산의 일정 비율
- 고정 금액
- 고정 수량

### 지원 위험 관리

- 손절
- 익절
- 최대 보유기간
- 중복 매수 허용 여부
- 최대 투자 비중

### 결과 지표

- 누적수익률
- CAGR
- 최대낙폭
- 연환산 변동성
- 샤프지수
- 거래 횟수
- 승률
- 평균 거래수익률
- 평균 보유기간
- 거래비용 총액
- 벤치마크 수익률

### MVP 제외 범위

- 실시간 자동매매
- 증권사 계좌 연결
- 선물·옵션
- 레버리지
- 공매도
- 분봉·틱 데이터
- 뉴스 감성분석
- 머신러닝 주가 예측
- 임의 Python 코드 실행
- 재무제표 기반 종목 선별
- 다종목 포트폴리오
- 파라미터 자동 최적화

---

## 4. 기술 스택

### Frontend

- React 또는 Next.js
- TypeScript
- Tailwind CSS
- Cloudflare Pages

### Backend

- Python
- FastAPI
- Pydantic
- psycopg 기반 PostgreSQL 연결

### Database

- PostgreSQL
- Neon PostgreSQL 사용
- 전략 초안, 전략 버전, 백테스트 실행 결과를 영속 저장

### Backtest Engine

초기 버전은 외부 백테스트 라이브러리에 강하게 의존하지 않고 아래 기술로 제한된 자체 엔진을 구현합니다.

- pandas
- NumPy

### Market Data

- 일봉 OHLCV 데이터
- 개인용 데이터 공급원으로 미국 주식·ETF는 `yfinance`, 한국 주식·ETF는 `pykrx` 사용
- FMP는 상용 데이터 품질 또는 서비스 확장 시 선택적으로 지원
- CSV 업로드 지원
- 단일 종목과 다자산 전환 전략 모두 CSV 또는 공급원 데이터로 실행 지원
- 데이터 해시와 공급원 정보를 실행 결과에 저장

### AI

- OpenAI API
- Structured Outputs
- JSON Schema 기반 전략 변환

### Charts

- Plotly
- 또는 Lightweight Charts

### Deployment

- Frontend: Cloudflare Pages
- Backend: Render
- Database: Neon PostgreSQL
- CI/CD: GitHub Actions

---

## 4.1 구현 현황 관리

실제 구현 현황과 후속 계획은 [Phase별 구현 우선순위](#13-구현-우선순위)에서 관리한다. 각 Phase는 `완료`, `진행 중`, `예정` 중 하나의 상태를 가지며, 완료 조건을 만족한 항목만 `완료`로 기록한다.

- 구현 또는 배포가 끝난 기능은 관련 Phase의 완료 범위와 완료 조건에 반영한다.
- 아직 검증되지 않은 기능은 해당 Phase의 다음 완료 조건에만 기록한다.
- 데이터 공급원, 배포 환경, 보안 설정 등 운영 구조가 바뀌면 같은 변경에서 README도 함께 갱신한다.

---

## 5. 권장 폴더 구조

```text
stock-backtester/
│
├── apps/
│   └── web/
│       ├── components/
│       ├── pages/
│       ├── features/
│       │   ├── chat/
│       │   ├── strategy/
│       │   └── backtest/
│       ├── lib/
│       └── types/
│
├── services/
│   └── api/
│       └── app/
│           ├── main.py
│           │
│           ├── api/
│           │   ├── chat_routes.py
│           │   ├── strategy_routes.py
│           │   ├── backtest_routes.py
│           │   └── market_data_routes.py
│           │
│           ├── domain/
│           │   ├── conversation.py
│           │   ├── strategy.py
│           │   ├── backtest.py
│           │   ├── trade.py
│           │   └── market_data.py
│           │
│           ├── schemas/
│           │   ├── chat_schema.py
│           │   ├── strategy_schema.py
│           │   ├── backtest_schema.py
│           │   └── result_schema.py
│           │
│           ├── enums/
│           │   ├── strategy_status.py
│           │   ├── backtest_status.py
│           │   ├── indicator_type.py
│           │   └── operator_type.py
│           │
│           ├── services/
│           │   ├── conversation_service.py
│           │   ├── strategy_parser_service.py
│           │   ├── strategy_validator_service.py
│           │   ├── strategy_compiler_service.py
│           │   ├── backtest_service.py
│           │   └── result_analysis_service.py
│           │
│           ├── repositories/
│           │   ├── strategy_repository.py
│           │   ├── backtest_repository.py
│           │   └── market_data_repository.py
│           │
│           ├── clients/
│           │   ├── openai_client.py
│           │   └── market_data_client.py
│           │
│           ├── backtest_engine/
│           │   ├── engine.py
│           │   ├── indicators.py
│           │   ├── signal_generator.py
│           │   ├── order_simulator.py
│           │   ├── portfolio.py
│           │   └── metrics.py
│           │
│           ├── workers/
│           │   └── backtest_worker.py
│           │
│           ├── exceptions/
│           │   ├── strategy_exception.py
│           │   ├── data_exception.py
│           │   └── backtest_exception.py
│           │
│           └── core/
│               ├── config.py
│               ├── database.py
│               ├── logging.py
│               └── security.py
│
├── data_pipeline/
│   ├── collect_market_data.py
│   ├── validate_market_data.py
│   └── save_parquet.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── parquet/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── fixtures/
│
├── infra/
│   ├── docker/
│   └── github-actions/
│
├── docs/
│   ├── strategy-schema.md
│   ├── backtest-rules.md
│   └── api-spec.md
│
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## 6. 핵심 서비스 책임

### StrategyParserService

사용자의 자연어를 구조화된 전략 JSON으로 변환합니다.

담당 범위:

- 종목 추출
- 기간 추출
- 매수 조건 추출
- 매도 조건 추출
- 투자 비중 추출
- 위험 관리 조건 추출
- 거래비용 조건 추출
- 체결 시점 추출
- 누락 항목과 가정값 구분

하지 않는 일:

- 백테스트 실행
- 수익률 계산
- 임의 Python 코드 생성

### StrategyValidatorService

전략 JSON이 실행 가능한지 검사합니다.

필수 검증:

- 종목 존재 여부
- 종목코드 유효성
- 시작일과 종료일 순서
- 데이터 존재 기간
- 매수 조건 존재 여부
- 매도 조건 존재 여부
- 지원 지표 여부
- 지원 연산자 여부
- 지표 기간이 1 이상인지
- 투자 비중이 0 초과 1 이하인지
- 손절·익절 값이 올바른지
- 조건 간 모순 여부
- 미래 데이터 참조 여부
- 초기 투자금 유효성

검증 결과:

```json
{
  "valid": false,
  "errors": [],
  "warnings": [],
  "missing_fields": [],
  "assumptions": []
}
```

### StrategyCompilerService

확정된 전략 JSON을 백테스트 엔진이 이해하는 내부 명령으로 변환합니다.

예시:

```text
SMA 20 계산
SMA 60 계산
SMA20이 SMA60을 상향 돌파하면 entry_signal=True
SMA20이 SMA60을 하향 돌파하면 exit_signal=True
신호 다음 거래일 시가로 주문 생성
```

AI가 Python 코드를 만들지 않고, 사전에 정의된 지표와 연산자를 조합합니다.

### BacktestService

백테스트 실행 흐름 전체를 관리합니다.

담당 범위:

- 실행 요청 생성
- 전략 버전 조회
- 데이터 버전 조회
- 실행 상태 변경
- Worker 호출
- 결과 저장
- 실패 원인 저장

### BacktestEngine

실제 계산만 수행합니다.

담당 범위:

- 지표 계산
- 신호 생성
- 주문 체결
- 현금 관리
- 주식 수량 관리
- 수수료 반영
- 슬리피지 반영
- 일별 평가금액 계산
- 거래 내역 생성
- 성과지표 계산

AI API 호출은 절대 하지 않습니다.

### ResultAnalysisService

백테스트 엔진이 계산한 결과를 사용자가 이해하기 쉬운 문장으로 설명합니다.

AI에게 전달하는 데이터는 계산 완료된 요약값으로 제한합니다.

```json
{
  "total_return": 0.843,
  "benchmark_return": 0.621,
  "cagr": 0.063,
  "max_drawdown": -0.214,
  "sharpe_ratio": 0.74,
  "trade_count": 18,
  "win_rate": 0.556,
  "best_trade": 0.183,
  "worst_trade": -0.102
}
```

AI가 계산 결과를 수정하거나 새로운 수익률을 생성해서는 안 됩니다.

---

## 7. 전략 JSON 예시

```json
{
  "strategy_name": "삼성전자 이동평균선 교차 전략",
  "market": "KRX",
  "universe": {
    "type": "SINGLE_STOCK",
    "symbols": ["005930"]
  },
  "period": {
    "start_date": "2015-01-01",
    "end_date": "2026-07-16"
  },
  "data": {
    "timeframe": "1D",
    "adjusted_price": true
  },
  "entry_rules": {
    "logic": "AND",
    "conditions": [
      {
        "left": {
          "type": "INDICATOR",
          "indicator": "SMA",
          "period": 20
        },
        "operator": "CROSS_ABOVE",
        "right": {
          "type": "INDICATOR",
          "indicator": "SMA",
          "period": 60
        }
      }
    ]
  },
  "exit_rules": {
    "logic": "AND",
    "conditions": [
      {
        "left": {
          "type": "INDICATOR",
          "indicator": "SMA",
          "period": 20
        },
        "operator": "CROSS_BELOW",
        "right": {
          "type": "INDICATOR",
          "indicator": "SMA",
          "period": 60
        }
      }
    ]
  },
  "position_sizing": {
    "method": "PERCENT_OF_EQUITY",
    "value": 0.5
  },
  "risk_management": {
    "stop_loss": 0.1,
    "take_profit": null,
    "maximum_holding_days": null
  },
  "execution": {
    "signal_time": "CLOSE",
    "execution_time": "NEXT_OPEN"
  },
  "costs": {
    "commission_rate": 0.001,
    "slippage_rate": 0.0005,
    "tax_rate": 0.0
  },
  "capital": {
    "initial_cash": 10000000,
    "currency": "KRW"
  },
  "benchmark": "KOSPI"
}
```

---

## 8. 사용자 흐름

### 1. 전략 입력

```text
RSI가 30 아래면 삼성전자를 사고 70 이상이면 팔아줘.
2018년부터 지금까지 테스트하고 초기 자금은 1,000만 원으로 해줘.
```

### 2. AI 전략 해석

서비스는 아래 내용을 사용자에게 보여줍니다.

```text
종목: 삼성전자
기간: 2018-01-01 ~ 현재
RSI 기간: 14일
매수 조건: RSI <= 30
매도 조건: RSI >= 70
초기 자금: 10,000,000원
체결 시점: 다음 거래일 시가
투자 비중: 가용 현금 100%
거래비용: 기본값
```

사용자가 입력하지 않은 값은 반드시 `AI 기본값` 또는 `가정`으로 구분합니다.

### 3. 사용자 확인

```text
조건 수정
채팅으로 수정
이 조건으로 실행
```

### 4. 전략 확정

확정 시 전략 버전을 생성합니다.

```text
Strategy 1 / Version 1
```

조건 수정 후 다시 확정하면 기존 버전을 수정하지 않고 새 버전을 생성합니다.

```text
Strategy 1 / Version 2
```

### 5. 백테스트 실행

```text
QUEUED
→ RUNNING
→ SUCCEEDED
```

실패 시:

```text
FAILED
```

### 6. 결과 표시

- 주요 성과지표
- 전략·벤치마크 자산곡선
- 낙폭 그래프
- 매수·매도 지점
- 거래 내역
- 전략 조건
- 데이터 버전
- 엔진 버전
- AI 결과 해설

---

## 9. 상태 Enum

### StrategyStatus

```text
DRAFT
NEEDS_INPUT
READY_TO_CONFIRM
CONFIRMED
ARCHIVED
```

### BacktestStatus

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELED
```

### IndicatorType

```text
OPEN
HIGH
LOW
CLOSE
VOLUME
SMA
EMA
RSI
RETURN
N_DAY_RETURN
N_DAY_HIGH
N_DAY_LOW
VOLUME_SMA
```

### OperatorType

```text
GREATER_THAN
GREATER_THAN_OR_EQUAL
LESS_THAN
LESS_THAN_OR_EQUAL
CROSS_ABOVE
CROSS_BELOW
EQUAL
```

---

## 10. 데이터베이스 초안

### conversations

```text
id
user_id
title
created_at
updated_at
```

### messages

```text
id
conversation_id
role
content
created_at
```

### strategy_drafts

```text
id
conversation_id
raw_input
parsed_strategy_json
status
missing_fields_json
assumptions_json
created_at
updated_at
```

### strategies

```text
id
user_id
name
created_at
updated_at
```

### strategy_versions

```text
id
strategy_id
version
strategy_json
schema_version
confirmed_at
```

### backtest_runs

```text
id
strategy_version_id
market_data_version_id
status
engine_version
started_at
finished_at
error_code
error_message
```

### backtest_metrics

```text
id
backtest_run_id
total_return
cagr
volatility
max_drawdown
sharpe_ratio
win_rate
trade_count
benchmark_return
total_cost
```

### trades

```text
id
backtest_run_id
symbol
entry_date
entry_price
exit_date
exit_price
quantity
pnl
return_rate
holding_days
entry_reason
exit_reason
```

### equity_curve

```text
id
backtest_run_id
trade_date
cash
market_value
total_equity
benchmark_equity
drawdown
```

### market_data_versions

```text
id
provider
collected_at
start_date
end_date
adjustment_method
checksum
```

---

## 11. 주요 API 초안

### Conversation

```http
POST /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}
POST /api/v1/conversations/{conversation_id}/messages
```

### Strategy Draft

```http
GET   /api/v1/strategy-drafts/{draft_id}
PATCH /api/v1/strategy-drafts/{draft_id}
POST  /api/v1/strategy-drafts/{draft_id}/validate
POST  /api/v1/strategy-drafts/{draft_id}/confirm
```

### Strategy

```http
GET  /api/v1/strategies
GET  /api/v1/strategies/{strategy_id}
GET  /api/v1/strategies/{strategy_id}/versions
POST /api/v1/strategies/{strategy_id}/clone
```

### Backtest

```http
POST /api/v1/backtests
GET  /api/v1/backtests/{backtest_id}
GET  /api/v1/backtests/{backtest_id}/result
GET  /api/v1/backtests/{backtest_id}/metrics
GET  /api/v1/backtests/{backtest_id}/trades
GET  /api/v1/backtests/{backtest_id}/equity-curve
```

### Market Data

```http
GET  /api/v1/market-data/symbols
GET  /api/v1/market-data/symbols/{symbol}
GET  /api/v1/market-data/symbols/{symbol}/availability
```

---

## 12. 백테스트 정확성 원칙

### 미래 데이터 참조 금지

기본 체결 방식:

```text
오늘 종가까지 확인
→ 장 마감 후 신호 계산
→ 다음 거래일 시가에 체결
```

오늘 종가로 계산한 신호를 같은 날 종가에 체결하면 안 됩니다.

### 전략 버전 고정

백테스트마다 아래 정보를 저장합니다.

- 전략 JSON
- 전략 스키마 버전
- 엔진 버전
- 주가 데이터 버전
- 수수료 설정
- 슬리피지 설정
- 실행 시각

### 수정주가 기준 표시

결과 화면에 수정주가 사용 여부와 조정 방식을 표시합니다.

### 거래비용 분리

- 매수 수수료
- 매도 수수료
- 거래세
- 슬리피지

각 항목을 별도로 계산하고 저장합니다.

### 데이터 누락 검사

백테스트 전에 아래 항목을 검사합니다.

- 중복 날짜
- 결측값
- 거래일 정렬
- 음수 거래량
- OHLC 관계 오류
- 비정상 가격
- 데이터 기간 부족

### 재현성

동일한 아래 조건에서는 결과가 항상 동일해야 합니다.

```text
전략 버전
데이터 버전
엔진 버전
거래비용
실행 옵션
```

---

## 13. 구현 우선순위

### Phase 1. 백테스트 엔진

상태: **완료**

먼저 웹과 AI 없이 Python 계산 엔진부터 구현합니다.

완료 범위:

- Parquet 또는 CSV 읽기
- SMA, EMA, RSI 계산
- 매수·매도 신호 생성
- 다음 거래일 시가 체결
- 현금과 주식 수량 관리
- 수수료와 슬리피지 반영
- 거래 내역 생성
- 누적수익률 계산
- CAGR 계산
- MDD 계산
- 결과 JSON 출력

추가 완료 범위:

- 손절/익절, 최대 보유기간, 거래세를 포함한 위험관리와 비용 처리
- 샤프 비율, 변동성, 승률, Same-data Buy & Hold 비교
- 2자산 국면 전환과 목표 비중 리밸런싱(주간·월간·분기 주기 선택)

### Phase 2. 전략 Schema

상태: **완료**

- Pydantic 모델 작성
- Enum 작성
- 전략 JSON 검증
- 잘못된 조건 거절
- JSON 전략으로 엔진 실행

추가 완료 범위:

- 단일 종목 규칙과 2자산 국면 전환, 목표 비중, 주간/월간/분기 리밸런싱 Schema
- Schema 밖의 지표 및 연산자 실행 차단

### Phase 3. API

상태: **완료**

- FastAPI 프로젝트 생성
- 전략 검증 API
- 백테스트 실행 API
- 결과 조회 API
- 오류 응답 통일

추가 완료 범위:

- FMP 미국 주식 일봉 OHLCV 조회 API와 단일 종목 CSV 업로드 실행 API
- Render 배포, CORS 설정, 상태 확인 API

### Phase 4. AI 전략 변환

상태: **완료**

- OpenAI Client 분리
- Structured Outputs 적용
- 자연어를 Strategy Schema로 변환
- 누락값과 가정값 구분
- AI 결과 자동 실행 금지

추가 완료 범위:

- 결과 지표만을 입력으로 사용하는 AI 해석 API
- API 키 공백/줄바꿈 제거와 외부 연결 오류의 안전한 사용자 메시지
- 단일 종목 조건에 KOSPI 등 별도 지수를 신호 종목으로 지정하는 교차자산 조건 파싱과, 신호 종목이 분리되지 않았을 때의 확인 요청

### Phase 5. 사용자 확인

상태: **완료**

- 채팅 화면
- 전략 요약 카드
- 기본값 표시
- 수정 기능
- 확정 기능
- 확정 후 전략 버전 저장

추가 완료 범위:

- 전략 초안의 가정, 누락 항목, 경고를 확인 화면에 표시
- 확정 전 실행 차단 및 확정 시 전략 버전 저장
- 확정된 초안 백테스트 실행 요청이 공급원 조회로 채워진 `data_sources`(데이터 출처)를 포함해도 거부되지 않도록 수정 — 이전에는 CSV·데모 데이터로만 실행이 성공하고, 실제 시장 데이터 공급원으로 조회한 뒤 실행하면 422로 거부되는 버그가 있었음
- 화면마다 있던 마케팅성 설명 문단 제거, 자명하거나 중복되는 안내 문장 정리, 기능 힌트는 상시 노출 텍스트 대신 툴팁(`title`)으로 이동 — 가정·경고 목록과 Buy & Hold 데이터 기준 안내처럼 결과 신뢰성에 필요한 문구는 유지

### Phase 6. 결과 화면

상태: **완료**

- 주요 지표 카드
- 자산곡선
- 벤치마크 비교
- 낙폭 차트
- 거래 내역
- AI 결과 설명

추가 완료 범위:

- 성과/낙폭 차트, Buy & Hold 비교, 재현용 데이터 해시, 거래 원장

### Phase 7. 전략 보관함

상태: **완료**

- 전략 목록
- 전략 버전
- 결과 비교
- 전략 복제
- 재실행

추가 완료 범위:

- 전략 초안, 버전, 백테스트 실행 결과를 Neon PostgreSQL에 영속 저장
- 결과 비교와 기존 실행 결과 불러오기

### Phase 8. 영속성 및 운영 검증

상태: **완료**

목표: 배포 환경에서도 전략 이력과 실행 결과가 안정적으로 보존되는지 검증한다.

완료 범위:

- Render API와 Neon PostgreSQL 연결
- `strategy_drafts`, `strategy_versions`, `backtest_runs` 테이블 자동 생성
- `/health`에서 현재 데이터베이스 백엔드 확인
- Cloudflare Pages에서 생성한 전략 초안, 확정 버전, 실행 결과가 Neon에 실제 저장되는 E2E 검증
- Alembic 기반 스키마 마이그레이션 체계(`alembic.ini`, `migrations/`) 도입. ORM이 없는 구조라 리비전은 수기 raw SQL로 작성하며, 기존 앱 부트스트랩(`initialize_schema`)과 동일하게 `IF NOT EXISTS`를 사용해 이미 운영 중인 DB에 적용해도 안전한 no-op이 되도록 함. 앞으로의 스키마 변경은 이 리비전 체계로 관리
- `scripts/db_data_tool.py`: 현재 설정된 DB(SQLite 또는 Neon)를 대상으로 `strategy_drafts`/`strategy_versions`/`backtest_runs`를 테이블 단위로 선택해 JSON으로 내보내고(export), 다른 DB로 가져올 수 있는(import) 도구. import는 기존 행과 기본키가 겹치면 건너뛰므로 재실행해도 중복 저장되지 않음

### Phase 9. 전략 편집 경험

상태: **완료**

목표: JSON 직접 수정 없이 사용자가 전략을 안전하게 수정할 수 있게 한다.

완료 범위:

- 시작일·종료일, 초기 자본, 수수료율, 목표 비중 합계를 저장 전 즉시 검증
- 슬리피지·세율, 손절·익절·최대 보유기간 편집과 입력 검증
- 원본 대비 기간·자본·비용·비중·위험관리 변경 영향 미리보기
- 종목, 기간, 초기 자본, 진입/청산 규칙을 폼으로 편집
- 수수료, 슬리피지, 세금, 손절/익절, 최대 보유기간 편집
- 수정 즉시 Schema 검증(저장 전 클라이언트 검증 + 저장 시 서버 재검증), 편집 중 실시간 자연어 요약, 영향 경고 갱신
- 자산별 목표 비중과 리밸런싱 주기(주간·월간·분기) 편집, 백테스트 엔진이 선택된 주기의 첫 공통 거래일에 리밸런싱

### Phase 10. 다중 자산 포트폴리오 고도화

상태: **완료 (조건별 목표 포트폴리오 폼 편집 UI는 예정)**

목표: ALLOCATION_REBALANCE를 일반적인 다중 자산 포트폴리오 규칙으로 확장한다.

완료 범위:

- 조건별 목표 포트폴리오와 현금 비중: `conditional_target_allocations`로 조건(교차자산 조건 포함)에 따라 대체 목표 비중 세트를 적용하고, 어느 조건도 맞지 않으면 기본 `target_allocations`로 대체. AI 파싱과 백엔드 검증 지원. 채팅으로는 요청 가능하나 폼 편집 UI는 아직 없음
- 리밸런싱 비용, 최소 주문 단위, 비중 허용 오차: `rebalance.rebalance_cost`(리밸런싱 1회당 고정비용, 실제로 거래가 발생한 회차에만 부과), `rebalance.min_order_lot`(주문 수량을 이 단위의 배수로 내림), `rebalance.weight_tolerance`(기존 보유 종목의 비중이 목표와 이 오차 이내면 리밸런싱 생략, 최초 매수에는 적용하지 않음) — Schema·엔진·전략 편집 폼까지 반영
- 자산별 데이터 누락 및 상장폐지 데이터에 대한 명시적 실행 거절: 종목 데이터가 요청 종료일보다 10일 넘게 일찍 끝나거나 시작일보다 10일 넘게 늦게 시작하면 공통 거래일 교집합으로 조용히 줄이지 않고 실행을 거절
- 다중 자산 거래 원장과 자산별 성과 기여도: `BacktestResult.symbol_attribution`(종목별 거래 횟수·손익 합계·총수익률 기여도·평균 보유일)을 API 응답과 결과 화면에 노출, 거래 내역 표에 종목 열 추가

### Phase 11. 시장 데이터 확장

상태: **진행 중**

목표: 미국 주식 외 시장을 추가하고 데이터의 출처와 재현성을 강화한다.

완료 조건:

- 개인 사용 단계에서 미국 주식·ETF 일봉 OHLCV는 `yfinance`, 한국 주식·ETF 일봉 OHLCV는 `pykrx`로 조회 **완료**
- 다자산 전환·리밸런싱 전략도 각 공급원 또는 CSV에서 종목별 데이터를 받아 공통 거래일로 정렬 **완료**
- 단일 종목뿐 아니라 다자산 전략에도 종목별 CSV 업로드 지원 **완료**
- `yfinance`의 조정주가 설정과 `pykrx`의 가격 조정 기준을 결과 화면·데이터 버전에 명시 **완료**
- 공급원, 조정 방식, 해시, 수집 시각을 데이터 버전과 실행 결과에 고정 **완료**
- 시장별 심볼 형식 검증: `pykrx`는 6자리 KRX 종목 코드, 미국 공급원은 허용된 티커 문자만 수락 **완료**
- `yfinance`와 `pykrx` 기반 종목 검색 및 선택 **완료**
- FMP는 개인용 기본 공급원이 아니라, 상용 데이터 품질·가용성이 필요해질 때 추가하는 선택 공급원으로 유지

개인용 데이터 사용 원칙:

- `yfinance`는 Yahoo Finance 데이터 이용 약관의 개인·연구 목적 범위 안에서만 사용하며, 데이터 재배포나 상용 서비스의 기본 공급원으로 사용하지 않는다.
- 공급원 응답 실패, 상장폐지, 거래정지 가능성, 누락 공통 거래일은 임의 보정하지 않고 실행 전 사용자에게 명시한다. **완료**

### Phase 12. 안정성 및 사용자 계정

상태: **진행 중 (운영 안정성 완료, 사용자 계정은 보류)**

목표: 다수 사용자가 사용할 수 있는 운영 안정성과 전략 소유권을 추가한다. 로그인·전략 소유권은 서비스를 실제로 여러 사용자에게 열 시점에 다시 논의하기로 하고 우선 보류.

완료 범위:

- 중복 실행 방지: 같은 초안(draft_id)에 대한 백테스트 실행 요청이 진행 중일 때 동시에 다시 요청하면 409로 거절 (`ExecutionGuard`, 단일 Render 인스턴스의 동기 실행 구조를 전제로 한 in-process 락)
- 실행 상태 관리: 백테스트 실행이 실패하면 이전에는 아무 흔적도 남기지 않고 에러만 반환했지만, 이제 `backtest_failures` 테이블에 실패 사유·초안·전략 버전을 기록하고 `GET /api/v1/strategies/{id}/failures`로 조회 가능
- API 오류 응답 표준화: `ValueError`/`HTTPException`뿐 아니라 엔진 내부에서 발생할 수 있는 예기치 못한 예외(`KeyError` 등)까지 전역 예외 핸들러로 잡아 항상 동일한 `{code, message, details}` 형태의 500 응답으로 변환
- 관측성: 모든 요청에 요청 ID를 부여해 로그와 `X-Request-ID` 응답 헤더에 남기고, `/health`가 실제 DB 연결 여부·버전 정보까지 확인하도록 확장
- 배포 환경 통합 테스트: `tests/integration/`에 앱 전체를 기동해 전체 전략 라이프사이클(파싱→확정→실행→조회)과 헬스체크, 오류 응답 일관성을 검증하는 스모크 테스트 추가
- GitHub Actions CI(`.github/workflows/ci.yml`)로 push·PR마다 백엔드 테스트와 프론트엔드 빌드를 자동 실행

다음 완료 조건 (보류):

- 사용자 인증, 전략 소유권, 사용자별 보관함
- API 키와 사용자 데이터의 접근 제어

---

## 14. Codex 구현 지침

### 기본 원칙

1. 한 번에 전체 서비스를 구현하지 않는다.
2. Phase 1부터 순서대로 구현한다.
3. 각 Phase마다 테스트를 먼저 또는 함께 작성한다.
4. AI가 생성한 Python 코드를 실행하는 기능은 만들지 않는다.
5. 전략 Schema에 없는 지표나 연산자는 실행하지 않는다.
6. 결과 계산과 AI 설명 로직을 분리한다.
7. 도메인 모델을 API 응답으로 직접 반환하지 않는다.
8. Request/Response Schema를 분리한다.
9. 외부 API 호출 코드는 Client 계층에 둔다.
10. DB 접근은 Repository 계층에 둔다.
11. 비즈니스 로직은 Service 계층에 둔다.
12. Route는 요청 검증과 Service 호출만 담당한다.
13. 날짜와 금액 계산에서 float 오차를 고려한다.
14. 미래 데이터 참조 방지 테스트를 반드시 작성한다.
15. 동일 입력의 재현성 테스트를 반드시 작성한다.

### 첫 번째 구현 작업

```text
1. 프로젝트 기본 폴더 생성
2. FastAPI 최소 실행 환경 구성
3. Strategy 관련 Enum 작성
4. Strategy Pydantic Schema 작성
5. 샘플 OHLCV Fixture 작성
6. SMA, EMA, RSI 구현
7. CROSS_ABOVE, CROSS_BELOW 구현
8. 단일 종목 백테스트 엔진 구현
9. 수익률, CAGR, MDD 계산
10. 단위 테스트 작성
```

### 초기에는 구현하지 말 것

- 로그인
- OAuth
- 결제
- 실시간 시세
- 실시간 주문
- WebSocket
- 다종목 포트폴리오
- 재무제표 전략
- AI 결과 해설
- 전략 최적화
- 복잡한 작업 큐
- Redis

초기 실행은 동기 방식으로 구현해도 됩니다.

백테스트 실행 시간이 길어질 때 Worker와 Queue를 추가합니다.

---

## 15. 테스트 요구사항

### Indicator Test

- SMA 값 검증
- EMA 값 검증
- RSI 값 검증
- 데이터 부족 시 NaN 처리
- 잘못된 기간 입력 처리

### Signal Test

- CROSS_ABOVE 발생일 검증
- CROSS_BELOW 발생일 검증
- 단순 비교 조건 검증
- AND 조건 검증
- OR 조건 검증

### Execution Test

- 신호 다음 거래일 시가 체결
- 마지막 거래일 신호 미체결
- 잔액 부족 시 주문 거절
- 수수료 반영
- 슬리피지 반영
- 중복 매수 제한

### Metrics Test

- 누적수익률
- CAGR
- MDD
- 변동성
- 샤프지수
- 승률
- 거래 횟수

### Regression Test

고정된 샘플 데이터와 고정된 전략을 사용해 결과가 변경되지 않는지 검사합니다.

```text
sample_sma_cross_strategy
expected_total_return
expected_trade_count
expected_max_drawdown
```

---

## 16. MVP 완료 기준

다음 조건을 모두 만족하면 MVP 1차 완료로 봅니다.

- 자연어로 단일 종목 전략을 입력할 수 있다.
- AI가 전략을 JSON Schema로 변환한다.
- 누락된 조건과 기본값이 구분되어 표시된다.
- 사용자가 확인하기 전에는 실행되지 않는다.
- SMA, EMA, RSI 전략을 실행할 수 있다.
- 다음 거래일 시가 체결이 적용된다.
- 수수료와 슬리피지가 반영된다.
- 누적수익률, CAGR, MDD, 승률, 거래 횟수가 계산된다.
- 전체 거래 내역을 조회할 수 있다.
- 전략 버전과 데이터 버전을 저장한다.
- 같은 입력과 데이터로 재실행 시 같은 결과가 나온다.
- 실행 실패 시 구체적인 오류를 반환한다.

---

## 17. 최종 원칙

```text
AI는 자연어를 전략으로 번역한다.
Validator는 전략이 실행 가능한지 판단한다.
사용자는 실행 전에 전략을 확인한다.
Compiler는 전략을 엔진 명령으로 변환한다.
Backtest Engine은 고정된 규칙으로 계산한다.
AI는 계산된 결과만 설명한다.
```

절대로 다음 구조를 사용하지 않습니다.

```text
사용자 입력
→ AI가 Python 코드 생성
→ 생성된 코드 실행
```

반드시 다음 구조를 사용합니다.

```text
사용자 입력
→ AI가 제한된 Strategy JSON 생성
→ Schema 검증
→ 사용자 확인
→ 사전에 구현된 Backtest Engine 실행
```
