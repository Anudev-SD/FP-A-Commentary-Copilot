"""Turn Financial_Sample.xlsx into account-level monthly P&L CSVs.

Outputs (data/): actual.csv, budget.csv, forecast.csv
Long format: period, segment, country, product, account, amount

Actuals come straight from the spreadsheet. Budget and Forecast do NOT exist in the
source file, so they are SIMULATED here with a fixed random seed (reproducible).
Prior Year is not a file: the app derives it from Actual shifted by 12 months.

Run:  python scripts/prepare_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "Financial_Sample.xlsx"
OUT = ROOT / "data"
SEED = 42
ACCOUNTS = ["Gross Sales", "Discounts", "COGS", "Units Sold"]
KEYS = ["period", "segment", "country", "product"]

# --- Simulation assumptions (documented in README as the evaluation "ground truth") ---
# Budget Gross Sales = Actual / budget_factor. A factor > 1 means the plan was too
# ambitious (actual below budget); < 1 means the plan was conservative (actual beat it).
SEGMENT_BUDGET_FACTOR = {
    "Government": 0.92,
    "Midmarket": 1.00,
    "Channel Partners": 1.03,
    "Enterprise": 1.15,
    "Small Business": 1.00,
}
PLAN_DISCOUNT_RATE = 0.05  # budget assumes a flat 5% of Gross Sales
BUDGET_COGS_RATE_BIAS = {"VTT": 0.96, "Velo": 0.96}  # plan assumed cheaper COGS for these
UNBUDGETED_ROW_SHARE = 0.06  # actual lines with no budget line (new business)
BUDGET_ONLY_ROWS = 40  # budget lines with no actual (deals that never landed)


def load_actuals() -> pd.DataFrame:
    df = pd.read_excel(RAW)
    df.columns = [c.strip() for c in df.columns]
    df["period"] = df["Date"].dt.strftime("%Y-%m")
    df = df.rename(columns={"Segment": "segment", "Country": "country", "Product": "product"})
    g = df.groupby(KEYS, as_index=False)[["Gross Sales", "Discounts", "COGS", "Units Sold"]].sum()
    return g


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    out = df.melt(id_vars=KEYS, value_vars=ACCOUNTS, var_name="account", value_name="amount")
    out["amount"] = out["amount"].round(2)
    return out.sort_values(KEYS + ["account"]).reset_index(drop=True)


def make_budget(a: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    b = a.copy()
    factor = b["segment"].map(SEGMENT_BUDGET_FACTOR).values * rng.lognormal(0, 0.08, len(b))
    b["Gross Sales"] = a["Gross Sales"].values * factor
    b["Units Sold"] = a["Units Sold"].values * factor
    b["Discounts"] = b["Gross Sales"] * PLAN_DISCOUNT_RATE
    cogs_rate = (a["COGS"] / a["Gross Sales"]).values
    cogs_rate = cogs_rate * b["product"].map(lambda p: BUDGET_COGS_RATE_BIAS.get(p, 1.0)).values
    cogs_rate = cogs_rate * rng.normal(1.0, 0.02, len(b))
    b["COGS"] = b["Gross Sales"] * cogs_rate

    # Some actual lines were never budgeted (new business).
    keep = rng.random(len(b)) > UNBUDGETED_ROW_SHARE
    b = b[keep]

    # Some budget lines never materialised (budget with no actual).
    periods = sorted(a["period"].unique())
    cross = pd.MultiIndex.from_product(
        [periods, sorted(a["segment"].unique()), sorted(a["country"].unique()), sorted(a["product"].unique())],
        names=KEYS,
    ).to_frame(index=False)
    merged = cross.merge(a[KEYS], on=KEYS, how="left", indicator=True)
    candidates = merged[merged["_merge"] == "left_only"][KEYS].reset_index(drop=True)
    picks = candidates.iloc[rng.choice(len(candidates), size=BUDGET_ONLY_ROWS, replace=False)].copy()
    gs = rng.choice(a["Gross Sales"].values, size=len(picks)) * rng.uniform(0.6, 1.0, len(picks))
    price = a["Gross Sales"].sum() / a["Units Sold"].sum()
    product_rate = (a.groupby("product")["COGS"].sum() / a.groupby("product")["Gross Sales"].sum())
    picks["Gross Sales"] = gs
    picks["Units Sold"] = gs / price
    picks["Discounts"] = gs * PLAN_DISCOUNT_RATE
    picks["COGS"] = gs * picks["product"].map(product_rate).values
    return pd.concat([b, picks], ignore_index=True)


def make_forecast(a: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    f = a.copy()
    noise = rng.lognormal(0, 0.04, len(f))
    f["Gross Sales"] = a["Gross Sales"].values * noise
    f["Units Sold"] = a["Units Sold"].values * noise
    f["Discounts"] = (a["Discounts"] / a["Gross Sales"]).values * f["Gross Sales"] * rng.normal(1.0, 0.03, len(f))
    f["COGS"] = (a["COGS"] / a["Gross Sales"]).values * f["Gross Sales"] * rng.normal(1.0, 0.02, len(f))
    return f


def main() -> None:
    rng = np.random.default_rng(SEED)
    a = load_actuals()
    b = make_budget(a, rng)
    f = make_forecast(a, rng)
    for name, df in [("actual", a), ("budget", b), ("forecast", f)]:
        to_long(df).to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}.csv  lines={len(df):>4}  gross_sales={df['Gross Sales'].sum():,.0f}")
    print("Periods:", a["period"].min(), "to", a["period"].max())


if __name__ == "__main__":
    main()
