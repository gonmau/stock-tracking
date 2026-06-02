"""
backfill_263750.py — 펄어비스(263750) 외인보유율 백필
KRX_ID / KRX_PW 환경변수 필요
"""
import os, json, time
from datetime import datetime, timedelta, timezone
from pykrx import stock

KST    = timezone(timedelta(hours=9))
TICKER = "263750"

# ── KRX 로그인 ──────────────────────────────────────────────────────
krx_id = os.environ.get("KRX_ID", "")
krx_pw = os.environ.get("KRX_PW", "")
if krx_id and krx_pw:
    try:
        stock.get_market_ohlcv("20260101", "20260101", "005930")  # 세션 초기화용 더미 호출
        from pykrx.website import krx as krx_login
        krx_login.MKD80037().fetch(id=krx_id, pw=krx_pw)
        print("✓ KRX 로그인 성공")
    except Exception as e:
        print(f"⚠ KRX 로그인 시도 실패: {e}")
else:
    print("⚠ KRX_ID/KRX_PW 없음 — 로그인 없이 시도")

time.sleep(1)

# ── 데이터 로드 ─────────────────────────────────────────────────────
data_path = f"data/{TICKER}_game.json"
if not os.path.exists(data_path):
    print(f"파일 없음: {data_path}")
    exit(1)

with open(data_path, encoding="utf-8") as f:
    meta = json.load(f)

records = meta.get("records", [])
to_fill = [r for r in records if r.get("foreign_rate", 0.0) == 0.0]
print(f"백필 대상: {len(to_fill)}일 / 전체 {len(records)}일")

if not to_fill:
    print("모두 채워져 있음")
    exit(0)

start_d = to_fill[0]["date"].replace("-", "")
end_d   = to_fill[-1]["date"].replace("-", "")
print(f"기간: {start_d} ~ {end_d}")

# ── 방법 A: 기간별 단일종목 조회 (가장 빠름) ───────────────────────
rate_map = {}
print(f"\n[A] get_exhaustion_rates_of_foreign_investment_by_date 시도...")
try:
    df = stock.get_exhaustion_rates_of_foreign_investment_by_date(start_d, end_d, TICKER)
    time.sleep(1)
    if df is not None and not df.empty:
        cols = df.columns.tolist()
        print(f"  컬럼: {cols}")
        rc = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), cols[2] if len(cols)>=3 else None)
        if rc:
            for idx, row in df.iterrows():
                d = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)[:10].replace("-","")
                rate_map[d] = round(float(row[rc]), 2)
            print(f"  → {len(rate_map)}일 수집 성공!")
    else:
        print("  빈 결과")
except Exception as e:
    print(f"  실패: {e}")

# ── 방법 B: by_ticker (날짜 단일) 루프 ────────────────────────────
if not rate_map:
    print(f"\n[B] get_exhaustion_rates_of_foreign_investment_by_ticker 날짜 루프 시도...")
    all_dates = [r["date"].replace("-","") for r in to_fill]
    for d in all_dates:
        try:
            df = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(d)
            time.sleep(0.2)
            if df is not None and not df.empty and TICKER in df.index:
                cols = df.columns.tolist()
                print(f"  [{d}] 컬럼: {cols}")  # 첫 성공 시 컬럼 출력
                rc = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), cols[2] if len(cols)>=3 else None)
                if rc:
                    rate_map[d] = round(float(df.loc[TICKER, rc]), 2)
        except Exception as e:
            if len(rate_map) == 0 and all_dates.index(d) < 3:  # 처음 3일만 에러 출력
                print(f"  [{d}] 실패: {e}")
            continue
    print(f"  → {len(rate_map)}일 수집")

# ── records 업데이트 ────────────────────────────────────────────────
filled, ffilled = 0, 0
last_val = None
for r in to_fill:
    d = r["date"].replace("-","")
    if d in rate_map:
        r["foreign_rate"] = rate_map[d]
        last_val = rate_map[d]
        filled += 1
    elif last_val is not None:
        r["foreign_rate"] = last_val
        ffilled += 1

print(f"\n신규 수집: {filled}일, ffill: {ffilled}일")

meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
with open(data_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print(f"✓ 저장 완료: {data_path}")
