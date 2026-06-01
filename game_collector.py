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
from datetime import datetime, timedelta, timezone
from pykrx import stock

# GitHub Actions는 UTC 기준 실행 → KST(+9) 보정 필수
KST = timezone(timedelta(hours=9))

def now_kst():
    return datetime.now(KST).replace(tzinfo=None)

# ───────────────────────────────────────────
# 종목 정의
# ───────────────────────────────────────────
GAME_STOCKS = {
    "259960": {"name": "크래프톤",            "shares": 44_039_000},
    "263750": {"name": "펄어비스",            "shares": 64_250_000},  # KOSDAQ
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
    end   = now_kst() - timedelta(days=2)   # T+2 반영 (KST 기준)
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
        end   = now_kst() - timedelta(days=2)   # KST 기준
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    except Exception:
        return get_dates()


def fetch_ticker(ticker: str, name: str, total_shares: int, data_path: str, info: dict = None):
    start, end = get_incremental_dates(data_path)
    print(f"\n[{name} / {ticker}] 수집 기간: {start} ~ {end}")

    # 주가
    try:
        price_df = stock.get_market_ohlcv_by_date(start, end, ticker)
        time.sleep(1)
    except Exception as e:
        print(f"  ✗ 주가 수집 실패: {e}")
        return None

    if price_df is None or price_df.empty:
        print(f"  ✗ 주가 데이터 없음: {ticker}")
        return None

    # 거래대금 컬럼 있으면 같이 가져옴
    avail_cols = [c for c in ["종가","거래량","거래대금"] if c in price_df.columns]
    if "종가" not in price_df.columns:
        print(f"  ✗ 종가 컬럼 없음: {list(price_df.columns)}")
        return None
    price_df = price_df[avail_cols].rename(
        columns={"종가": "close", "거래량": "volume", "거래대금": "trading_value"}
    )
    if "trading_value" not in price_df.columns:
        price_df["trading_value"] = 0

    # 공매도
    try:
        short_df = stock.get_shorting_status_by_date(start, end, ticker)
        time.sleep(1)
        if short_df is None:
            short_df = pd.DataFrame()
    except Exception as e:
        print(f"  ⚠ 공매도 수집 실패 (공매도 미대상 종목일 수 있음): {e}")
        short_df = pd.DataFrame()

    # 공매도 컬럼 자동 감지 (기존 collector.py 로직 동일)
    if not short_df.empty:
        print(f"  공매도 컬럼 목록: {list(short_df.columns)}")
        rename_map = {}
        for col in short_df.columns:
            col_s = str(col).strip()
            # 공매도 거래량 (pykrx가 반환하는 컬럼명 "거래량"이 곧 공매도량)
            if col_s == "거래량" and "short_vol" not in rename_map.values():
                rename_map[col] = "short_vol"
            elif any(k in col_s for k in ["공매도량","공매도 수량","공매도수량"]) \
                    and "금액" not in col_s and "비중" not in col_s and "short_vol" not in rename_map.values():
                rename_map[col] = "short_vol"
            # 잔고수량 (로그에서 확인된 컬럼명)
            elif col_s in ["잔고수량","잔고 수량","보유잔고"] and "balance" not in rename_map.values():
                rename_map[col] = "balance"
            elif "잔고" in col_s and "금액" not in col_s and "비중" not in col_s \
                    and "balance" not in rename_map.values():
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
        print(f"  공매도 join 컬럼: {available}")
        df = price_df.join(short_df[available], how="left")
        if "balance" in df.columns:
            print(f"  join 후 balance 최신: {df['balance'].tail(3).tolist()}")
        else:
            print("  ✗ join 후 balance 컬럼 없음")
    else:
        df = price_df.copy()
        df["short_vol"] = 0
        df["balance"]   = 0

    # 공매도 잔고는 KRX T-3~4 지연 → 최신 몇 행이 NaN → ffill로 보완
    for col in ["short_vol", "balance"]:
        if col in df.columns:
            df[col] = df[col].ffill().fillna(0)

    df = df.fillna(0)
    if "close" not in df.columns:
        print(f"  ✗ close 컬럼 없음 — 스킵")
        return pd.DataFrame()

    # 파생 컬럼
    df["balance_m"]   = df["balance"] / 10000
    df["short_k"]     = df["short_vol"] / 1000
    df["ratio_calc"]  = df["balance"] / total_shares * 100 if total_shares else 0
    df["balance_chg"] = df["balance_m"].diff()
    df["bal_5ma"]     = df["balance_m"].rolling(5).mean()
    df["price_5ma"]   = df["close"].rolling(5).mean()
    df["price_20ma"]  = df["close"].rolling(20).mean()
    # 거래대금 억원 / 회전율
    df["trading_value_b"] = (df["trading_value"] / 1e8).round(1) if "trading_value" in df.columns else 0
    df["turnover"] = (df["volume"] / total_shares * 100).round(3) if total_shares else 0
    df["vol_20ma"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = (df["volume"] / df["vol_20ma"]).round(2)   # 거래량 20일 대비 배율
    # 숏커버링 신호: 잔고 감소 + 주가 상승
    price_chg = df["close"].pct_change() * 100
    df["short_cover_signal"] = (
        (df["balance_chg"] < -1) & (price_chg > 0)
    ).astype(int)
    # 공매도 공세 신호: 잔고 증가 + 주가 하락
    df["short_attack_signal"] = (
        (df["balance_chg"] > 1) & (price_chg < 0)
    ).astype(int)

    # 외국인 보유비율
    # pykrx 실제 API: get_exhaustion_rates_of_foreign_investment(date, market)
    # → 전 종목 DataFrame 반환, index = ticker
    def _fetch_foreign_rate(date_str: str, ticker: str) -> float | None:
        """date_str: 'YYYYMMDD' 형식. 해당 날짜 외인지분율 반환, 실패 시 None"""
        for market in ["ALL", "KOSPI", "KOSDAQ"]:
            try:
                fr_df = stock.get_exhaustion_rates_of_foreign_investment(date_str, market=market)
                time.sleep(0.5)
                if fr_df is None or fr_df.empty:
                    continue
                if ticker not in fr_df.index:
                    continue
                fr_cols = fr_df.columns.tolist()
                rate_col = next(
                    (c for c in fr_cols if any(k in str(c) for k in ["지분율", "보유비율", "외국인비율"])),
                    None
                )
                if rate_col is None and len(fr_cols) >= 3:
                    rate_col = fr_cols[2]
                if rate_col:
                    val = float(fr_df.loc[ticker, rate_col])
                    print(f"  ✓ 외인보유율 수집 완료 ({date_str}, {market}): {val:.2f}%")
                    return val
            except Exception as e:
                print(f"  ⚠ get_exhaustion_rates_of_foreign_investment({date_str}, {market}): {e}")
                continue
        return None

    try:
        # 최신 날짜(end)부터 최대 5 영업일 전까지 역순으로 시도 (휴일·지연 대비)
        end_dt = datetime.strptime(end, "%Y%m%d")
        fr_val = None
        for delta in range(0, 6):
            candidate = (end_dt - timedelta(days=delta)).strftime("%Y%m%d")
            fr_val = _fetch_foreign_rate(candidate, ticker)
            if fr_val is not None:
                break
        df["foreign_rate"] = round(fr_val, 2) if fr_val is not None else 0.0
        if fr_val is None:
            print(f"  ⚠ 외인보유율 최종 실패: 6일 역순 조회 모두 실패")
    except Exception as e:
        print(f"  ⚠ 외인보유율 예외: {e}")
        df["foreign_rate"] = 0.0

    if "foreign_rate" not in df.columns:
        df["foreign_rate"] = 0.0

    # 시가총액
    try:
        mc_df = stock.get_market_cap_by_date(start, end, ticker)
        time.sleep(1)
        if not mc_df.empty:
            mc_cols = mc_df.columns.tolist()
            cap_col = next((c for c in mc_cols if "시가총액" in str(c)), None)
            if cap_col:
                mc_df = mc_df[[cap_col]].rename(columns={cap_col: "market_cap"})
                df = df.join(mc_df["market_cap"], how="left")
                df["market_cap"] = df["market_cap"].ffill().fillna(0)
                # 억원 단위로 변환
                df["market_cap_b"] = (df["market_cap"] / 1e8).round(0)
    except Exception as e:
        print(f"  ⚠ 시가총액 수집 실패: {e}")
        df["market_cap_b"] = 0.0

    if "market_cap_b" not in df.columns:
        df["market_cap_b"] = 0.0

    # PER / PBR / EPS / BPS
    try:
        fn_df = stock.get_market_fundamental_by_date(start, end, ticker)
        time.sleep(1)
        if not fn_df.empty:
            fn_cols = fn_df.columns.tolist()
            per_col = next((c for c in fn_cols if "PER" in str(c).upper()), None)
            pbr_col = next((c for c in fn_cols if "PBR" in str(c).upper()), None)
            div_col = next((c for c in fn_cols if "DIV" in str(c).upper() or "배당" in str(c)), None)
            rename = {}
            if per_col: rename[per_col] = "per"
            if pbr_col: rename[pbr_col] = "pbr"
            if div_col: rename[div_col] = "div_yield"
            if rename:
                fn_df = fn_df[list(rename.keys())].rename(columns=rename)
                df = df.join(fn_df, how="left")
                for col in ["per","pbr","div_yield"]:
                    if col in df.columns:
                        df[col] = df[col].ffill().fillna(0).round(2)
    except Exception as e:
        print(f"  ⚠ 펀더멘털 수집 실패: {e}")

    for col in ["per","pbr","div_yield"]:
        if col not in df.columns:
            df[col] = 0.0

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
            "foreign_rate": round(float(row["foreign_rate"]) if pd.notna(row.get("foreign_rate", 0)) else 0, 2),
            "market_cap_b": int(row["market_cap_b"]) if pd.notna(row.get("market_cap_b", 0)) else 0,
            "per":       round(float(row["per"])       if pd.notna(row.get("per", 0))       else 0, 2),
            "pbr":       round(float(row["pbr"])       if pd.notna(row.get("pbr", 0))       else 0, 2),
            "div_yield": round(float(row["div_yield"]) if pd.notna(row.get("div_yield", 0)) else 0, 2),
            "trading_value_b":     round(float(row.get("trading_value_b", 0)), 1),
            "turnover":            round(float(row.get("turnover", 0)), 3),
            "vol_ratio":           round(float(row.get("vol_ratio", 0))  if pd.notna(row.get("vol_ratio", 0))  else 0, 2),
            "short_cover_signal":  int(row.get("short_cover_signal", 0)),
            "short_attack_signal": int(row.get("short_attack_signal", 0)),
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
        "updated_at":   now_kst().strftime("%Y-%m-%d %H:%M"),
        "records":      final_records,
    }

    os.makedirs("data", exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 저장: {data_path} (전체 {len(final_records)}일치, 신규 {len(new_records)}건)")


# ───────────────────────────────────────────
# 지수 수집 (KOSPI / KOSDAQ)
# ───────────────────────────────────────────
INDICES = {
    "1001": "KOSPI",
    "2001": "KOSDAQ",
}

def get_incremental_dates_index(data_path):
    if not os.path.exists(data_path):
        end   = now_kst() - timedelta(days=2)
        start = end - timedelta(days=DAYS_BACK)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    try:
        with open(data_path, encoding="utf-8") as f:
            meta = json.load(f)
        records = meta.get("records", [])
        if not records:
            end   = now_kst() - timedelta(days=2)
            start = end - timedelta(days=DAYS_BACK)
            return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        last_date = datetime.strptime(records[-1]["date"], "%Y-%m-%d")
        start = last_date - timedelta(days=5)
        end   = now_kst() - timedelta(days=2)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    except Exception:
        end   = now_kst() - timedelta(days=2)
        start = end - timedelta(days=DAYS_BACK)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_index(index_code, name):
    data_path = f"data/index_{name.lower()}.json"
    start, end = get_incremental_dates_index(data_path)
    print(f"\n[지수 {name} / {index_code}] 수집 기간: {start} ~ {end}")
    try:
        df = stock.get_index_ohlcv_by_date(start, end, index_code)
        time.sleep(1)
    except Exception as e:
        print(f"  ✗ {name} 지수 수집 실패: {e}")
        return
    if df.empty:
        print(f"  ✗ {name} 지수 데이터 없음")
        return

    close_col = next((c for c in df.columns if "종가" in str(c)), df.columns[0])
    df = df[[close_col]].rename(columns={close_col: "close"})
    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()

    new_records = []
    for dt, row in df.iterrows():
        new_records.append({
            "date":  dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
            "close": round(float(row["close"]), 2),
            "ma5":   round(float(row["ma5"])  if pd.notna(row["ma5"])  else 0, 2),
            "ma20":  round(float(row["ma20"]) if pd.notna(row["ma20"]) else 0, 2),
        })

    existing_records = []
    if os.path.exists(data_path):
        try:
            with open(data_path, encoding="utf-8") as f:
                old_meta = json.load(f)
            existing_records = old_meta.get("records", [])
        except Exception:
            pass

    merged = {r["date"]: r for r in existing_records}
    for r in new_records:
        merged[r["date"]] = r
    final_records = sorted(merged.values(), key=lambda x: x["date"])

    meta = {
        "index_code": index_code,
        "name":       name,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "records":    final_records,
    }
    os.makedirs("data", exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 저장: {data_path} (전체 {len(final_records)}일치)")


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
            df = fetch_ticker(ticker, name, total_shares, data_path, info=info)
            if df is None or df.empty:
                print(f"  ✗ {name}: 데이터 없음")
                errors.append(ticker)
                continue

            new_records = to_records(df)
            upsert_json(data_path, new_records, ticker, name, total_shares)

        except Exception as e:
            print(f"  ✗ {name} ({ticker}) 예외: {e}")
            errors.append(ticker)

        time.sleep(2)

    # 지수 수집
    print("\n" + "=" * 55)
    print("지수 수집 (KOSPI / KOSDAQ)")
    print("=" * 55)
    for code, name in INDICES.items():
        try:
            fetch_index(code, name)
        except Exception as e:
            print(f"  ✗ {name} 지수 예외: {e}")
        time.sleep(2)

    print("\n" + "=" * 55)
    print(f"수집 완료 | 성공: {len(GAME_STOCKS) - len(errors)}/{len(GAME_STOCKS)}")
    if errors:
        print(f"실패 티커: {errors}")
    print("=" * 55)


if __name__ == "__main__":
    main()
