"""planner -> compute -> retrieve -> draft -> review -> leadership summary."""
from __future__ import annotations

import json

from . import config, data_tools, guardrails, prompts
from .facts import FactStore
from .rag import DocIndex

MAX_PLANNER_ROUNDS = 3


# ------------------------------------------------------------------ rendering helpers
def render_draft(d: dict, with_questions: bool = True) -> str:
    out = []
    if d.get("headline"):
        out.append(f"**{d['headline']}**\n")
    for s in d.get("sections", []):
        out.append(f"### {s.get('title', '')}\n{s.get('body', '')}\n")
    if with_questions and d.get("open_questions"):
        out.append("### Open Questions\n" + "\n".join(f"- {q}" for q in d["open_questions"]))
    return "\n".join(out).strip()


def render_summary(s: dict) -> str:
    return "\n".join(f"- {b}" for b in s.get("bullets", []))


# ------------------------------------------------------------------ stage 1: facts
def baseline_facts(data, store: FactStore, period: str, compare: str, scope: str):
    """Facts the narrative can never do without. Code guarantees these; the LLM planner adds extras."""
    base = {"period": period, "compare": compare, "scope": scope}
    store.call(data, "get_pnl_summary", base)
    for metric in ("Net Sales", "Gross Profit"):
        for dim in data_tools.DIMS:
            store.call(data, "get_top_drivers", {**base, "metric": metric, "dimension": dim})
    store.call(data, "get_data_quality", base)


def planner_extras(llm, data, store: FactStore, period: str, compare: str, scope: str):
    """LLM tool-calling loop: the model chooses extra drill-downs, our code runs them."""
    have = [f"{f['fact_id']}: {f['tool']} {json.dumps(f['args'])}" for f in store.as_list()]
    messages = [
        {"role": "system", "content": prompts.PLANNER_SYSTEM},
        {"role": "user", "content": f"Period {period}, comparison {compare}, scope {scope}.\n"
                                    f"Available periods: {data.periods[0]} to {data.periods[-1]}.\n"
                                    "Facts already collected:\n" + "\n".join(have)},
    ]
    for _ in range(MAX_PLANNER_ROUNDS):
        msg = llm.chat(messages, tools=data_tools.TOOL_SCHEMAS)
        assistant = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant["tool_calls"] = [{"id": tc.id, "type": "function",
                                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                       for tc in msg.tool_calls]
        messages.append(assistant)
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            fid = store.call(data, tc.function.name, args)
            payload = store.facts[fid] if fid else {"error": "tool call failed or invalid arguments"}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(payload)})
    return store


# ------------------------------------------------------------------ stage 2: RAG
def doc_queries(store: FactStore) -> list[str]:
    qs = ["variance sign convention favourable unfavourable", "executive commentary writing rules",
          "materiality threshold", "currency and data coverage caveats"]
    for f in store.as_list():
        if f["tool"] == "get_pnl_summary":
            for ln in f["result"]["lines"]:
                if abs(ln["variance_pct"] or 0) >= config.MATERIALITY_PCT:
                    qs.append(f"{ln['account']} definition")
            qs.append("gross margin and discount rate definition")
    return qs


def retrieve_docs(index: DocIndex, store: FactStore):
    return index.retrieve(doc_queries(store))


def docs_json(docs) -> str:
    return json.dumps([{"id": c.id, "text": c.text} for c in docs], separators=(",", ":"))


# ------------------------------------------------------------------ stage 3: generate + verify
def generate_verified(llm, system: str, user: str, render, store: FactStore, doc_ids: set, max_repairs: int = 1):
    """Generate JSON, run guardrails, and ask for ONE repair if numbers/citations are off."""
    out = llm.json_chat(system, user)
    attempt = 0
    while True:
        problems = guardrails.audit(render(out), store.numbers(), store.ids(), doc_ids)
        if guardrails.is_clean(problems) or attempt >= max_repairs:
            return out, problems, attempt
        attempt += 1
        fix = (user + "\n\nYOUR PREVIOUS OUTPUT:\n" + json.dumps(out) +
               "\n\nGUARDRAIL PROBLEMS TO FIX:\n" + json.dumps(problems) +
               "\nRewrite the JSON. Remove or correct every problem. Use only numbers from FACTS and cite each "
               "numeric sentence with a valid fact id.")
        out = llm.json_chat(system, fix)


