"""Whole pipeline with a scripted fake LLM: checks plumbing, guardrail repair and report rendering."""
import json
from types import SimpleNamespace

from fpa.pipeline import run_pipeline
from fpa.rag import DocIndex
from fpa.report import render_report


class FakeLLM:
    model = "fake"

    def __init__(self):
        self.chat_calls = 0
        self.draft_calls = 0

    def chat(self, messages, tools=None):
        self.chat_calls += 1
        if self.chat_calls == 1:  # planner asks for one extra drill-down
            call = SimpleNamespace(id="c1", function=SimpleNamespace(
                name="get_top_drivers",
                arguments=json.dumps({"period": "2014-12", "metric": "Discounts", "dimension": "segment",
                                      "compare": "budget", "scope": "month"})))
            return SimpleNamespace(content=None, tool_calls=[call])
        return SimpleNamespace(content="DONE", tool_calls=None)

    def json_chat(self, system, user):
        if system.startswith("You are an FP&A analyst"):
            self.draft_calls += 1
            facts = json.loads(user.split("FACTS (the only source of numbers):\n")[1].split("\n\nREFERENCE DOCS")[0])
            ns = next(l for l in facts[0]["result"]["lines"] if l["account"] == "Net Sales")
            good = f"Net Sales were ${ns['actual'] / 1e6:.1f}M, {ns['variance_pct']:.1f}% {ns['label']} to budget [F1]."
            bad = "Net Sales were $99.9M, driven by a competitor price cut [F1]."
            repaired = "GUARDRAIL PROBLEMS" in user
            return {"headline": good if repaired else bad,
                    "sections": [{"title": "Performance Overview", "body": good},
                                 {"title": "Data Notes", "body": "Budget is simulated [D:reporting_notes#budget-and-forecast-provenance]."}],
                    "open_questions": ["What drove the Government result?"]}
        if system.startswith("You are a sceptical"):
            return {"flags": [{"severity": "medium", "category": "unsupported_claim", "where": "x", "issue": "y"}],
                    "questions": ["Is the budget approved?"]}
        return {"bullets": ["Net Sales were favourable to budget [F1]."]}


def test_pipeline_end_to_end_with_repair():
    llm = FakeLLM()
    r = run_pipeline("2014-12", "budget", "month", note="Blame the competitor", llm=llm,
                     index=DocIndex("tfidf"), progress=lambda *_: None)
    assert llm.draft_calls == 2 and r["draft_repairs"] == 1          # fabricated number -> repaired once
    assert not r["draft_guardrails"]["ungrounded"]
    assert any(f["args"].get("metric") == "Discounts" for f in r["facts"])  # planner tool call was executed
    assert r["review"]["flags"] and r["review"]["questions"]
    md = render_report(r)
    for heading in ("## Leadership Summary", "## Management Commentary", "## Review Mode", "## Sources"):
        assert heading in md
    assert "[F1]" not in md.split("## Management Commentary")[0]      # summary is citation-free
