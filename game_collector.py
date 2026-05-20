"""
game_collector.py
GitHub Actions에서 collector.py 직후 실행
pykrx로 게임주 전종목 주가 + 공매도 수집 → data/{ticker}_game.json 저장

기존 collector.py / data/263750.json 과 완전히 독립적으로 동작
"""

import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

# ───────────────────────────────────────────
# 종목 정의
# ───────────────────────────────────────────
GAME_STOCKS = {
    "259960": {"name": "크래프톤",            "shares": 44_039_000},
    "263750": {"name": "펄어비스",            "shares": 64_250_000},
    "036570": {"name": "엔씨소프트",          "shares": 21_954_022},
    "251270": {"name": "넷마블",              "shares": 84_739_137},
    "462870": {"name": "시프트업",            "shares": 50_000_000},
    "293490": {"name": "카카오게임즈",        "shares": 134_986_390},
    "095660": {"name": "네오위즈",            "shares": 18_652_100},
    "225570": {"name": "넥슨게임즈",          "shares": 58_718_164},
    "078340": {"name": "컴투스",              "shares": 11_367_920},
    "078630": {"name": "게임빌(컴투스홀딩스)","shares": 7_000_000},
    "069080": {"name": "웹젠",               "shares": 30_098_760},
    "194480": {"name": "데브시스터즈",        "shares": 12_988_480},
    "112040": {"name": "위메이드",            "shares": 37_600_000},
    "067000": {"name": "조이시티",            "shares": 27_000_000},
    "123420": {"name": "선데이토즈",          "shares": 14_030_000},
    "201060": {"name": "미투온",              "shares": 20_000_000},
}

DAYS_BACK = 365  # 최초 수집 시 1년치


def get_dates():
    end   = datetime.today() - timedelta(days=2)   # T+2 반영 (기존 collector.py 동일)
    start = end - timedelta(days=DAYS_BACK)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def get_incremental_dates(existing_path: str):
    """기존 JSON이 있으면 마지막 날짜 기준 +5일 겹쳐서 증분 수집"""
    if not os.path.exists(existing_path):
        return get_dates()
    try:
        with open(existing_path, encoding="utf-8") as f:
            meta = json.load(f)
        records = meta.get("records", [])
        if not records:
            return get_dates()
        last_date = datetime.strptime(records[-1]["date"], "%Y-%m-%d")
        start = last_date - timedelta(days=5)   # 겹침 여유
        end   = datetime.today() - timedelta(days=2)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    except Exception:
        return get_dates()


def fetch_ticker(ticker: str, name: str, total_shares: int, data_path: str):
    start, end = get_incremental_dates(data_path)
    print(f"\n[{name} / {ticker}] 수집 기간: {start} ~ {end}")

    # 주가
    try:
        price_df = stock.get_market_ohlcv_by_date(start, end, ticker)
        time.sleep(1)
    except Exception as e:
        print(f"  ✗ 주가 수집 실패: {e}")
        return None

    price_df = price_df[["종가", "거래량"]].rename(
        columns={"종가": "close", "거래량": "volume"}
    )

    # 공매도
    try:
        short_df = stock.get_shorting_status_by_date(start, end, ticker)
        time.sleep(1)
    except Exception as e:
        print(f"  ✗ 공매도 수집 실패: {e}")
        short_df = pd.DataFrame()

    # 공매도 컬럼 자동 감지 (기존 collector.py 로직 동일)
    if not short_df.empty:
        print(f"  공매도 컬럼 목록: {list(short_df.columns)}")
        rename_map = {}
        for col in short_df.columns:
            col_s = str(col).strip()
            if any(k in col_s for k in ["공매도량", "공매도 수량", "공매도수량", "공매도"]) \
                    and "금액" not in col_s and "비중" not in col_s and "short_vol" not in rename_map.values():
                rename_map[col] = "short_vol"
            elif any(k in col_s for k in ["잔고수량", "잔고 수량", "보유잔고", "잔고"]) \
                    and "금액" not in col_s and "비중" not in col_s and "balance" not in rename_map.values():
                rename_map[col] = "balance"
            elif "비중" in col_s and "ratio_pct" not in rename_map.values():
                rename_map[col] = "ratio_pct"

        short_df = short_df.rename(columns=rename_map)
        numeric_cols = short_df.select_dtypes(include="number").columns.tolist()
        if "short_vol" not in short_df.columns and len(numeric_cols) >= 1:
            short_df = short_df.rename(columns={numeric_cols[0]: "short_vol"})
        if "balance" not in short_df.columns and len(numeric_cols) >= 4:
            short_df = short_df.rename(columns={numeric_cols[3]: "balance"})
        elif "balance" not in short_df.columns and len(numeric_cols) >= 2:
            short_df = short_df.rename(columns={numeric_cols[-1]: "balance"})

        available = [c for c in ["short_vol", "balance", "ratio_pct"] if c in short_df.columns]
        df = price_df.join(short_df[available], how="left")
    else:
        df = price_df.copy()
        df["short_vol"] = 0
        df["balance"]   = 0

    df = df.fillna(0)

    # 파생 컬럼
    df["balance_m"]   = df["balance"] / 10000
    df["short_k"]     = df["short_vol"] / 1000
    df["ratio_calc"]  = df["balance"] / total_shares * 100 if total_shares else 0
    df["balance_chg"] = df["balance_m"].diff()
    df["bal_5ma"]     = df["balance_m"].rolling(5).mean()
    df["price_5ma"]   = df["close"].rolling(5).mean()
    df["price_20ma"]  = df["close"].rolling(20).mean()

    return df


