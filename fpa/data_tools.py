"""Deterministic finance calculations.

Rule of the project: the LLM never does arithmetic. It asks these tools, and the tool
outputs become the only source of numbers for the narrative.
"""
from __future__ import annotations

import pandas as pd

from . import config

DIMS = ["segment", "country", "product"]
BASE_ACCOUNTS = ["Gross Sales", "Discounts", "COGS", "Units Sold"]
METRICS = ["Gross Sales", "Discounts", "Net Sales", "COGS", "Gross Profit", "Units Sold"]
# Costs and discounts are stored as positive amounts, so LOWER is better for them.
HIGHER_IS_BETTER = {
    "Gross Sales": True, "Discounts": False, "Net Sales": True,
    "COGS": False, "Gross Profit": True, "Units Sold": True,
}
RATIO_HIGHER_IS_BETTER = {"gross_margin_pct": True, "discount_rate_pct": False, "cogs_pct_net_sales": False}
COMPARES = ["budget", "forecast", "prior_year"]
SCOPES = ["month", "ytd"]
SCENARIO = {"budget": "Budget", "forecast": "Forecast", "prior_year": "Prior Year"}
DEFAULTS = {
    "get_pnl_summary": {"compare": "budget", "scope": "month"},
    "get_top_drivers": {"compare": "budget", "scope": "month", "n": 3},
    "get_trend": {"months": 6},
    "get_data_quality": {"compare": "budget", "scope": "month"},
}


# ----------------------------------------------------------------- helpers
def r2(x):
    return None if x is None else round(float(x), 2)


def _safe_div(a, b):
    return None if b is None or abs(b) < 1e-9 else a / b


def _label(variance: float, higher_is_better: bool) -> str:
    if abs(variance) < 0.005:
        return "flat"
    good = variance > 0 if higher_is_better else variance < 0
    return "favourable" if good else "unfavourable"


def _var(actual: float, comp: float, higher_is_better: bool) -> dict:
    v = actual - comp  # ALWAYS actual minus comparison
    pct = _safe_div(v, abs(comp))
    return {
        "variance": r2(v),
        "variance_pct": r2(pct * 100) if pct is not None else None,
        "label": _label(v, higher_is_better),
    }


def _wide(long_df: pd.DataFrame) -> pd.DataFrame:
    w = long_df.pivot_table(index=["period"] + DIMS, columns="account", values="amount",
                            aggfunc="sum", fill_value=0.0).reset_index()
    w.columns.name = None
    for a in BASE_ACCOUNTS:
        if a not in w:
            w[a] = 0.0
    w["Net Sales"] = w["Gross Sales"] - w["Discounts"]
    w["Gross Profit"] = w["Net Sales"] - w["COGS"]
    return w


def _ratios(df: pd.DataFrame) -> dict:
    gs, d, ns, cg, gp = (df[c].sum() for c in ["Gross Sales", "Discounts", "Net Sales", "COGS", "Gross Profit"])

    def pct(n, den):
        x = _safe_div(n, den)
        return None if x is None else x * 100

    return {
        "gross_margin_pct": pct(gp, ns),          # Gross Profit / Net Sales
        "discount_rate_pct": pct(d, gs),          # Discounts / Gross Sales
        "cogs_pct_net_sales": pct(cg, ns),        # COGS / Net Sales
    }


