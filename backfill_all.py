"""
backfill_all.py — 전체 게임주 외인보유율 백필
get_exhaustion_rates_of_foreign_investment_by_date(start, end, ticker) 사용
종목당 API 1회 호출 → 전체 약 2~3분
"""
import os, json, time
from datetime import datetime, timedelta, timezone
from pykrx import stock

KST = timezone(timedelta(hours=9))

GAME_STOCKS = {
    "259960": "크래프톤",
    "263750": "펄어비스",
    "036570": "엔씨소프트",
    "251270": "넷마블",
    "462870": "시프트업",
    "293490": "카카오게임즈",
    "095660": "네오위즈",
    "225570": "넥슨게임즈",
    "078340": "컴투스",
    "078630": "컴투스홀딩스",
    "069080": "웹젠",
    "194480": "데브시스터즈",
    "112040": "위메이드",
    "067000": "조이시티",
    "123420": "선데이토즈",
    "201060": "미투온",
}

def backfill_ticker(ticker, name):
    data_path = f"data/{ticker}_game.json"
    if not os.path.exists(data_path):
        print(f"  파일 없음: {data_path} — 스킵")
        return

    with open(data_path, encoding="utf-8") as f:
        meta = json.load(f)

    records = meta.get("records", [])
    to_fill = [r for r in records if r.get("foreign_rate", 0.0) == 0.0]

    if not to_fill:
        print(f"  → 이미 완료, 스킵")
        return

    start_d = to_fill[0]["date"].replace("-", "")
    end_d   = to_fill[-1]["date"].replace("-", "")
    print(f"  백필 대상: {len(to_fill)}일 ({start_d} ~ {end_d})")

    rate_map = {}
    try:
        df = stock.get_exhaustion_rates_of_foreign_investment_by_date(start_d, end_d, ticker)
        time.sleep(1)
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            rc = next((c for c in cols if any(k in str(c) for k in ["지분율", "보유비율"])), None)
            if rc is None and len(cols) >= 3:
                rc = cols[2]
            if rc:
                for idx, row in df.iterrows():
                    d = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)[:10].replace("-", "")
                    rate_map[d] = round(float(row[rc]), 2)
    except Exception as e:
        print(f"  API 실패: {e}")

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

    print(f"  → 신규 {filled}일, ffill {ffilled}일")

    meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 저장: {data_path}")


print("=" * 50)
print("전체 게임주 외인보유율 백필 시작")
print("=" * 50)

for ticker, name in GAME_STOCKS.items():
    print(f"\n[{name} / {ticker}]")
    try:
        backfill_ticker(ticker, name)
    except Exception as e:
        print(f"  ✗ 예외: {e}")

print("\n" + "=" * 50)
print("완료")
print("=" * 50)
