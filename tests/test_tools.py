"""Driver correctness: tool outputs must match the independent ground truth."""
import pytest

from evaluation import ground_truth as gt
from fpa.data_tools import DIMS, PnLData

CASES = [("2014-12", "budget", "month"), ("2014-10", "budget", "month"),
         ("2014-12", "forecast", "ytd"), ("2014-11", "prior_year", "month"), ("2014-06", "budget", "ytd")]
METRICS = ["Gross Sales", "Discounts", "Net Sales", "COGS", "Gross Profit"]


@pytest.fixture(scope="module")
def data():
    return PnLData()


@pytest.mark.parametrize("period,compare,scope", CASES)
def test_summary_matches_ground_truth(data, period, compare, scope):
    res = data.get_pnl_summary(period, compare, scope)
    lines = {l["account"]: l for l in res["lines"]}
    for m in METRICS:
        a, c, v = gt.totals(period, compare, scope, m)
        assert lines[m]["actual"] == pytest.approx(a, abs=0.02)
        assert lines[m]["comparison"] == pytest.approx(c, abs=0.02)
        assert lines[m]["variance"] == pytest.approx(v, abs=0.02)


@pytest.mark.parametrize("period,compare,scope", CASES)
@pytest.mark.parametrize("metric", ["Net Sales", "Gross Profit", "COGS", "Discounts"])
@pytest.mark.parametrize("dim", DIMS)
def test_top_drivers_match_ground_truth(data, period, compare, scope, metric, dim):
    got = data.get_top_drivers(period, metric, dim, compare, scope, n=3)["drivers"]
    exp = gt.top_drivers(period, compare, scope, metric, dim, n=3)
    assert [g["member"] for g in got] == [e[0] for e in exp]
    for g, e in zip(got, exp):
        assert g["variance"] == pytest.approx(e[1], abs=0.02)


def test_favourable_labels(data):
    lines = {l["account"]: l for l in data.get_pnl_summary("2014-12", "budget", "month")["lines"]}
    for acct in ("Discounts", "COGS"):  # costs: lower than comparison is favourable
        expected = "favourable" if lines[acct]["variance"] < 0 else "unfavourable"
        assert lines[acct]["label"] == expected
    for acct in ("Gross Sales", "Net Sales", "Gross Profit"):
        expected = "favourable" if lines[acct]["variance"] > 0 else "unfavourable"
        assert lines[acct]["label"] == expected


def test_partial_prior_year_is_flagged(data):
    res = data.get_pnl_summary("2014-12", "prior_year", "ytd")
    assert res["comparison_months"] < res["actual_months"]
    assert res["warnings"]


def test_bad_inputs_return_errors_not_crashes(data):
    from fpa.data_tools import call_tool
    assert "error" in call_tool(data, "get_pnl_summary", {"period": "1999-01"})
    assert "error" in call_tool(data, "get_top_drivers", {"period": "2014-12", "metric": "Profit??", "dimension": "segment"})
    assert "error" in call_tool(data, "no_such_tool", {})
