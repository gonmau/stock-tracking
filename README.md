# 📊 모의매매 자동 매매 시스템

> pykrx + Naver Finance 기반 한국 주식 자동 모의매매 (NXT 장외 포함)

## 기능

| 항목 | 내용 |
|------|------|
| 자동 실행 | GitHub Actions, 10분 간격 (평일 KST 08:00~20:10) |
| 가격 조회 | Naver Finance 실시간 / NXT 장외가 / pykrx 종가 |
| 매매 전략 | RSI, MA 골든크로스/데드크로스, 복합 |
| 손절/익절 | 설정값 기반 자동 매도 |
| 수수료/세금 | 매매 수수료 + 증권거래세 반영 |
| NXT 거래 | 장 전/후 NXT 장외 가격으로 체결 |
| 알림 | 매매 발생 시 Discord 웹훅 알림 |
| 대시보드 | GitHub Pages HTML 대시보드 |

## 파일 구조

```
stock-tracking/          ← 기존 리포에 추가
├── 모의매매.py
├── 모의매매_dashboard.html   → GitHub Pages index로 사용 가능
├── requirements.txt
├── .github/workflows/
│   └── 모의매매.yml
└── data/
    ├── settings.json       ← 설정 (대시보드에서 편집 가능)
    ├── watchlist.json      ← 감시종목 (대시보드에서 추가/삭제)
    ├── portfolio.json      ← 포트폴리오 상태 (자동 생성)
    ├── trades.json         ← 매매이력 (자동 생성)
    └── summary.json        ← 대시보드용 요약 (자동 생성)
```

## 초기 설정

### 1. GitHub Secrets 추가
`Settings → Secrets → Actions`
```
DISCORD_WEBHOOK   Discord 웹훅 URL
```

### 2. 대시보드 설정
`모의매매_dashboard.html` 상단의 `REPO` 변수를 실제 리포명으로 수정:
```javascript
const REPO = 'gonmau/stock-tracking';  // ← 본인 리포
```

### 3. GitHub Pages 활성화
`Settings → Pages → Branch: main, Folder: / (root)` 또는 `/docs`

### 4. 감시종목 추가
대시보드 상단 **"+ 종목 추가"** 버튼 → GitHub PAT 입력 → 저장

## 매매 전략

| 전략 | 매수 조건 | 매도 조건 |
|------|-----------|-----------|
| `rsi_ma` | RSI < 30 **AND** MA5 > MA20 | RSI > 70 OR MA5 < MA20 OR 손절/익절 |
| `rsi` | RSI < 30 | RSI > 70 OR 손절/익절 |
| `ma` | MA5 > MA20 골든크로스 | MA5 < MA20 데드크로스 OR 손절/익절 |
| `manual` | 자동매매 없음 (대시보드 모니터링만) | 자동매매 없음 |

## 수수료/세금 구조

| 항목 | 기본값 | 설명 |
|------|--------|------|
| 매매 수수료 | 0.015% (0.00015) | 매수/매도 양방향 |
| NXT 추가 수수료 | 0.01% (0.0001) | NXT 장외 추가분 |
| 증권거래세 | 0.18% (0.0018) | 매도 시만 부과 |

## NXT 거래

`use_nxt: true` 설정 시 NXT 운영 시간에도 자동 매매:
- 장 전: KST 08:00~09:00
- 장 후: KST 15:40~20:00

Naver Finance `overMarketPriceInfo` API로 실시간 NXT 가격 조회.

## Discord 알림 예시

```
📈 모의매매 매수 [NXT]
종목: 펄어비스 (263750)
가격: 23,450원 × 42주 = 985,000원
수수료: 148원 | 총비용: 985,198원
사유: RSI=28.3(과매도) + 골든크로스(MA5=23,100>MA20=22,800)
잔여 현금: 9,014,802원
```

## 대시보드 기능

- **포지션**: 현재 보유 종목, 평가금액, 평가손익, 비중
- **매매이력**: 전체/매수/매도 필터, CSV 다운로드
- **감시종목**: 종목 추가/삭제, 전략 변경, 활성화 토글
- **차트**: 자산 추이, 누적 손익, 포트폴리오 구성 파이차트
- **설정**: 수수료/세금/손절익절/RSI/MA 파라미터 실시간 수정

## 주의사항

- 모의매매이므로 실제 주문 없음
- KRX 공휴일은 별도 처리 없음 (API 실패 시 건너뜀)
- NXT 호가는 Naver Finance 제공분에 의존
