"""Command line entry point.

Examples
  python main.py --dry-run                              # no API calls: facts + retrieved docs
  python main.py --period 2014-12 --compare budget      # full pipeline
  python main.py --period 2014-12 --compare forecast --scope ytd
  python main.py --period 2014-10 --note "Enterprise missed because of competitor price cuts"
"""
import argparse
import json

from fpa import config, data_tools
from fpa.pipeline import facts_and_docs_only, run_pipeline
from fpa.rag import DocIndex
from fpa.report import render_report


def main():
    data = data_tools.PnLData()
    p = argparse.ArgumentParser(description="FP&A Commentary Copilot")
    p.add_argument("--period", default=data.periods[-1], help="YYYY-MM (default: latest)")
    p.add_argument("--compare", choices=data_tools.COMPARES, default="budget")
    p.add_argument("--scope", choices=data_tools.SCOPES, default="month")
    p.add_argument("--note", default="", help="Optional analyst note (treated as unverified)")
    p.add_argument("--rag-backend", choices=["auto", "chroma", "tfidf"], default="auto")
    p.add_argument("--dry-run", action="store_true", help="Compute facts and retrieve docs only (no LLM)")
    a = p.parse_args()

    if a.dry_run:
        store, docs = facts_and_docs_only(a.period, a.compare, a.scope, data=data)
        print(json.dumps(store.as_list(), indent=2)[:6000], "\n...")
        print("\nRetrieved docs:", [c.id for c in docs])
        return

    result = run_pipeline(a.period, a.compare, a.scope, a.note, data=data, index=DocIndex(a.rag_backend))
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    stem = f"report_{a.period}_{a.compare}_{a.scope}"
    md = render_report(result)
    (config.OUTPUT_DIR / f"{stem}.md").write_text(md, encoding="utf-8")
    (config.OUTPUT_DIR / f"{stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\n" + md)
    print(f"\nSaved to outputs/{stem}.md and .json")


if __name__ == "__main__":
    main()
