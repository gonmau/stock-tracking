# 펄어비스(263750) 공매도 트래커

공매도 잔고 추이와 주가를 함께 추적해 위험 구간과 역이용 신호를 자동 감지합니다.

## 구조

```
short-tracker-263750/
├── app.py              # Streamlit 대시보드
├── collector.py        # GitHub Actions 데이터 수집기
├── seed_data.py        # 초기 데이터 시드 생성
├── requirements.txt
├── data/
│   └── 263750.json     # 수집된 데이터 (자동 업데이트)
└── .github/workflows/
    └── collect.yml     # 매일 오전 자동 수집
```

## 설치 & 실행

### 1. GitHub 레포 생성

```bash
git clone https://github.com/your-username/short-tracker-263750
cd short-tracker-263750
```

### 2. 초기 데이터 시드 생성

KRX에서 공매도 잔고 엑셀 다운로드 후:

```bash
pip install pykrx pandas openpyxl
python seed_data.py --excel data_1817_20260519.xlsx
```

`data/263750.json` 생성됨 → 커밋 & 푸시

### 3. GitHub Secrets 설정

레포 Settings → Secrets → Actions:

| 이름 | 값 |
|------|----|
| `KRX_ID` | KRX 로그인 ID |
| `KRX_PW` | KRX 로그인 PW |

> KRX 계정 없으면 [data.krx.co.kr](https://data.krx.co.kr) 에서 무료 가입

### 4. Streamlit Cloud 배포

1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 레포 연결
3. Main file: `app.py`
4. Deploy

### 5. 앱 사이드바 설정

- GitHub 사용자명 입력
- 레포명 입력
- 완료

## 데이터 자동 수집

GitHub Actions가 **평일 오전 8시 (UTC)** = KST 오후 5시 장 마감 후 자동 실행.

수동 실행: Actions 탭 → `공매도 데이터 수집` → `Run workflow`

## 신호 기준 (과거 데이터 기반)

| 잔고 | 신호 | 행동 |
|------|------|------|
| 200만주↑ | 🔴 DANGER | 신규 매수 자제 |
| 150~200만주 | 🟡 WARNING | 잔고 감소 확인 후 진입 |
| 80~150만주 | 🔵 NEUTRAL | 분할매수 가능 |
| 80만주↓ | 🟢 SQUEEZE | 숏커버 반등 기대 |

당일 공매도 200천주↑ → 🔴 ATTACK (당일 추가 하락 경계)

## 역이용 신호 자동 감지

- 잔고 10일 최고점 대비 15%↓ 감소 → 상환 진행 중
- 잔고 감소 + 주가 상승 동반 → 숏커버 반등
- 5MA > 20MA 골든크로스 → 추세 전환 가능
- 잔고비율 1.5%↓ → 숏스퀴즈 압력 낮음
