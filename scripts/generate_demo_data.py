#!/usr/bin/env python3
"""
Generate deterministic synthetic historical Agmarknet price series, daily arrivals,
and co-op demo lots for HarvestWise (AGR-06).

Features:
- 6 Pune region markets x 4 commodities x 5 years (2020-2024).
- Tomato bimodal arrivals with annual timing drift and heavy-tailed price shocks.
- Inverse price-arrivals dynamics.
- Spatial price correlation across mandis.
- Seeded and 100% reproducible.
- Clearly labelled synthetic dataset with metadata headers.
"""

import os
import json
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

START_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2024, 12, 31)

MARKETS = [
    {"id": "mkt_junnar", "name": "Junnar", "district": "Pune", "price_bias": 0.92, "base_arrivals": 45.0},
    {"id": "mkt_narayangaon", "name": "Narayangaon", "district": "Pune", "price_bias": 0.94, "base_arrivals": 90.0},
    {"id": "mkt_khed", "name": "Khed", "district": "Pune", "price_bias": 0.98, "base_arrivals": 60.0},
    {"id": "mkt_pune", "name": "Pune", "district": "Pune", "price_bias": 1.10, "base_arrivals": 180.0},
    {"id": "mkt_shirur", "name": "Shirur", "district": "Pune", "price_bias": 0.95, "base_arrivals": 50.0},
    {"id": "mkt_baramati", "name": "Baramati", "district": "Pune", "price_bias": 0.97, "base_arrivals": 55.0},
]

COMMODITIES = {
    "Tomato": {
        "variety": "Hybrid / Processing",
        "grade": "FAQ",
        "base_price": 1250.0,
        "price_volatility": 0.45,
        "arrivals_volatility": 0.50,
        "price_elasticity": -0.65,
    },
    "Onion": {
        "variety": "Red / Nasik",
        "grade": "FAQ",
        "base_price": 1600.0,
        "price_volatility": 0.35,
        "arrivals_volatility": 0.40,
        "price_elasticity": -0.55,
    },
    "Potato": {
        "variety": "Jyoti / Table",
        "grade": "FAQ",
        "base_price": 1300.0,
        "price_volatility": 0.25,
        "arrivals_volatility": 0.30,
        "price_elasticity": -0.45,
    },
    "Banana": {
        "variety": "Grand Naine",
        "grade": "FAQ",
        "base_price": 1550.0,
        "price_volatility": 0.20,
        "arrivals_volatility": 0.25,
        "price_elasticity": -0.40,
    },
}

