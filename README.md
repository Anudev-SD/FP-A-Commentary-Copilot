# FP&A Commentary Copilot

Drafts monthly performance commentary from P&L data (Actual vs Budget / Forecast / Prior Year), computes variances and top drivers with tools, grounds explanations in a finance glossary via RAG, reviews its own draft, and writes a Leadership Summary.

> **Important:** the source file (`Financial_Sample.xlsx`) has no Budget or Forecast. `scripts/prepare_data.py` **simulates** them with a fixed seed. Every report says so.

## How it works (think of a finance team)

| Stage | Real-world analogy | Code |
|---|---|---|
| Compute | Analyst with a calculator. The LLM never does maths. | `fpa/data_tools.py` |
| Planner | Senior analyst asks "also check discounts by segment" | `planner_extras()` in `fpa/pipeline.py` (OpenAI tool calling) |
| Retrieve (RAG) | Looking up the finance policy handbook | `fpa/rag.py` (ChromaDB + OpenAI embeddings) |
| Draft | Writing the commentary | `generate_verified()` + `prompts.DRAFT_SYSTEM` |
| Guardrails | Checker who ticks every number against the workings | `fpa/guardrails.py` |
| Review Mode | Sceptical manager with red pen | `run_review()` |
| Leadership Summary | One-minute version for executives | `prompts.SUMMARY_SYSTEM` |

```
period + compare + scope
   -> baseline facts (code)  -> planner extras (LLM tool calls)   => FactStore: F1, F2, ...
   -> RAG: pinned rules + semantic glossary hits                  => docs: D:glossary#...
   -> Draft (cites [F#] / [D:...]) -> number + citation audit -> 1 repair pass if needed
   -> Review Mode (data checks + guardrail results + LLM judgement) -> flags + questions
   -> Leadership Summary (audited too) -> outputs/report_*.md + .json
```

## Setup (Mac, VS Code)

```bash
cd fpa-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your OpenAI key in .env
python scripts/prepare_data.py   # regenerates data/actual.csv, budget.csv, forecast.csv
pytest -q                        # 78 tests, no API key needed
```

## Run

```bash
                                   # free: facts + retrieved docs, no LLM
python main.py --period 2014-12 --compare budget           # full pipeline
python main.py --period 2014-12 --compare forecast --scope ytd
python main.py --period 2014-10 --note "Channel Partners missed due to competitor price cuts"
streamlit run app.py                                       # optional UI
python -m evaluation.run_eval                              # evaluation table -> outputs/eval_report.md
```
Valid periods: 2013-09 to 2014-12. Prior Year exists only from 2014-09 (source starts Sep 2013).
Models: default `gpt-4o-mini` (change `OPENAI_MODEL` in `.env`). A full run is about 5 to 7 API calls.

## Safety design ("no fabricated figures")
1. LLM gets numbers only from tool outputs (`FactStore`).
2. Every number in the draft is matched to a fact (rounding-aware); unmatched numbers trigger one repair pass, then a visible high-severity flag.
3. Every numeric sentence needs a `[F#]` citation; unknown ids are flagged.
4. Analyst notes are treated as unverified; causes are never asserted without evidence.
5. Favourable/unfavourable labels come from code (costs: lower is favourable), not from the model.

## Evaluation
- `tests/test_tools.py`: top deltas and totals vs an independent recomputation from the raw Excel.
- `tests/test_guardrails.py`, `tests/test_rag.py`, `tests/test_pipeline_fake.py`: guardrails, retrieval, plumbing with a fake LLM.
- `evaluation/run_eval.py`: groundedness, citation validity, driver recall, expected review flags, LLM-as-judge scores, and an adversarial case (unverified cause + invented numbers).

### Simulation assumptions (ground truth for evaluation)
Budget = Actual adjusted per segment (Government budget low, Enterprise and Channel Partners high), flat 5% planned discount rate, cheaper planned COGS for VTT and Velo, about 6% of actual lines unbudgeted, 40 budget lines with no actual. A good commentary should surface these patterns as *what* happened, never as invented *why*.

## Layout
```
main.py  app.py  data/(raw, csvs)  docs/(glossary, reporting notes = RAG sources)
fpa/(config, data_tools, guardrails, rag, llm, prompts, facts, pipeline, report)
scripts/prepare_data.py  tests/  evaluation/  docs/TECHNICAL_REPORT.md
```

## Limitations
Only Gross Sales, Discounts, COGS, Units Sold exist (no opex/EBITDA). Price/volume/mix is not computed. Direction words ("rose") are not machine-checked, only numbers and labels; the Review step covers the rest. The glossary/policies are simulated. Currency is unstated in the source.
