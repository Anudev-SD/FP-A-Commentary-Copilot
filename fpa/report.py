"""Turn a pipeline result into the final markdown report."""
from . import guardrails
from .pipeline import render_draft, render_summary


def render_report(r: dict) -> str:
    req = r["request"]
    scope = "year to date" if req["scope"] == "ytd" else "month"
    title = f"Performance Commentary: {req['period']} ({scope}) vs {req['compare'].replace('_', ' ')}"
    out = [f"# {title}", "", "> DRAFT for FP&A review. Budget and Forecast are simulated in this prototype.", ""]

    out += ["## Leadership Summary", guardrails.strip_citations(render_summary(r["summary"])), ""]
    if r["summary_guardrails"]["ungrounded"]:
        out += ["> WARNING: summary contains numbers not found in the facts: " +
                ", ".join(t["token"] for t in r["summary_guardrails"]["ungrounded"]), ""]

    out += ["## Management Commentary (with citations)", render_draft(r["draft"]), ""]

    out += ["## Review Mode", ""]
    flags = r["review"]["flags"]
    if flags:
        out += ["| Severity | Category | Where | Issue | Source |", "|---|---|---|---|---|"]
        for f in flags:
            cells = [f.get("severity", ""), f.get("category", ""), str(f.get("where", ""))[:60],
                     str(f.get("issue", "")) + (f" Fix: {f['suggested_fix']}" if f.get("suggested_fix") else ""),
                     f.get("source", "")]
            out.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
    else:
        out.append("No flags raised.")
    if r["review"]["questions"]:
        out += ["", "**Follow-up questions for the analyst**"] + [f"{i}. {q}" for i, q in enumerate(r["review"]["questions"], 1)]

    out += ["", "## Sources", "", "**Data facts**"]
    for f in r["facts"]:
        out.append(f"- [{f['fact_id']}] `{f['tool']}` {f['args']}")
    out += ["", "**Reference documents used**"] + [f"- [D:{d}]" for d in r["docs_used"]]
    out += ["", f"_Model: {req['model']} | RAG backend: {req['rag_backend']} | "
                f"draft repair passes: {r['draft_repairs']}_"]
    return "\n".join(out)
