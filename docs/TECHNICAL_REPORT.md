# Technical Report: FP&A Commentary Copilot (draft)

## 1. Problem
Turn structured P&L data into executive commentary without fabricated figures or unsupported business claims.

## 2. Data
Financial Sample workbook: 700 transactions, Sep 2013 to Dec 2014, 5 segments, 5 countries, 6 products. Aggregated to month x segment x country x product in long format (period, segment, country, product, account, amount). Accounts: Gross Sales, Discounts, COGS, Units Sold; Net Sales and Gross Profit derived. Budget and Forecast are simulated (seed 42); Prior Year is Actual shifted 12 months. See README for the simulation assumptions.

## 3. Architecture
Baseline facts (code) -> LLM planner with tool calling -> FactStore -> RAG -> draft -> audit/repair -> review -> summary. Code guarantees the essential facts; the LLM adds drill-downs. Rationale: reliability first, agency second.

## 4. Prompting
Structured JSON outputs; hard rules in system prompts (numbers only from facts, citation format, no causes without evidence, notes unverified, no guidance); separate prompts for draft, review, summary and judge (`fpa/prompts.py`). Temperature 0.

## 5. Tools
get_pnl_summary, get_top_drivers, get_trend, get_data_quality. Variance = Actual - comparison; labels by account type; variance % undefined when comparison is zero; partial comparison coverage emits warnings.

## 6. RAG
Glossary and reporting notes split by heading; pinned chunks (narrative rules, materiality, sign conventions) always included; semantic hits chosen from queries derived from the facts. ChromaDB + text-embedding-3-small; TF-IDF fallback for offline tests.

## 7. Guardrails
Rounding-aware numeric matching, citation validity, uncited-number detection, one repair pass, residual issues surfaced in Review Mode.

## 8. Evaluation
Method: see README. **Results: TO FILL after running `python -m evaluation.run_eval` with your key.** Paste the table from `outputs/eval_report.md` here and discuss failures.

| Metric | Target | Result |
|---|---|---|
| Tool accuracy (pytest) | 100% | 78 tests pass (verify on your machine) |
| Ungrounded numbers | 0 | TBD |
| Invalid citations | 0 | TBD |
| Driver recall | >= 0.8 | TBD |
| Adversarial: note stated as fact | false | TBD |

## 9. Limitations and future work
Direction words unchecked; no price/volume/mix; synthetic plans and policies; single-model judge bias. Next: PVM decomposition, opex accounts, multi-month trend narratives, human-in-the-loop edits, FastAPI service wrapper.
