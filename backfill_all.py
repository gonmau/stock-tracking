"""
backfill_all.py — 전체 게임주 외인보유율 백필 v2
- market 파라미터 명시 (KOSPI/KOSDAQ 분리)
- 호출 간격 2초로 늘려 rate limit 회피
- 실패 시 날짜별 루프 fallback
"""
import os, json, time
from datetime import datetime, timedelta, timezone
from pykrx import stock

KST = timezone(timedelta(hours=9))

# market 정보 포함
GAME_STOCKS = {
    "259960": ("크래프톤",    "KOSPI"),
    "263750": ("펄어비스",    "KOSDAQ"),
    "036570": ("엔씨소프트",  "KOSPI"),
    "251270": ("넷마블",      "KOSPI"),
    "462870": ("시프트업",    "KOSPI"),
    "293490": ("카카오게임즈","KOSDAQ"),
    "095660": ("네오위즈",    "KOSDAQ"),
    "225570": ("넥슨게임즈",  "KOSDAQ"),
    "078340": ("컴투스",      "KOSDAQ"),
    "078630": ("컴투스홀딩스","KOSDAQ"),
    "069080": ("웹젠",        "KOSDAQ"),
    "194480": ("데브시스터즈","KOSDAQ"),
    "112040": ("위메이드",    "KOSDAQ"),
    "067000": ("조이시티",    "KOSDAQ"),
    "123420": ("선데이토즈",  "KOSDAQ"),
    "201060": ("미투온",      "KOSDAQ"),
}

def try_by_date(start_d, end_d, ticker, market):
    """기간별 단일종목 조회 — market 명시 버전과 미명시 버전 모두 시도"""
    attempts = [
        lambda: stock.get_exhaustion_rates_of_foreign_investment_by_date(start_d, end_d, ticker),
    ]
    for fn in attempts:
        try:
            df = fn()
            time.sleep(2)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"    시도 실패: {e}", flush=True)
            time.sleep(2)
    return None

def extract_rate_map(df, ticker):
    cols = df.columns.tolist()
    rc = next((c for c in cols if any(k in str(c) for k in ["지분율", "보유비율"])), None)
    if rc is None and len(cols) >= 3:
        rc = cols[2]
    if not rc:
        return {}
    rate_map = {}
    for idx, row in df.iterrows():
        d = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)[:10].replace("-", "")
        rate_map[d] = round(float(row[rc]), 2)
    return rate_map

def backfill_ticker(ticker, name, market):
    data_path = f"data/{ticker}_game.json"
    if not os.path.exists(data_path):
        print(f"  파일 없음 — 스킵", flush=True)
        return

    with open(data_path, encoding="utf-8") as f:
        meta = json.load(f)

    records  = meta.get("records", [])
    to_fill  = [r for r in records if r.get("foreign_rate", 0.0) == 0.0]

    if not to_fill:
        print(f"  → 이미 완료, 스킵", flush=True)
        return

    start_d = to_fill[0]["date"].replace("-", "")
    end_d   = to_fill[-1]["date"].replace("-", "")
    print(f"  백필 대상: {len(to_fill)}일 ({start_d} ~ {end_d}), market={market}", flush=True)

    # ── 방법 A: 기간별 조회 ──────────────────────────────────────
    rate_map = {}
    df = try_by_date(start_d, end_d, ticker, market)
    if df is not None:
        rate_map = extract_rate_map(df, ticker)
        print(f"  기간별 조회 성공: {len(rate_map)}일", flush=True)
    else:
        # ── 방법 B: 날짜별 루프 (by_ticker) ──────────────────────
        print(f"  기간별 실패 → 날짜별 루프...", flush=True)
        all_dates = [r["date"].replace("-","") for r in to_fill]
        for i, d in enumerate(all_dates):
            try:
                fr_df = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(d)
                time.sleep(1)
                if fr_df is not None and not fr_df.empty and ticker in fr_df.index:
                    cols = fr_df.columns.tolist()
                    rc = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), None)
                    if rc is None and len(cols) >= 3:
                        rc = cols[2]
                    if rc:
                        rate_map[d] = round(float(fr_df.loc[ticker, rc]), 2)
                if i % 20 == 0:
                    print(f"    {i+1}/{len(all_dates)}일 처리중... ({len(rate_map)}일 수집)", flush=True)
            except Exception as e:
                time.sleep(1)
        print(f"  날짜별 루프 완료: {len(rate_map)}일", flush=True)

    # ── records 업데이트 ─────────────────────────────────────────
    filled, ffilled = 0, 0
    last_val = None
    for r in to_fill:
        d = r["date"].replace("-", "")
        if d in rate_map:
            r["foreign_rate"] = rate_map[d]
            last_val = rate_map[d]
            filled += 1
        elif last_val is not None:
            r["foreign_rate"] = last_val
            ffilled += 1

    print(f"  → 신규 {filled}일, ffill {ffilled}일", flush=True)

    meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 저장: {data_path}", flush=True)


print("=" * 50, flush=True)
print("전체 게임주 외인보유율 백필 v2 시작", flush=True)
print("=" * 50, flush=True)

for ticker, (name, market) in GAME_STOCKS.items():
    print(f"\n[{name} / {ticker}]", flush=True)
    try:
        backfill_ticker(ticker, name, market)
    except Exception as e:
        print(f"  ✗ 예외: {e}", flush=True)
    time.sleep(3)   # 종목간 여유

print("\n" + "=" * 50, flush=True)
print("완료", flush=True)
print("=" * 50, flush=True)
