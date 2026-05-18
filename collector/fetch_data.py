import os
import sqlite3
import pandas as pd
import numpy as np

from datetime import datetime, timedelta
from pykrx import stock

TICKER = "263750"
TICKER_NAME = "펄어비스"

DB_PATH = "data/short_interest.db"

TOTAL_SHARES = 64250000


def get_dates(days_back=180):
    end = datetime.today() - timedelta(days=2)
    start = end - timedelta(days=days_back)

    return (
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d")
    )


def fetch():

    start, end = get_dates()

    price_df = stock.get_market_ohlcv_by_date(
        start,
        end,
        TICKER
    )

    short_df = stock.get_shorting_status_by_date(
        start,
        end,
        TICKER
    )

    price_df = price_df[["종가", "거래량"]].rename(
        columns={
            "종가": "close",
            "거래량": "volume"
        }
    )

    rename_map = {}

    for col in short_df.columns:

        if "공매도" in col and "금액" not in col and "비중" not in col:
            rename_map[col] = "short_vol"

        elif "잔고" in col and "금액" not in col and "비중" not in col:
            rename_map[col] = "balance"

    short_df = short_df.rename(columns=rename_map)

    df = price_df.join(
        short_df[list(rename_map.values())],
        how="inner"
    )

    df = df.dropna()

    return df


def calculate_indicators(df):

    df["short_ratio"] = (
        df["short_vol"] / df["volume"]
    ) * 100

    df["balance_ratio"] = (
        df["balance"] / TOTAL_SHARES
    ) * 100

    df["price_return"] = df["close"].pct_change() * 100

    df["balance_change"] = df["balance"].diff()

    df["volume_change"] = df["volume"].pct_change() * 100

    # 공매도 압박 점수
    df["pressure_score"] = (
        (df["balance_change"] / 10000) * 0.5
        + df["short_ratio"] * 0.3
        - df["price_return"] * 0.2
    )

    # 숏커버 점수
    df["short_cover_score"] = (
        (-df["balance_change"] / 10000)
        * df["price_return"]
    )

    # Z-score 이상 탐지
    mean = df["short_ratio"].rolling(20).mean()
    std = df["short_ratio"].rolling(20).std()

    df["short_zscore"] = (
        df["short_ratio"] - mean
    ) / std

    # 이동평균
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()

    return df


def save_to_db(df):

    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    df.to_sql(
        "pearlabyss_short",
        conn,
        if_exists="replace",
        index=True
    )

    conn.close()


if __name__ == "__main__":

    print("데이터 수집 중...")

    df = fetch()

    df = calculate_indicators(df)

    save_to_db(df)

    print("DB 저장 완료")
