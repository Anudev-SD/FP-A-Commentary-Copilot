"""Evaluate the full pipeline on the test cases.  Run:  python -m evaluation.run_eval

Metrics per case
  ungrounded_numbers   numbers in the draft that match no tool output (target 0)
  invalid_citations    cited ids that do not exist (target 0)
  uncited_sentences    numeric sentences without a citation (target 0)
  driver_recall        share of ground-truth #1 drivers (Net Sales and Gross Profit x 3 dimensions)
                       named in the Key Drivers section; ground truth is computed independently
  expected_flags_ok    Review Mode raised the flag categories we know it must raise
  judge scores         LLM-as-judge groundedness / clarity / consistency (1-5)
  note_as_fact         adversarial: did the draft state the unverified analyst note as fact?
Tool accuracy (top deltas match data) is covered separately by:  pytest tests/test_tools.py
"""
import json
from pathlib import Path

from fpa import config, data_tools, prompts
from fpa.llm import LLM
from fpa.pipeline import docs_json, render_draft, run_pipeline
from fpa.rag import DocIndex

from . import ground_truth as gt

CASES = json.loads((Path(__file__).parent / "test_cases.json").read_text())


def key_drivers_text(draft: dict) -> str:
    for s in draft.get("sections", []):
        if "driver" in s.get("title", "").lower():
            return s.get("body", "")
    return render_draft(draft, with_questions=False)


def driver_recall(case: dict, draft: dict) -> float:
    text = key_drivers_text(draft)
    hits = total = 0
    for metric in ("Net Sales", "Gross Profit"):
        for dim in data_tools.DIMS:
            top = gt.top_drivers(case["period"], case["compare"], case["scope"], metric, dim, 1)[0][0]
            total += 1
            hits += gt.mentioned(text, top)
    return hits / total


def judge(llm: LLM, result: dict, index: DocIndex) -> dict:
    docs = [index.by_id[i] for i in result["docs_used"]]
    user = (f"ANALYST NOTE: {result['request']['note'] or '(none)'}\n\nDRAFT:\n{render_draft(result['draft'])}\n\n"
            f"FACTS:\n{json.dumps(result['facts'], separators=(',', ':'))}\n\nDOCS:\n{docs_json(docs)}")
    return llm.json_chat(prompts.JUDGE_SYSTEM, user)


def main():
    llm, index, data = LLM(), DocIndex(), data_tools.PnLData()
    rows = []
    for case in CASES:
        print(f"Running {case['id']} ...")
        r = run_pipeline(case["period"], case["compare"], case["scope"], case["note"],
                         llm=llm, data=data, index=index, progress=lambda *_: None)
        g = r["draft_guardrails"]
        cats = {f.get("category") for f in r["review"]["flags"]}
        j = judge(llm, r, index)
        rows.append({
            "id": case["id"], "numbers_checked": g["checked"], "ungrounded": len(g["ungrounded"]),
            "invalid_cites": len(g["invalid_citations"]), "uncited": len(g["uncited_numeric_sentences"]),
            "repairs": r["draft_repairs"], "driver_recall": round(driver_recall(case, r["draft"]), 2),
            "flags_ok": set(case.get("expect_flags", [])) <= cats, "n_flags": len(r["review"]["flags"]),
            "groundedness": j.get("groundedness"), "clarity": j.get("clarity"),
            "consistency": j.get("consistency"), "note_as_fact": j.get("presents_note_as_fact"),
        })
    cols = list(rows[0])
    md = ["# Evaluation report", "", f"Model: {llm.model}", "", "| " + " | ".join(cols) + " |",
          "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    (config.OUTPUT_DIR / "eval_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print("\nSaved to outputs/eval_report.md")


if __name__ == "__main__":
    main()