def generate_seasonality(day_of_year: int, year: int, commodity: str) -> float:
    """Computes realistic seasonal multiplier for commodity arrivals."""
    iso_week = int(day_of_year / 7.0) + 1
    
    if commodity == "Tomato":
        # Bimodal arrivals: Peak 1 (weeks 6-14, Feb-Apr), Peak 2 (weeks 40-47, Oct-Nov)
        # Year-to-year drift in timing (+/- 1.5 weeks)
        year_shift = (year % 3 - 1) * 1.5
        peak1 = math.exp(-0.5 * ((iso_week - (10 + year_shift)) / 3.0) ** 2)
        peak2 = math.exp(-0.5 * ((iso_week - (43 + year_shift)) / 3.5) ** 2)
        season = 0.45 + 1.25 * peak1 + 1.10 * peak2
        # Lean season dip in monsoon (July)
        if 26 <= iso_week <= 32:
            season *= 0.60
        return season

    elif commodity == "Onion":
        # Rabi peak arrivals in April-May (weeks 14-22), lean in Sept-Nov (weeks 38-46)
        peak = math.exp(-0.5 * ((iso_week - 18) / 4.0) ** 2)
        trough = math.exp(-0.5 * ((iso_week - 42) / 4.0) ** 2)
        return 0.50 + 1.40 * peak - 0.35 * trough

    elif commodity == "Potato":
        # Peak harvest Jan-March (weeks 3-12)
        peak = math.exp(-0.5 * ((iso_week - 8) / 3.5) ** 2)
        return 0.60 + 1.10 * peak

    elif commodity == "Banana":
        # Relatively stable with moderate post-monsoon surge (weeks 34-44)
        peak = math.exp(-0.5 * ((iso_week - 38) / 6.0) ** 2)
        return 0.75 + 0.45 * peak

    return 1.0

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(script_dir, ".."))
    demo_dir = os.path.join(project_dir, "data", "demo")
    os.makedirs(demo_dir, exist_ok=True)

    print("Generating HarvestWise synthetic Agmarknet price series and arrivals...")

    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    price_records = []
    arrivals_records = []

    # Common macro state shock series (correlated regional movements)
    n_days = len(dates)
    macro_shock = np.random.standard_t(df=4, size=n_days) * 0.08

    for d_idx, current_date in enumerate(dates):
        day_of_year = current_date.timetuple().tm_yday
        year = current_date.year
        date_str = current_date.strftime("%Y-%m-%d")

        for comm_name, comm_cfg in COMMODITIES.items():
            seas = generate_seasonality(day_of_year, year, comm_name)
            
            # Base regional arrivals for this date
            comm_arrivals_shock = np.random.normal(0, comm_cfg["arrivals_volatility"] * 0.20)
            regional_arrivals_factor = max(0.20, seas + comm_arrivals_shock)

            # Base regional price from inverse price-arrivals elasticity
            elasticity = comm_cfg["price_elasticity"]
            log_price_ratio = elasticity * math.log(regional_arrivals_factor)
            price_macro = math.exp(log_price_ratio + macro_shock[d_idx])

            for mkt in MARKETS:
                # Market specific arrivals
                mkt_arrivals_noise = np.random.lognormal(0, 0.15)
                arrivals_tonnes = round(mkt["base_arrivals"] * regional_arrivals_factor * mkt_arrivals_noise, 1)

                # Market specific price with heavy-tailed idiosyncratic noise
                mkt_price_noise = np.random.standard_t(df=4) * 0.04
                modal_price = comm_cfg["base_price"] * price_macro * mkt["price_bias"] * math.exp(mkt_price_noise)
                
                # Boundary checks & integer rounding in Rs/quintal
                modal_price = max(150.0, round(modal_price, 0))
                min_price = round(modal_price * np.random.uniform(0.88, 0.95), 0)
                max_price = round(modal_price * np.random.uniform(1.05, 1.15), 0)

                price_records.append({
                    "date": date_str,
                    "state": "Maharashtra",
                    "district": mkt["district"],
                    "market": mkt["name"],
                    "market_id": mkt["id"],
                    "commodity": comm_name,
                    "variety": comm_cfg["variety"],
                    "grade": comm_cfg["grade"],
                    "min_price": min_price,
                    "max_price": max_price,
                    "modal_price": modal_price,
                    "is_synthetic": True,
                })

                arrivals_records.append({
                    "date": date_str,
                    "market": mkt["name"],
                    "market_id": mkt["id"],
                    "commodity": comm_name,
                    "arrivals_tonnes": arrivals_tonnes,
                    "is_synthetic": True,
                })

    # Save Prices CSV
    df_prices = pd.DataFrame(price_records)
    prices_csv_path = os.path.join(demo_dir, "daily_prices.csv")
    df_prices.to_csv(prices_csv_path, index=False)
    print(f"Saved {len(df_prices):,} price rows to {prices_csv_path}")

    # Save Arrivals CSV
    df_arrivals = pd.DataFrame(arrivals_records)
    arrivals_csv_path = os.path.join(demo_dir, "daily_arrivals.csv")
    df_arrivals.to_csv(arrivals_csv_path, index=False)
    print(f"Saved {len(df_arrivals):,} arrival rows to {arrivals_csv_path}")

    # Generate Co-op Demo Lots (Pune/Junnar rural cluster)
    print("Generating demo co-op pooling open lots...")
    villages = [
        {"name": "Otur", "lat": 19.260, "lon": 73.910},
        {"name": "Alephata", "lat": 19.180, "lon": 74.050},
        {"name": "Manchar", "lat": 19.006, "lon": 73.940},
        {"name": "Narayangaon Rural", "lat": 19.120, "lon": 73.970},
        {"name": "Junnar East", "lat": 19.210, "lon": 73.890},
        {"name": "Rajgurunagar / Khed", "lat": 18.860, "lon": 73.910},
        {"name": "Ghodegaon", "lat": 19.040, "lon": 73.830},
    ]

    farmer_names = [
        "Ramesh Jadhav", "Ananda Shinde", "Suresh Patil", "Dattatray Wagh",
        "Santosh Kale", "Baban Thorat", "Popat Gholap", "Vikas Bankar",
        "Eknath Chaudhari", "Kashinath Dumbre", "Navnath Kurkute", "Sunil Tambe",
        "Pandurang Hande", "Ganesh Mengade", "Sanjay Shete", "Nitin Gunjal",
        "Sachin Bhor", "Amol Sahane", "Mahesh Lande", "Tukaram Gawade",
        "Ashok Phapale", "Yogesh Walunj", "Pradeep Pingale", "Balasaheb Kute",
    ]

    coop_lots = []
    # Seeded reference harvest dates (yesterday and today relative to demo date)
    ref_date = datetime(2024, 10, 28)

    # 1. Specifically create 2 compatible Tomato lots to match the 30 qtl demo user
    # Total pool = 30 (user) + 40 (Ramesh) + 35 (Ananda) = 105 qtl >= 100 qtl MOQ!
    coop_lots.append({
        "lot_id": "lot_demo_01",
        "farmer_name": "Ramesh Jadhav",
        "village": "Otur",
        "district": "Pune",
        "lat": 19.245,
        "lon": 73.905,
        "commodity": "Tomato",
        "variety": "Processing (Abhinav / US-440)",
        "quantity_qtl": 40.0,
        "harvest_date": (ref_date - timedelta(days=1)).strftime("%Y-%m-%d"),
        "grade": "B",
        "is_processing_grade": True,
        "packaging": "crates",
        "willing_to_pool": True,
        "max_pickup_distance_km": 30.0,
        "phone_masked": "+91 98220 *****",
    })

    coop_lots.append({
        "lot_id": "lot_demo_02",
        "farmer_name": "Ananda Shinde",
        "village": "Junnar East",
        "district": "Pune",
        "lat": 19.212,
        "lon": 73.895,
        "commodity": "Tomato",
        "variety": "Processing (Aryaman / Laxmi)",
        "quantity_qtl": 35.0,
        "harvest_date": ref_date.strftime("%Y-%m-%d"),
        "grade": "B",
        "is_processing_grade": True,
        "packaging": "crates",
        "willing_to_pool": True,
        "max_pickup_distance_km": 25.0,
        "phone_masked": "+91 94231 *****",
    })

    # Additional 22 diversified lots across Onion, Potato, Banana, and other Tomatos
    for i, name in enumerate(farmer_names[2:], start=3):
        v = villages[i % len(villages)]
        crop = ["Tomato", "Onion", "Potato", "Banana"][i % 4]
        qtl = float(np.random.choice([20.0, 25.0, 30.0, 45.0, 50.0, 60.0]))
        h_days_ago = int(np.random.choice([0, 1, 2, 3]))
        grade = str(np.random.choice(["A", "B", "C"], p=[0.30, 0.50, 0.20]))

        coop_lots.append({
            "lot_id": f"lot_demo_{i:02d}",
            "farmer_name": name,
            "village": v["name"],
            "district": "Pune",
            "lat": round(v["lat"] + np.random.uniform(-0.02, 0.02), 4),
            "lon": round(v["lon"] + np.random.uniform(-0.02, 0.02), 4),
            "commodity": crop,
            "variety": "Standard Hybrid",
            "quantity_qtl": qtl,
            "harvest_date": (ref_date - timedelta(days=h_days_ago)).strftime("%Y-%m-%d"),
            "grade": grade,
            "is_processing_grade": (crop == "Tomato" and grade in ["A", "B"]),
            "packaging": np.random.choice(["crates", "gunny_bags"]),
            "willing_to_pool": True,
            "max_pickup_distance_km": 30.0,
            "phone_masked": f"+91 98{np.random.randint(100, 999)} *****",
        })

    coop_json_path = os.path.join(demo_dir, "coop_lots.json")
    with open(coop_json_path, "w", encoding="utf-8") as f:
        json.dump({"open_lots": coop_lots, "is_synthetic": True}, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(coop_lots)} demo co-op lots to {coop_json_path}")

    # Generate metadata description file
    meta_path = os.path.join(demo_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "random_seed": RANDOM_SEED,
            "date_range": [START_DATE.strftime("%Y-%m-%d"), END_DATE.strftime("%Y-%m-%d")],
            "markets_count": len(MARKETS),
            "commodities_count": len(COMMODITIES),
            "price_rows": len(df_prices),
            "arrival_rows": len(df_arrivals),
            "coop_lots_count": len(coop_lots),
            "provenance": "Synthetic calibrated to Agmarknet schema and NABCONS (2022) / GIZ (2016) parameters",
            "is_synthetic": True
        }, f, indent=2)
    print("Metadata generated successfully.")

if __name__ == "__main__":
    main()
