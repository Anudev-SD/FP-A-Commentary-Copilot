from fpa.guardrails import audit, checkable_numbers, strip_citations

ALLOWED = [12378765.4, 8.31, 0.99, 1180167.48]
FIDS, DIDS = {"F1", "F2"}, {"glossary#variance"}


def run(text):
    return audit(text, ALLOWED, FIDS, DIDS)


def test_rounded_numbers_pass():
    p = run("Net Sales were $12.4M [F1]. The variance was 8.3% [F1]. Margin rose 1.0pp [F2].")
    assert not p["ungrounded"] and not p["uncited_numeric_sentences"]


def test_fabricated_number_is_caught():
    p = run("Net Sales were $13.9M [F1].")
    assert [t["token"] for t in p["ungrounded"]] == ["$13.9M"]


def test_invalid_citation_is_caught():
    p = run("Net Sales were $12.4M [F9]. See [D:glossary#nope].")
    assert set(p["invalid_citations"]) == {"F9", "D:glossary#nope"}


def test_uncited_numeric_sentence_is_caught():
    p = run("Net Sales were $12.4M.")
    assert len(p["uncited_numeric_sentences"]) == 1


def test_years_periods_and_small_ints_are_ignored():
    assert checkable_numbers("In Q4 2014-12 the top 3 drivers across 5 segments.") == []


def test_citation_after_full_stop_is_tolerated():
    p = run("Net Sales were $12.4M. [F1]")
    assert not p["uncited_numeric_sentences"]


def test_strip_citations():
    assert strip_citations("Sales rose [F1] again [D:glossary#variance].") == "Sales rose again."
