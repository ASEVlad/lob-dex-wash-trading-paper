# prepare_postmerge_csv.py
import pandas as pd
import numpy as np
import hashlib
from pathlib import Path

def make_txhash(row: pd.Series) -> str:
    # stable pseudo-hash (not a blockchain txid): hex string
    s = f"{int(row['timestamp'])}|{row['seller']}|{row['buyer']}|{row['size']:.12g}"
    return "tx-" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def prepare_postmerge_csv(
    df: pd.DataFrame,
    out_csv: str,
) -> None:
    df = df.copy()

    # --- time handling (to UTC seconds) ---
    # ensure datetime dtype
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    if df["time"].dt.tz is None:
        # assume already UTC if tz-naive
        df["time"] = df["time"].dt.tz_localize("UTC")
    else:
        df["time"] = df["time"].dt.tz_convert("UTC")

    # integer seconds
    df["timestamp"] = (df["time"].astype("int64") // 10**9).astype("int64")

    # transactionHash: make a deterministic synthetic id per row
    df["transactionHash"] = df.index

    # addresses as strings (R handles strings better than large ints)
    df["buyer_id"] = df["seller"].astype(str)   # note: we set like this so that when ether=FALSE the R code flips back
    df["seller_id"] = df["buyer"].astype(str)

    # trade amounts
    df["trade_amount_token"] = df["size"].astype(float)

    # trade_amount_dollar using constant token USD price (your chosen quick method)
    df["trade_amount_dollar"] = df["trade_amount_token"] * df["price"]

    # final column order (mirrors R)
    cols = [
        "timestamp",
        "transactionHash",
        "buyer_id",
        "seller_id",
        "trade_amount_dollar",
        "trade_amount_token",
    ]
    out = df[cols].sort_values("timestamp").reset_index(drop=True)
    # write CSV
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"Saved prepared post-merge trades to: {out_csv}")