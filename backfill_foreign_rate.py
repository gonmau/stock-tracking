"""
backfill_foreign_rate.py
foreign_rate가 0.0인 과거 records를 pykrx로 채워서 JSON 업데이트
GitHub Actions 수동 트리거(workflow_dispatch)로 1회 실행
"""

import os
import json
import time
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
    "078630": "게임빌(컴투스홀딩스)",
    "069080": "웹젠",
    "194480": "데브시스터즈",
    "112040": "위메이드",
    "067000": "조이시티",
    "123420": "선데이토즈",
    "201060": "미투온",
}

# pykrx 전체 조회 결과를 날짜별로 캐싱 (종목마다 같은 날짜 재호출 방지)
_cache: dict[str, object] = {}   # key: "YYYYMMDD_MARKET"


def fetch_exhaustion(date_str: str) -> object | None:
    """date_str 기준 전체 외인보유율 DataFrame 반환 (캐시 활용)"""
    for market in ["ALL", "KOSPI", "KOSDAQ"]:
        cache_key = f"{date_str}_{market}"
        if cache_key in _cache:
            return _cache[cache_key]
        try:
            df = stock.get_exhaustion_rates_of_foreign_investment(date_str, market=market)
            time.sleep(0.3)
            if df is not None and not df.empty:
                _cache[cache_key] = df
                return df
        except Exception as e:
            print(f"    get_exhaustion({date_str}, {market}): {e}")
    return None


def get_rate_col(df) -> str | None:
    cols = df.columns.tolist()
    rate_col = next(
        (c for c in cols if any(k in str(c) for k in ["지분율", "보유비율", "외국인비율"])),
        None
    )
    if rate_col is None and len(cols) >= 3:
        rate_col = cols[2]
    return rate_col


def backfill_ticker(ticker: str, name: str):
    data_path = f"data/{ticker}_game.json"
    if not os.path.exists(data_path):
        print(f"[{name}] 파일 없음: {data_path}")
        return

    with open(data_path, encoding="utf-8") as f:
        meta = json.load(f)

    records = meta.get("records", [])

    # foreign_rate가 없거나 0.0인 records만 대상
    to_fill = [r for r in records if r.get("foreign_rate", 0.0) == 0.0]
    print(f"\n[{name} / {ticker}] 백필 대상: {len(to_fill)}일 / 전체 {len(records)}일")

    if not to_fill:
        print("  → 모두 채워져 있음, 스킵")
        return

    filled = 0
    last_val = None   # 조회 실패 시 직전값으로 forward fill

    for r in to_fill:
        date_str = r["date"].replace("-", "")
        fr_df = fetch_exhaustion(date_str)

        if fr_df is not None and ticker in fr_df.index:
            rate_col = get_rate_col(fr_df)
            if rate_col:
                val = round(float(fr_df.loc[ticker, rate_col]), 2)
                r["foreign_rate"] = val
                last_val = val
                filled += 1
                continue

        # 조회 실패 → 직전값 유지 (0보다 나음)
        if last_val is not None:
            r["foreign_rate"] = last_val

    print(f"  → {filled}일 신규 수집, {len(to_fill) - filled}일 ffill 처리")

    meta["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 저장 완료: {data_path}")


def main():
    print("=" * 55)
    print("외인보유율 백필 시작")
    print("=" * 55)

    for ticker, name in GAME_STOCKS.items():
        try:
            backfill_ticker(ticker, name)
        except Exception as e:
            print(f"  ✗ {name} ({ticker}) 예외: {e}")
        time.sleep(1)

    print("\n" + "=" * 55)
    print("백필 완료")
    print("=" * 55)


if __name__ == "__main__":
    main()
