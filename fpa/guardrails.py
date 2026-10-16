"""'No fabricated numbers' enforcement.

Every number in generated text must match (after rounding) a number that came out of a
tool call. Every cited id must exist. Sentences with numbers must carry a citation.
"""
from __future__ import annotations

import re

CITE_RE = re.compile(r"\[(F\d+|D:[A-Za-z0-9_#\-]+)\]")
_ANY_BRACKET = re.compile(r"\[[^\]]*\]")
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}(?:-\d{2})?\b")
_NUM_RE = re.compile(
    r"(?P<cur>[$€£])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<unit>\s?(?:%|pp|bps|million|billion|thousand|[KMB])(?![A-Za-z]))?",
    re.IGNORECASE,
)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def collect_numbers(obj, out=None) -> list:
    """Walk any JSON-like structure and gather absolute numeric values."""
    out = [] if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_numbers(v, out)
    return out


def checkable_numbers(text: str) -> list:
    """Numbers worth verifying: money, percentages, comma-grouped or decimal figures.

    Plain small integers (\"top 3\", \"Q4\") and years/periods are ignored on purpose.
    """
    clean = _ANY_BRACKET.sub(" ", text)
    clean = _DATE_RE.sub(" ", clean)
    found = []
    for m in _NUM_RE.finditer(clean):
        raw = m.group("num").replace(",", "")
        unit = (m.group("unit") or "").strip().lower()
        if not (m.group("cur") or unit or "," in m.group("num") or "." in raw):
            continue
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        value, scale = float(raw), 1.0
        if unit in _MULT:
            scale = _MULT[unit]
            value *= scale
        elif unit == "bps":
            scale = 0.01
            value *= scale
        tol = 0.5 * (10 ** -decimals) * scale
        found.append({"token": m.group(0).strip(), "value": value, "tol": tol})
    return found


def audit(text: str, allowed_numbers: list, valid_fact_ids: set, valid_doc_ids: set) -> dict:
    # tolerate a citation placed after the full stop: "... $1.0M. [F2]"
    text = re.sub(r"\.\s+(\[(?:F\d+|D:[^\]]+)\])", r" \1.", text)
    toks = checkable_numbers(text)
    ungrounded = [{"token": t["token"], "value": round(t["value"], 4)} for t in toks
                  if not any(abs(t["value"] - f) <= t["tol"] + 1e-9 for f in allowed_numbers)]
    invalid = sorted({c for c in CITE_RE.findall(text)
                      if (c.startswith("D:") and c[2:] not in valid_doc_ids)
                      or (not c.startswith("D:") and c not in valid_fact_ids)})
    uncited = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", text):
        if checkable_numbers(s) and not CITE_RE.search(s):
            uncited.append(s.strip()[:160])
    return {"checked": len(toks), "ungrounded": ungrounded,
            "invalid_citations": invalid, "uncited_numeric_sentences": uncited}


def is_clean(problems: dict) -> bool:
    return not (problems["ungrounded"] or problems["invalid_citations"] or problems["uncited_numeric_sentences"])


def strip_citations(text: str) -> str:
    return re.sub(r"\s{2,}", " ", re.sub(r"\s?\[(?:F\d+|D:[^\]]+)\]", "", text)).strip()