# ----------------------------------------------------------------- data class
class PnLData:
    def __init__(self, data_dir=None):
        d = data_dir or config.DATA_DIR
        raw = {s: pd.read_csv(d / f"{s}.csv", dtype={"period": str}) for s in ["actual", "budget", "forecast"]}
        self.frames = {
            "Actual": _wide(raw["actual"]),
            "Budget": _wide(raw["budget"]),
            "Forecast": _wide(raw["forecast"]),
        }
        py = raw["actual"].copy()
        py["period"] = py["period"].map(lambda p: str(pd.Period(p, "M") + 12))
        self.frames["Prior Year"] = _wide(py)
        self.periods = sorted(self.frames["Actual"]["period"].unique())

    # -- internal
    def _validate(self, period, compare=None, scope=None):
        if period not in self.periods:
            raise ValueError(f"Unknown period '{period}'. Use YYYY-MM between {self.periods[0]} and {self.periods[-1]}.")
        if compare is not None and compare not in COMPARES:
            raise ValueError(f"compare must be one of {COMPARES}")
        if scope is not None and scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}")

    def _select(self, scenario: str, period: str, scope: str) -> pd.DataFrame:
        df = self.frames[scenario]
        if scope == "month":
            return df[df["period"] == period]
        start = f"{period[:4]}-01"
        return df[(df["period"] >= start) & (df["period"] <= period)]

    # -- tools
    def get_pnl_summary(self, period: str, compare: str = "budget", scope: str = "month") -> dict:
        """Actual vs comparison for every P&L line, plus margin and rate ratios."""
        self._validate(period, compare, scope)
        a = self._select("Actual", period, scope)
        c = self._select(SCENARIO[compare], period, scope)
        lines = []
        for m in METRICS:
            av, cv = a[m].sum(), c[m].sum()
            lines.append({"account": m, "actual": r2(av), "comparison": r2(cv), **_var(av, cv, HIGHER_IS_BETTER[m])})
        ra, rc = _ratios(a), _ratios(c)
        ratios = {}
        for k, hib in RATIO_HIGHER_IS_BETTER.items():
            av, cv = ra[k], rc[k]
            if av is None or cv is None:
                ratios[k] = {"actual": r2(av), "comparison": r2(cv), "variance_pp": None, "label": "n/a"}
            else:
                ratios[k] = {"actual": r2(av), "comparison": r2(cv), "variance_pp": r2(av - cv),
                             "label": _label(av - cv, hib)}
        a_months, c_months = a["period"].nunique(), c["period"].nunique()
        warnings = []
        if c_months < a_months:
            warnings.append(f"Comparison covers {c_months} of {a_months} months in scope; variances are not like-for-like.")
        if c["Gross Sales"].sum() == 0:
            warnings.append("No comparison data exists for this period.")
        return {"tool": "get_pnl_summary", "period": period, "scope": scope, "compare": compare,
                "actual_months": int(a_months), "comparison_months": int(c_months),
                "lines": lines, "ratios": ratios, "warnings": warnings}

    def get_top_drivers(self, period: str, metric: str, dimension: str, compare: str = "budget",
                        scope: str = "month", n: int = 3) -> dict:
        """Rank members of a dimension (segment/country/product) by absolute variance."""
        self._validate(period, compare, scope)
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        if dimension not in DIMS:
            raise ValueError(f"dimension must be one of {DIMS}")
        n = max(1, min(int(n), 6))
        a = self._select("Actual", period, scope).groupby(dimension)[metric].sum()
        c = self._select(SCENARIO[compare], period, scope).groupby(dimension)[metric].sum()
        idx = a.index.union(c.index)
        tbl = pd.DataFrame({"actual": a.reindex(idx, fill_value=0.0), "comparison": c.reindex(idx, fill_value=0.0)})
        tbl["variance"] = tbl["actual"] - tbl["comparison"]
        total = tbl["variance"].sum()
        tbl = tbl.reindex(tbl["variance"].abs().sort_values(ascending=False).index)
        hib = HIGHER_IS_BETTER[metric]
        drivers = []
        for name, row in tbl.head(n).iterrows():
            share = _safe_div(row["variance"], total)
            drivers.append({"member": name, "actual": r2(row["actual"]), "comparison": r2(row["comparison"]),
                            **_var(row["actual"], row["comparison"], hib),
                            "share_of_total_variance_pct": r2(share * 100) if share is not None else None})
        return {"tool": "get_top_drivers", "period": period, "scope": scope, "compare": compare,
                "metric": metric, "dimension": dimension, "total_variance": r2(total),
                "total_label": _label(total, hib), "drivers": drivers,
                "other_members_variance": r2(tbl.iloc[n:]["variance"].sum()), "members_total": int(len(tbl))}

    def get_trend(self, metric: str, period: str, months: int = 6) -> dict:
        """Monthly Actual vs Budget for the last N months (context, not a forecast)."""
        self._validate(period)
        if metric not in METRICS:
            raise ValueError(f"metric must be one of {METRICS}")
        months = max(2, min(int(months), 12))
        i = self.periods.index(period)
        window = self.periods[max(0, i - months + 1): i + 1]
        act, bud = self.frames["Actual"], self.frames["Budget"]
        series = [{"period": p, "actual": r2(act[act["period"] == p][metric].sum()),
                   "budget": r2(bud[bud["period"] == p][metric].sum())} for p in window]
        return {"tool": "get_trend", "metric": metric, "period": period, "months": len(window), "series": series}

    def get_data_quality(self, period: str, compare: str = "budget", scope: str = "month") -> dict:
        """Deterministic checks that feed Review Mode (coverage, orphans, concentration)."""
        self._validate(period, compare, scope)
        a = self._select("Actual", period, scope)
        c = self._select(SCENARIO[compare], period, scope)
        keys = ["period"] + DIMS
        m = a[keys + ["Gross Sales"]].merge(c[keys + ["Gross Sales"]], on=keys, how="outer",
                                             suffixes=("_a", "_c"), indicator=True)
        a_total, c_total = a["Gross Sales"].sum(), c["Gross Sales"].sum()
        unbudgeted = m.loc[m["_merge"] == "left_only", "Gross Sales_a"].sum()
        orphan = m.loc[m["_merge"] == "right_only", "Gross Sales_c"].sum()
        unb_pct = (_safe_div(unbudgeted, a_total) or 0) * 100
        orp_pct = (_safe_div(orphan, c_total) or 0) * 100
        conc = {}
        for d in DIMS:
            s = a.groupby(d)["Net Sales"].sum().sort_values(ascending=False)
            if len(s) and s.sum() > 0:
                conc[d] = {"member": s.index[0], "share_of_net_sales_pct": r2(s.iloc[0] / s.sum() * 100)}
        a_months, c_months = a["period"].nunique(), c["period"].nunique()
        findings = []
        if config.BUDGET_FORECAST_ARE_SIMULATED and compare in ("budget", "forecast"):
            findings.append({"severity": "high", "category": "data_provenance",
                             "message": f"The {compare} figures are simulated for this prototype and are not an approved management plan."})
        if compare == "prior_year" and c_months < a_months:
            findings.append({"severity": "high", "category": "missing_data",
                             "message": f"Prior-year data covers {c_months} of {a_months} months in scope."})
        if unb_pct >= 1:
            findings.append({"severity": "medium", "category": "missing_data",
                             "message": f"{unb_pct:.1f}% of Actual Gross Sales sits in lines with no {compare} line, so part of the variance is unplanned business."})
        if orp_pct >= 1:
            findings.append({"severity": "medium", "category": "missing_data",
                             "message": f"{orp_pct:.1f}% of {compare} Gross Sales sits in lines with no Actual, so part of the variance is planned business that did not occur."})
        for d, info in conc.items():
            if info["share_of_net_sales_pct"] >= 40:
                findings.append({"severity": "low", "category": "concentration",
                                 "message": f"{info['member']} is {info['share_of_net_sales_pct']:.1f}% of Actual Net Sales by {d}; results are sensitive to it."})
        findings.append({"severity": "low", "category": "weak_assumption",
                         "message": "The source file does not state a currency; amounts are shown with $ by convention."})
        return {"tool": "get_data_quality", "period": period, "scope": scope, "compare": compare,
                "metrics": {"actual_months": int(a_months), "comparison_months": int(c_months),
                            "actual_lines_without_comparison_pct": r2(unb_pct),
                            "comparison_lines_without_actual_pct": r2(orp_pct),
                            "concentration": conc},
                "findings": findings}