# ------------------------------------------------------------------ stage 4: review mode
def run_review(llm, store: FactStore, docs, draft_md: str, guard: dict) -> dict:
    dq = next((f["result"] for f in store.as_list() if f["tool"] == "get_data_quality"), {"findings": []})
    flags = [{"severity": f["severity"], "category": f["category"], "where": "dataset",
              "issue": f["message"], "source": "data_check"} for f in dq.get("findings", [])]
    for t in guard["ungrounded"]:
        flags.append({"severity": "high", "category": "number_not_in_facts", "where": t["token"],
                      "issue": "This number does not match any tool output.", "source": "guardrail"})
    for c in guard["invalid_citations"]:
        flags.append({"severity": "high", "category": "invalid_citation", "where": c,
                      "issue": "Cited id does not exist.", "source": "guardrail"})
    for s in guard["uncited_numeric_sentences"]:
        flags.append({"severity": "medium", "category": "missing_citation", "where": s,
                      "issue": "Sentence contains a number but no citation.", "source": "guardrail"})
    user = (f"DRAFT:\n{draft_md}\n\nFACTS:\n{store.as_json()}\n\nREFERENCE DOCS:\n{docs_json(docs)}\n\n"
            f"DATA CHECKS ALREADY RUN:\n{json.dumps(dq.get('findings', []))}\n\nGUARDRAIL RESULTS:\n{json.dumps(guard)}")
    out = llm.json_chat(prompts.REVIEW_SYSTEM, user)
    for f in out.get("flags", []):
        flags.append({**f, "source": "llm_review"})
    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: order.get(f.get("severity", "low"), 3))
    return {"flags": flags, "questions": out.get("questions", [])}


# ------------------------------------------------------------------ orchestration
def facts_and_docs_only(period: str, compare: str, scope: str, data=None, index=None):
    """No LLM involved: handy for learning, debugging and free dry runs."""
    data = data or data_tools.PnLData()
    index = index or DocIndex("tfidf")
    store = FactStore()
    baseline_facts(data, store, period, compare, scope)
    return store, retrieve_docs(index, store)


def run_pipeline(period: str, compare: str = "budget", scope: str = "month", note: str = "",
                 llm=None, data=None, index=None, progress=print) -> dict:
    from .llm import LLM
    data = data or data_tools.PnLData()
    llm = llm or LLM()
    index = index or DocIndex()
    store = FactStore()

    progress("1/5  Computing facts with tools (baseline + LLM planner)")
    baseline_facts(data, store, period, compare, scope)
    planner_extras(llm, data, store, period, compare, scope)

    progress(f"2/5  Retrieving glossary and policy context ({index.backend_name})")
    docs = retrieve_docs(index, store)

    progress("3/5  Drafting commentary (with guardrail check and one repair pass)")
    user = (f"REPORTING REQUEST: period={period}, comparison={compare}, scope={scope}\n"
            f"ANALYST NOTE (unverified, may be empty): {note or '(none)'}\n\n"
            f"FACTS (the only source of numbers):\n{store.as_json()}\n\n"
            f"REFERENCE DOCS (cite as [D:id]):\n{docs_json(docs)}")
    draft, draft_problems, draft_repairs = generate_verified(
        llm, prompts.DRAFT_SYSTEM, user,
        lambda d: render_draft(d), store, index.ids)
    draft_md = render_draft(draft)

    progress("4/5  Review Mode (flags + follow-up questions)")
    review = run_review(llm, store, docs, draft_md, draft_problems)

    progress("5/5  Leadership Summary")
    s_user = f"DRAFT:\n{draft_md}\n\nFACTS:\n{store.as_json()}"
    summary, sum_problems, _ = generate_verified(
        llm, prompts.SUMMARY_SYSTEM, s_user, render_summary, store, index.ids)

    return {"request": {"period": period, "compare": compare, "scope": scope, "note": note,
                        "model": getattr(llm, "model", "unknown"), "rag_backend": index.backend_name},
            "facts": store.as_list(), "docs_used": [c.id for c in docs],
            "draft": draft, "draft_guardrails": draft_problems, "draft_repairs": draft_repairs,
            "review": review, "summary": summary, "summary_guardrails": sum_problems}