def to_records(df: pd.DataFrame) -> list:
    records = []
    for dt, row in df.iterrows():
        records.append({
            "date":        dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
            "close":       int(row["close"]),
            "volume":      int(row["volume"]),
            "short_vol":   round(float(row["short_k"]),   1),
            "balance":     round(float(row["balance_m"]), 2),
            "ratio":       round(float(row["ratio_calc"]), 3),
            "balance_chg": round(float(row["balance_chg"]) if pd.notna(row["balance_chg"]) else 0, 2),
            "bal_5ma":     round(float(row["bal_5ma"])    if pd.notna(row["bal_5ma"])    else 0, 2),
            "price_5ma":   round(float(row["price_5ma"])  if pd.notna(row["price_5ma"])  else 0, 0),
            "price_20ma":  round(float(row["price_20ma"]) if pd.notna(row["price_20ma"]) else 0, 0),
        })
    return records


def upsert_json(data_path: str, new_records: list, ticker: str, name: str, total_shares: int):
    """기존 JSON과 병합 — 날짜 기준 중복 제거, 최신 우선"""
    existing_records = []
    if os.path.exists(data_path):
        try:
            with open(data_path, encoding="utf-8") as f:
                old_meta = json.load(f)
            existing_records = old_meta.get("records", [])
        except Exception:
            pass

    # 날짜 기준 딕셔너리 merge (신규 우선)
    merged = {r["date"]: r for r in existing_records}
    for r in new_records:
        merged[r["date"]] = r

    final_records = sorted(merged.values(), key=lambda x: x["date"])

    meta = {
        "ticker":       ticker,
        "name":         name,
        "total_shares": total_shares,
        "updated_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records":      final_records,
    }

    os.makedirs("data", exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 저장: {data_path} (전체 {len(final_records)}일치, 신규 {len(new_records)}건)")


def main():
    print("=" * 55)
    print("게임주 전종목 수집 시작")
    print("=" * 55)

    errors = []

    for ticker, info in GAME_STOCKS.items():
        name         = info["name"]
        total_shares = info["shares"]
        data_path    = f"data/{ticker}_game.json"

        try:
            df = fetch_ticker(ticker, name, total_shares, data_path)
            if df is None or df.empty:
                print(f"  ✗ {name}: 데이터 없음")
                errors.append(ticker)
                continue

            new_records = to_records(df)
            upsert_json(data_path, new_records, ticker, name, total_shares)

        except Exception as e:
            print(f"  ✗ {name} ({ticker}) 예외: {e}")
            errors.append(ticker)

        time.sleep(2)  # 종목 간 KRX 부하 방지

    print("\n" + "=" * 55)
    print(f"수집 완료 | 성공: {len(GAME_STOCKS) - len(errors)}/{len(GAME_STOCKS)}")
    if errors:
        print(f"실패 티커: {errors}")
    print("=" * 55)


if __name__ == "__main__":
    main()
