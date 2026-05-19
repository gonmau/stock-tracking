"""
collector.py
GitHub Actions에서 매일 실행 → data/263750.json 업데이트
pykrx로 주가 + 공매도 잔고 수집
"""

import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

TICKER      = "263750"
DATA_PATH   = "data/263750.json"
TOTAL_SHARES = 64_250_000  # 발행주식수
DAYS_BACK   = 365          # 1년치 수집


def get_dates():
    end   = datetime.today() - timedelta(days=2)   # T+2 반영
    start = end - timedelta(days=DAYS_BACK)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch():
    start, end = get_dates()
    print(f"수집 기간: {start} ~ {end}")

    price_df = stock.get_market_ohlcv_by_date(start, end, TICKER)
    time.sleep(1)
    short_df = stock.get_shorting_status_by_date(start, end, TICKER)
    time.sleep(1)

    price_df = price_df[["종가", "거래량"]].rename(
        columns={"종가": "close", "거래량": "volume"}
    )

    # 공매도 컬럼 정규화
    rename_map = {}
    for col in short_df.columns:
        col_s = col.strip()
        if "공매도" in col_s and "금액" not in col_s and "비중" not in col_s:
            rename_map[col] = "short_vol"
        elif "잔고" in col_s and "금액" not in col_s and "비중" not in col_s:
            rename_map[col] = "balance"
        elif "비중" in col_s:
            rename_map[col] = "ratio_pct"
    short_df = short_df.rename(columns=rename_map)

    df = price_df.join(
        short_df[[c for c in ["short_vol","balance","ratio_pct"] if c in short_df.columns]],
        how="inner"
    ).dropna()

    # 파생 컬럼
    df["balance_m"]   = df["balance"] / 10000
    df["short_k"]     = df["short_vol"] / 1000
    df["ratio_calc"]  = df["balance"] / TOTAL_SHARES * 100
    df["balance_chg"] = df["balance_m"].diff()
    df["bal_5ma"]     = df["balance_m"].rolling(5).mean()
    df["price_5ma"]   = df["close"].rolling(5).mean()
    df["price_20ma"]  = df["close"].rolling(20).mean()

    return df


def to_json(df):
    records = []
    for dt, row in df.iterrows():
        records.append({
            "date":        dt.strftime("%Y-%m-%d"),
            "close":       int(row["close"]),
            "volume":      int(row["volume"]),
            "short_vol":   round(float(row["short_k"]),  1),   # 천주
            "balance":     round(float(row["balance_m"]), 2),   # 만주
            "ratio":       round(float(row["ratio_calc"]), 3),
            "balance_chg": round(float(row["balance_chg"]) if pd.notna(row["balance_chg"]) else 0, 2),
            "bal_5ma":     round(float(row["bal_5ma"])   if pd.notna(row["bal_5ma"])   else 0, 2),
            "price_5ma":   round(float(row["price_5ma"]) if pd.notna(row["price_5ma"]) else 0, 0),
            "price_20ma":  round(float(row["price_20ma"])if pd.notna(row["price_20ma"])else 0, 0),
        })

    meta = {
        "ticker":      TICKER,
        "name":        "펄어비스",
        "total_shares": TOTAL_SHARES,
        "updated_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records":     records,
    }

    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {DATA_PATH} ({len(records)}일치)")


if __name__ == "__main__":
    df = fetch()
    to_json(df)
