"""Independent re-computation of expected answers.

Deliberately written WITHOUT importing fpa.data_tools, and Actual is read straight from the
raw Excel file (using its own 'Sales' and 'Profit' columns), so a bug in the tools cannot
hide itself by also being in the checker.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "Financial_Sample.xlsx"
COL = {"Gross Sales": "Gross Sales", "Discounts": "Discounts", "Net Sales": "Sales", "COGS": "COGS", "Gross Profit": "Profit"}
DIM = {"segment": "Segment", "country": "Country", "product": "Product"}
ALIASES = {"United States of America": ["united states", "usa", "u.s."]}


def _raw_actual() -> pd.DataFrame:
    df = pd.read_excel(RAW)
    df.columns = [c.strip() for c in df.columns]
    df["period"] = df["Date"].dt.strftime("%Y-%m")
    return df


def _scenario_from_csv(name: str) -> pd.DataFrame:
    long = pd.read_csv(ROOT / "data" / f"{name}.csv", dtype={"period": str})
    rows = {}
    for r in long.itertuples():
        key = (r.period, r.segment, r.country, r.product)
        rows.setdefault(key, {})[r.account] = r.amount
    df = pd.DataFrame([{"period": k[0], "Segment": k[1], "Country": k[2], "Product": k[3], **v} for k, v in rows.items()]).fillna(0.0)
    df["Sales"] = df["Gross Sales"] - df["Discounts"]
    df["Profit"] = df["Sales"] - df["COGS"]
    return df


def _frame(compare: str) -> pd.DataFrame:
    if compare in ("budget", "forecast"):
        return _scenario_from_csv(compare)
    df = _raw_actual().copy()
    df["period"] = [str(pd.Period(p, "M") + 12) for p in df["period"]]  # prior year -> shifted by a year
    return df


def _scope(df: pd.DataFrame, period: str, scope: str) -> pd.DataFrame:
    if scope == "month":
        return df[df["period"] == period]
    return df[(df["period"] >= period[:4] + "-01") & (df["period"] <= period)]


def totals(period: str, compare: str, scope: str, metric: str):
    col = COL[metric]
    a = _scope(_raw_actual(), period, scope)[col].sum()
    c = _scope(_frame(compare), period, scope)[col].sum()
    return a, c, a - c


def top_drivers(period: str, compare: str, scope: str, metric: str, dimension: str, n: int = 3):
    col, dim = COL[metric], DIM[dimension]
    a = _scope(_raw_actual(), period, scope).groupby(dim)[col].sum()
    c = _scope(_frame(compare), period, scope).groupby(dim)[col].sum()
    members = set(a.index) | set(c.index)
    var = {m: a.get(m, 0.0) - c.get(m, 0.0) for m in members}
    ranked = sorted(var.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return ranked[:n]


def mentioned(text: str, member: str) -> bool:
    t = text.lower()
    return member.lower() in t or any(a in t for a in ALIASES.get(member, []))
