"""
seed_data.py
────────────────────────────────────────────────────────
업로드된 공매도 엑셀(KRX 다운로드)과 수동 주가 데이터를
합쳐서 data/263750.json 초기 시드를 생성합니다.

이후부터는 GitHub Actions(collector.py)가 자동 업데이트.

실행:
    pip install pykrx pandas openpyxl
    python seed_data.py --excel data_1817_20260519.xlsx
"""

import os
import sys
import json
import argparse
import pandas as pd
from datetime import datetime

TICKER       = "263750"
TOTAL_SHARES = 64_250_000
OUT_PATH     = "data/263750.json"

# ── 수동 주가 데이터 (차트 + 검색 기반) ──────────────────
PRICE_MAP = {
    "2025-05-16": 38500, "2025-06-02": 37000, "2025-07-10": 42000,
    "2025-08-13": 35000, "2025-09-17": 31000, "2025-10-15": 30500,
    "2025-11-12": 33000, "2025-12-05": 34000, "2025-12-30": 37400,
    "2026-01-02": 39800, "2026-01-30": 57200, "2026-02-13": 47200,
    "2026-02-19": 52900, "2026-02-27": 51400,
    "2026-03-10": 65500, "2026-03-11": 61500, "2026-03-12": 60100,
    "2026-03-13": 65300, "2026-03-16": 67600, "2026-03-17": 64000,
    "2026-03-18": 63200, "2026-03-19": 46000,
    "2026-03-20": 48100, "2026-03-23": 42100, "2026-03-24": 39800,
    "2026-03-25": 49500, "2026-03-26": 51200, "2026-03-27": 56700,
    "2026-03-30": 65600, "2026-03-31": 69000,
    "2026-04-01": 77400, "2026-04-02": 67900, "2026-04-03": 63700,
    "2026-04-06": 61600, "2026-04-07": 57400, "2026-04-08": 57200,
    "2026-04-09": 56500, "2026-04-10": 55300,
    "2026-04-13": 57900, "2026-04-14": 57100, "2026-04-15": 56000,
    "2026-04-16": 56300, "2026-04-17": 53800,
    "2026-04-20": 54200, "2026-04-21": 54300, "2026-04-22": 56700,
    "2026-04-23": 55400, "2026-04-24": 57100,
    "2026-04-27": 60300, "2026-04-28": 59900, "2026-04-29": 60100,
    "2026-04-30": 57200,
    "2026-05-04": 58500, "2026-05-06": 54900, "2026-05-07": 53400,
    "2026-05-08": 52600, "2026-05-11": 52600,
    "2026-05-12": 52800, "2026-05-13": 53600, "2026-05-14": 50100,
    "2026-05-15": 47200, "2026-05-18": 45800,
}


def load_excel(path: str) -> pd.DataFrame:
    """KRX 공매도 잔고 엑셀 로드"""
    df = pd.read_excel(path, header=0)

    # 컬럼 자동 감지
    col_names = []
    for col in df.columns:
        s = str(col).strip()
        col_names.append(s)

    df.columns = col_names

    # 날짜 컬럼 찾기
    date_col = None
    for c in df.columns:
        try:
            sample = df[c].dropna().iloc[0]
            pd.to_datetime(sample)
            date_col = c
            break
        except Exception:
            continue

    if date_col is None:
        # 첫 번째 컬럼을 날짜로 가정
        date_col = df.columns[0]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df = df.set_index(date_col).sort_index()

    # 공매도량 / 잔고 컬럼 감지
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    # KRX 형식: [공매도수량, ..., 순보유잔고수량, ...]
    # 보통 4번째가 잔고, 1번째가 당일 공매도
    short_col   = numeric_cols[0] if len(numeric_cols) > 0 else None
    balance_col = numeric_cols[3] if len(numeric_cols) > 3 else (
                  numeric_cols[-1] if numeric_cols else None)

    print(f"  날짜컬럼: {date_col}")
    print(f"  당일공매도컬럼: {short_col}")
    print(f"  잔고컬럼: {balance_col}")

    out = pd.DataFrame(index=df.index)
    if short_col:
        out["short_vol"] = pd.to_numeric(df[short_col], errors="coerce")
    if balance_col:
        out["balance"]   = pd.to_numeric(df[balance_col], errors="coerce")

    return out.dropna()


def build_merged(short_df: pd.DataFrame) -> pd.DataFrame:
    price_df = pd.DataFrame(
        list(PRICE_MAP.items()), columns=["date", "close"]
    )
    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df = price_df.set_index("date")

    df = short_df.join(price_df, how="left")

    # 파생
    df["balance_m"]   = df["balance"] / 10000
    df["short_k"]     = df["short_vol"] / 1000
    df["ratio"]       = df["balance"] / TOTAL_SHARES * 100
    df["balance_chg"] = df["balance_m"].diff()
    df["bal_5ma"]     = df["balance_m"].rolling(5).mean()
    df["price_5ma"]   = df["close"].rolling(5).mean()
    df["price_20ma"]  = df["close"].rolling(20).mean()

    return df


def to_json(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    records = []
    for dt, row in df.iterrows():
        if pd.isna(row.get("close")):
            continue
        records.append({
            "date":        dt.strftime("%Y-%m-%d"),
            "close":       int(row["close"]),
            "volume":      0,   # 시드에는 거래량 없음 → 0
            "short_vol":   round(float(row["short_k"]),   1),
            "balance":     round(float(row["balance_m"]),  2),
            "ratio":       round(float(row["ratio"]),      3),
            "balance_chg": round(float(row["balance_chg"])
                                 if pd.notna(row["balance_chg"]) else 0, 2),
            "bal_5ma":     round(float(row["bal_5ma"])
                                 if pd.notna(row["bal_5ma"])  else 0, 2),
            "price_5ma":   round(float(row["price_5ma"])
                                 if pd.notna(row["price_5ma"]) else 0, 0),
            "price_20ma":  round(float(row["price_20ma"])
                                 if pd.notna(row["price_20ma"])else 0, 0),
        })

    meta = {
        "ticker":       TICKER,
        "name":         "펄어비스",
        "total_shares": TOTAL_SHARES,
        "updated_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records":      records,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 저장 완료: {OUT_PATH}  ({len(records)}일치)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True, help="KRX 공매도 엑셀 경로")
    args = parser.parse_args()

    print(f"엑셀 로드: {args.excel}")
    short_df = load_excel(args.excel)
    print(f"  공매도 데이터: {len(short_df)}일")

    df = build_merged(short_df)
    to_json(df)


if __name__ == "__main__":
    main()
