"""
backfill_263750.py — 펄어비스(263750) 외인보유율 백필 + API 탐색
"""
import os, json, time
from datetime import datetime, timedelta, timezone
from pykrx import stock

KST  = timezone(timedelta(hours=9))
TICKER = "263750"
NAME   = "펄어비스"

# ── Step 1: 어떤 API가 실제로 동작하는지 확인 ──────────────────────
print("=== API 탐색 ===")
test_end   = (datetime.now(KST) - timedelta(days=2)).strftime("%Y%m%d")
test_start = (datetime.now(KST) - timedelta(days=10)).strftime("%Y%m%d")

# 방법 A: 기간별 단일 종목 조회
print(f"\n[A] get_exhaustion_rates_of_foreign_investment_by_date({test_start}, {test_end}, {TICKER})")
try:
    df_a = stock.get_exhaustion_rates_of_foreign_investment_by_date(test_start, test_end, TICKER)
    print(f"  성공! shape={df_a.shape}, columns={df_a.columns.tolist()}")
    print(df_a.tail(3))
except Exception as e:
    print(f"  실패: {e}")

time.sleep(1)

# 방법 B: 단일 날짜 전종목 (market 없이)
print(f"\n[B] get_exhaustion_rates_of_foreign_investment({test_end})")
try:
    df_b = stock.get_exhaustion_rates_of_foreign_investment(test_end)
    print(f"  성공! shape={df_b.shape}, columns={df_b.columns.tolist()}")
    if TICKER in df_b.index:
        print(f"  {TICKER} 행: {df_b.loc[TICKER].to_dict()}")
except Exception as e:
    print(f"  실패: {e}")

time.sleep(1)

# 방법 C: market="KOSDAQ" 명시
print(f"\n[C] get_exhaustion_rates_of_foreign_investment({test_end}, market='KOSDAQ')")
try:
    df_c = stock.get_exhaustion_rates_of_foreign_investment(test_end, market="KOSDAQ")
    print(f"  성공! shape={df_c.shape}, columns={df_c.columns.tolist()}")
    if TICKER in df_c.index:
        print(f"  {TICKER} 행: {df_c.loc[TICKER].to_dict()}")
except Exception as e:
    print(f"  실패: {e}")

time.sleep(1)

# 방법 D: get_market_trading_value_by_investor (외국인 매매로 지분율 추정 불가지만 확인용)
print(f"\n[D] pykrx 전체 함수 목록 중 foreign 관련:")
funcs = [f for f in dir(stock) if "foreign" in f.lower() or "exhaust" in f.lower()]
print(f"  {funcs}")


# ── Step 2: 동작하는 API로 백필 ────────────────────────────────────
print("\n=== 백필 시작 ===")
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

all_dates = [r["date"].replace("-", "") for r in to_fill]
start_d = all_dates[0]
end_d   = all_dates[-1]
print(f"기간: {start_d} ~ {end_d}")

# 방법 A 시도: 기간별 단일 종목 조회 (가장 빠름)
rate_map = {}
try:
    df_period = stock.get_exhaustion_rates_of_foreign_investment_by_date(start_d, end_d, TICKER)
    time.sleep(1)
    if df_period is not None and not df_period.empty:
        cols = df_period.columns.tolist()
        print(f"기간별 조회 성공, 컬럼: {cols}")
        rate_col = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), None)
        if rate_col is None and len(cols) >= 3:
            rate_col = cols[2]
        if rate_col:
            for idx, row in df_period.iterrows():
                d = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx).replace("-","")[:8]
                rate_map[d] = round(float(row[rate_col]), 2)
            print(f"→ 기간별 조회로 {len(rate_map)}일 수집 완료")
except Exception as e:
    print(f"기간별 조회 실패: {e} → 날짜별 루프로 fallback")

# 방법 A 실패 시 날짜별 루프 (느리지만 확실)
if not rate_map:
    print("날짜별 루프 시작 (약 1~2분)...")
    for d in all_dates:
        for market in ["KOSDAQ", "ALL"]:   # 펄어비스는 KOSDAQ 먼저
            try:
                fr_df = stock.get_exhaustion_rates_of_foreign_investment(d, market=market)
                time.sleep(0.2)
                if fr_df is not None and not fr_df.empty and TICKER in fr_df.index:
                    cols = fr_df.columns.tolist()
                    rc = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), None)
                    if rc is None and len(cols) >= 3:
                        rc = cols[2]
                    if rc:
                        rate_map[d] = round(float(fr_df.loc[TICKER, rc]), 2)
                        break
            except Exception:
                continue
    print(f"→ 날짜별 루프로 {len(rate_map)}일 수집")

# records에 반영 (rate_map에 없는 날은 ffill)
filled = 0
last_val = None
for r in to_fill:
    d = r["date"].replace("-", "")
    if d in rate_map:
        r["foreign_rate"] = rate_map[d]
        last_val = rate_map[d]
        filled += 1
    elif last_val is not None:
        r["foreign_rate"] = last_val

print(f"신규 수집: {filled}일, ffill: {len(to_fill)-filled}일")

meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
with open(data_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print(f"✓ 저장 완료: {data_path}")
