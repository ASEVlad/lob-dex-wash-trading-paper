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
    token_id: str,
    token_usd_const: float,
    eth_usd_const: float | None = None,
    price_is_token_in_eth: bool | None = None,
    ether_address: str = "0x0000000000000000000000000000000000000000",
) -> None:
    """
    Build the 'post-merge' table the R pipeline expects, using constant prices.

    Inputs
    ------
    df: DataFrame with columns:
        - price : float64   (optional; used only if price_is_token_in_eth=True)
        - size  : float64   (token amount)
        - time  : datetime64[ns] (tz-aware or tz-naive in UTC)
        - seller: int/str
        - buyer : int/str
    token_id:     identifier for the (non-ETH) token (symbol or address)
    token_usd_const: constant USD price for that token (applied to all rows)
    eth_usd_const:   optional constant ETH/USD (only needed if you also want ETH amounts)
    price_is_token_in_eth:
        - If True: use df['price'] as token-in-ETH.
        - If False/None: ignore df['price'] for ETH math; use eth_usd_const if provided.

    Output CSV columns (matches R 'merge_*' output shape):
        date, cut, blockNumber, timestamp, transactionHash,
        eth_buyer, eth_seller, ether, token,
        trade_amount_eth, trade_amount_dollar, trade_amount_token, token_price_in_eth
    """
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
    df["timestamp"] = (df["time"].view("int64") // 10**9).astype("int64")

    # start-of-day (UTC) seconds, used by the R code as 'cut'
    df["cut"] = (df["timestamp"] // 86_400) * 86_400

    # simple monotone blockNumber (only used for ordering in one place)
    df["blockNumber"] = df["timestamp"].astype("int64")

    # transactionHash: make a deterministic synthetic id per row
    df["transactionHash"] = df.apply(make_txhash, axis=1)

    # addresses as strings (R handles strings better than large ints)
    df["eth_buyer"] = df["seller"].astype(str)   # note: we set like this so that when ether=FALSE the R code flips back
    df["eth_seller"] = df["buyer"].astype(str)

    # constant token id & ether address
    df["token"] = str(token_id)
    df["ether"] = ether_address

    # trade amounts
    df["trade_amount_token"] = df["size"].astype(float)

    # token price in ETH (constant or from df['price'])
    token_price_in_eth = np.nan
    if price_is_token_in_eth is True and "price" in df.columns:
        # take from the dataframe (row-specific). If you want a constant, overwrite below.
        df["token_price_in_eth"] = df["price"].astype(float)
    elif (eth_usd_const is not None) and (token_usd_const is not None):
        # constant derived from USDs
        token_price_in_eth = float(token_usd_const) / float(eth_usd_const)
        df["token_price_in_eth"] = token_price_in_eth
    else:
        df["token_price_in_eth"] = np.nan  # optional field

    # trade_amount_eth (only useful if you plan to run ether=TRUE in R; harmless otherwise)
    if "token_price_in_eth" in df.columns and df["token_price_in_eth"].notna().any():
        df["trade_amount_eth"] = df["trade_amount_token"] * df["token_price_in_eth"]
    else:
        df["trade_amount_eth"] = 0.0

    # trade_amount_dollar using constant token USD price (your chosen quick method)
    df["trade_amount_dollar"] = df["trade_amount_token"] * float(token_usd_const)

    # nice 'date' column for summaries (UTC date)
    df["date"] = pd.to_datetime(df["cut"], unit="s", utc=True).dt.date

    # final column order (mirrors R)
    cols = [
        "date",
        "cut",
        "blockNumber",
        "timestamp",
        "transactionHash",
        "eth_buyer",
        "eth_seller",
        "ether",
        "token",
        "trade_amount_eth",
        "trade_amount_dollar",
        "trade_amount_token",
        "token_price_in_eth",
    ]
    out = df[cols].sort_values(["token", "blockNumber", "timestamp"]).reset_index(drop=True)

    # write CSV
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"Saved prepared post-merge trades to: {out_csv}")