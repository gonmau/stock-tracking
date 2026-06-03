"""
backfill_all.py v3
- 6개월 단위로 나눠서 조회 (KRX 응답 제한 회피)
- 실패 시 3개월 → 1개월 단위로 재시도
"""
import os, json, time, sys
from datetime import datetime, timedelta, timezone
from pykrx import stock

KST = timezone(timedelta(hours=9))

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

def split_periods(start_d, end_d, months=6):
    """날짜 범위를 N개월 단위 청크로 분할"""
    start = datetime.strptime(start_d, "%Y%m%d")
    end   = datetime.strptime(end_d,   "%Y%m%d")
    chunks = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=30*months), end)
        chunks.append((cur.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cur = chunk_end + timedelta(days=1)
    return chunks

def fetch_period(start_d, end_d, ticker):
    """단일 기간 조회, 성공 시 {날짜: 지분율} dict 반환"""
    try:
        df = stock.get_exhaustion_rates_of_foreign_investment_by_date(start_d, end_d, ticker)
        time.sleep(1.5)
        if df is None or df.empty:
            return None
        cols = df.columns.tolist()
        rc = next((c for c in cols if any(k in str(c) for k in ["지분율","보유비율"])), None)
        if rc is None and len(cols) >= 3:
            rc = cols[2]
        if not rc:
            return None
        result = {}
        for idx, row in df.iterrows():
            d = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)[:10].replace("-","")
            result[d] = round(float(row[rc]), 2)
        return result
    except Exception as e:
        print(f"    fetch_period({start_d}~{end_d}): {e}", flush=True)
        time.sleep(1.5)
        return None

def backfill_ticker(ticker, name, market):
    data_path = f"data/{ticker}_game.json"
    if not os.path.exists(data_path):
        print(f"  파일 없음 — 스킵", flush=True)
        return

    with open(data_path, encoding="utf-8") as f:
        meta = json.load(f)

    records = meta.get("records", [])
    to_fill = [r for r in records if r.get("foreign_rate", 0.0) == 0.0]

    if not to_fill:
        print(f"  → 이미 완료, 스킵", flush=True)
        return

    start_d = to_fill[0]["date"].replace("-","")
    end_d   = to_fill[-1]["date"].replace("-","")
    print(f"  백필 대상: {len(to_fill)}일 ({start_d} ~ {end_d})", flush=True)

    rate_map = {}

    # 6개월 → 3개월 → 1개월 순으로 청크 크기 줄여가며 시도
    for months in [6, 3, 1]:
        chunks = split_periods(start_d, end_d, months=months)
        print(f"  [{months}개월 단위] {len(chunks)}개 청크 조회...", flush=True)
        rate_map = {}
        for i, (cs, ce) in enumerate(chunks):
            result = fetch_period(cs, ce, ticker)
            if result:
                rate_map.update(result)
                print(f"    청크 {i+1}/{len(chunks)} ({cs}~{ce}): {len(result)}일 수집", flush=True)
            else:
                print(f"    청크 {i+1}/{len(chunks)} ({cs}~{ce}): 실패", flush=True)

        success_rate = len(rate_map) / len(to_fill) if to_fill else 0
        print(f"  → {months}개월 단위 결과: {len(rate_map)}/{len(to_fill)}일 ({success_rate:.0%})", flush=True)

        if success_rate >= 0.8:   # 80% 이상 수집되면 충분
            break

    # records 업데이트
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

    print(f"  → 신규 {filled}일, ffill {ffilled}일", flush=True)

    meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 저장: {data_path}", flush=True)


print("=" * 50, flush=True)
print("전체 게임주 외인보유율 백필 v3", flush=True)
print("=" * 50, flush=True)

for ticker, (name, market) in GAME_STOCKS.items():
    print(f"\n[{name} / {ticker}]", flush=True)
    try:
        backfill_ticker(ticker, name, market)
    except Exception as e:
        print(f"  ✗ 예외: {e}", flush=True)
    time.sleep(2)

print("\n" + "=" * 50, flush=True)
print("완료", flush=True)
print("=" * 50, flush=True)
