#!/usr/bin/env python3
"""
Agmarknet / CEDA Price & Arrivals Ingestion & Cleaning Script.

Accepts Agmarknet bulk CSV schema:
- Prices: date, state, district, market, commodity, variety, grade, min_price, max_price, modal_price
- Arrivals: date, market, commodity, arrivals_tonnes

Cleans data without look-ahead leakage:
- Normalizes dates and market names.
- Removes duplicates, retaining modal average.
- Fills small missing gaps (e.g., Sunday APMC closures, <=3 days) using strictly PAST forward-fill.
- Never interpolates from future dates.
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np

def clean_agmarknet_prices(prices_path: str, output_path: str) -> pd.DataFrame:
    print(f"Reading Agmarknet price data from {prices_path}...")
    df = pd.read_csv(prices_path)

    required_cols = ["date", "market", "commodity", "modal_price"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required Agmarknet price column: {col}")

    # Parse dates robustly
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Clean text columns
    df["market"] = df["market"].astype(str).str.strip()
    df["commodity"] = df["commodity"].astype(str).str.strip().str.capitalize()
    
    # Numeric price conversion
    for col in ["min_price", "max_price", "modal_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop zero or negative prices
    df = df[df["modal_price"] > 0]

    # Deduplicate: if multiple grades/varieties recorded on same day, take median modal price
    grouped = df.groupby(["date", "market", "commodity"]).agg({
        "modal_price": "median",
        "min_price": "min" if "min_price" in df.columns else lambda x: np.nan,
        "max_price": "max" if "max_price" in df.columns else lambda x: np.nan,
        "state": "first" if "state" in df.columns else lambda x: "Maharashtra",
        "district": "first" if "district" in df.columns else lambda x: "Pune",
        "variety": "first" if "variety" in df.columns else lambda x: "Standard",
        "grade": "first" if "grade" in df.columns else lambda x: "FAQ",
    }).reset_index()

    # Sort strictly by time to prevent any temporal leakage
    grouped = grouped.sort_values(["commodity", "market", "date"]).reset_index(drop=True)

    # Gap-filling with strictly historical forward-fill (max 3 days for weekend APMC closure)
    filled_frames = []
    for (comm, mkt), sub_df in grouped.groupby(["commodity", "market"]):
        sub_df = sub_df.copy()
        sub_df["dt"] = pd.to_datetime(sub_df["date"])
        sub_df = sub_df.set_index("dt")
        
        # Reindex to full daily range
        full_idx = pd.date_range(sub_df.index.min(), sub_df.index.max(), freq="D")
        reindexed = sub_df.reindex(full_idx)
        
        # Strictly forward fill up to 3 days (NO BACKWARD FILL to avoid lookahead leakage)
        reindexed["modal_price"] = reindexed["modal_price"].ffill(limit=3)
        reindexed["min_price"] = reindexed["min_price"].ffill(limit=3)
        reindexed["max_price"] = reindexed["max_price"].ffill(limit=3)
        reindexed["commodity"] = comm
        reindexed["market"] = mkt
        reindexed["state"] = reindexed["state"].ffill()
        reindexed["district"] = reindexed["district"].ffill()
        reindexed["variety"] = reindexed["variety"].ffill()
        reindexed["grade"] = reindexed["grade"].ffill()
        
        reindexed["date"] = reindexed.index.strftime("%Y-%m-%d")
        reindexed = reindexed.dropna(subset=["modal_price"])
        filled_frames.append(reindexed.reset_index(drop=True))

    final_df = pd.concat(filled_frames, ignore_index=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_df.to_csv(output_path, index=False)
    print(f"Successfully cleaned prices saved to {output_path} ({len(final_df):,} rows)")
    return final_df

def clean_agmarknet_arrivals(arrivals_path: str, output_path: str) -> pd.DataFrame:
    print(f"Reading Agmarknet arrivals data from {arrivals_path}...")
    df = pd.read_csv(arrivals_path)

    required_cols = ["date", "market", "commodity", "arrivals_tonnes"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required Agmarknet arrivals column: {col}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["market"] = df["market"].astype(str).str.strip()
    df["commodity"] = df["commodity"].astype(str).str.strip().str.capitalize()
    df["arrivals_tonnes"] = pd.to_numeric(df["arrivals_tonnes"], errors="coerce").fillna(0.0)

    # Aggregate total arrivals per market/commodity/date
    grouped = df.groupby(["date", "market", "commodity"])["arrivals_tonnes"].sum().reset_index()
    grouped = grouped.sort_values(["commodity", "market", "date"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    grouped.to_csv(output_path, index=False)
    print(f"Successfully cleaned arrivals saved to {output_path} ({len(grouped):,} rows)")
    return grouped

def main():
    parser = argparse.ArgumentParser(description="Clean Agmarknet/CEDA historical datasets without look-ahead leakage")
    parser.add_argument("--prices-in", type=str, required=True, help="Path to raw prices CSV")
    parser.add_argument("--prices-out", type=str, required=True, help="Path to output cleaned prices CSV")
    parser.add_argument("--arrivals-in", type=str, default="", help="Path to raw arrivals CSV")
    parser.add_argument("--arrivals-out", type=str, default="", help="Path to output cleaned arrivals CSV")
    args = parser.parse_args()

    clean_agmarknet_prices(args.prices_in, args.prices_out)
    if args.arrivals_in and args.arrivals_out:
        clean_agmarknet_arrivals(args.arrivals_in, args.arrivals_out)

if __name__ == "__main__":
    main()