# ----------------------------------------------------------------- tool registry
def normalize_args(name: str, args: dict) -> dict:
    out = dict(DEFAULTS.get(name, {}))
    out.update({k: v for k, v in (args or {}).items() if v is not None})
    return out


def call_tool(data: PnLData, name: str, args: dict) -> dict:
    fns = {"get_pnl_summary": data.get_pnl_summary, "get_top_drivers": data.get_top_drivers,
           "get_trend": data.get_trend, "get_data_quality": data.get_data_quality}
    if name not in fns:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fns[name](**normalize_args(name, args))
    except (ValueError, TypeError) as e:
        return {"error": str(e)}


def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


_P = {"type": "string", "description": "Reporting month as YYYY-MM"}
_C = {"type": "string", "enum": COMPARES, "description": "Comparison scenario"}
_S = {"type": "string", "enum": SCOPES, "description": "month = single month, ytd = January to the month"}

TOOL_SCHEMAS = [
    _fn("get_pnl_summary", "Actual vs comparison for all P&L lines with variance, variance %, favourable/unfavourable label and margin ratios.",
        {"period": _P, "compare": _C, "scope": _S}, ["period", "compare", "scope"]),
    _fn("get_top_drivers", "Rank members of a dimension by absolute variance for one metric (what is driving the variance).",
        {"period": _P, "metric": {"type": "string", "enum": METRICS}, "dimension": {"type": "string", "enum": DIMS},
         "compare": _C, "scope": _S, "n": {"type": "integer", "description": "How many drivers (1-6)"}},
        ["period", "metric", "dimension", "compare", "scope"]),
    _fn("get_trend", "Actual vs Budget monthly series for the last N months for one metric (context only).",
        {"metric": {"type": "string", "enum": METRICS}, "period": _P, "months": {"type": "integer"}}, ["metric", "period"]),
]
