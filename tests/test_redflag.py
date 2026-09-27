"""Offline tests: no API key or vector index needed. The LLM and the retriever are replaced by fakes where needed."""

import pytest

import redflag.qa as qa
from evals.run import is_correct
from redflag.index import rrf
from redflag.ingest import UNIT, load_pages, page_units
from redflag.memo import check_memo, red_flags


def test_unit_detection_carries_to_continuation_pages():
    pages = [{"text": "Summary (₹ in lakhs)\nRevenue 44,401.61"}, {"text": "Borrowings 18,628.02"}, {"text": "x"}, {"text": "y"}, {"text": "(Rs. in million) z"}]
    assert page_units(pages) == ["lakhs", "lakhs", "lakhs", None, "million"]
    assert UNIT.search("(₹ in crores)").group(1).lower() == "crores"


def test_real_page_carries_unit():
    from redflag.ingest import extract_pages

    pages = extract_pages("madhur_steel")
    assert page_units(pages)[84] == "lakhs"  # page 85: table continues from page 84 without its own unit line


def test_citation_check_catches_wrong_page_quote_and_value():
    assert qa.check_citation("madhur_steel", 85, "Borrowings  18,628.02   11,405.28", 18628.02) is None
    assert "not found on page 86" in qa.check_citation("madhur_steel", 86, "Borrowings 18,628.02", 18628.02)
    assert "does not appear" in qa.check_citation("madhur_steel", 85, "Borrowings 18,628.02", 18682.02)
    assert "no page" in qa.check_citation("madhur_steel", None, "x", 1)


def _state(**ex):
    return {"ex": qa.Extraction(found=True, **ex), "passages": [{"page": 86, "unit": "lakhs"}], "doc": "madhur_steel"}


def test_compute_growth_and_unit_conversion_in_python():
    s = _state(operation="growth_pct", operands=[qa.Operand(label="FY25", value=33956.36, unit="lakhs", page=86, quote="q"),
                                                 qa.Operand(label="FY26", value=44401.61, unit="lakhs", page=86, quote="q")])
    assert qa.compute(s)["ex"].value == pytest.approx(30.76, abs=0.01)
    s = _state(operation="convert_to_crore", operands=[qa.Operand(label="rev", value=44401.61, unit=None, page=86, quote="q")])
    assert qa.compute(s)["ex"].value == pytest.approx(444.02, abs=0.01)  # unit taken from the page label


def test_agent_retries_then_declines_when_citation_never_verifies(monkeypatch):
    calls = []

    def fake_call(model, system, user, schema):
        calls.append(user)
        return qa.Extraction(found=True, answer="18,682.02", value=18682.02, unit="lakhs", page=85, quote="Borrowings 18,682.02"), \
            {"latency_s": 0.1, "cost_usd": 0.0, "tokens_in": 1, "tokens_out": 1}

    monkeypatch.setattr(qa, "call", fake_call)
    monkeypatch.setattr(qa, "search", lambda *a, **k: [{"page": 85, "unit": "lakhs", "text": "Borrowings 18,628.02"}])
    r = qa.ask("What were current borrowings?", "madhur_steel", "full")
    assert not r["found"] and r["attempts"] == 2 and "Not verified" in r["answer"]
    assert "failed verification" in calls[1]


def test_rrf_rewards_agreement():
    a = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
    b = [{"id": "y"}, {"id": "w"}]
    assert [h["id"] for h in rrf([a, b], k=2)] == ["y", "x"]


def test_scoring_is_sign_insensitive_and_declines_count():
    g = {"type": "table_number", "value": -67.09}
    assert is_correct(g, {"found": True, "value": 67.09}) and not is_correct(g, {"found": True, "value": 670.9})
    assert is_correct({"type": "not_disclosed"}, {"found": False})
    assert not is_correct({"type": "not_disclosed"}, {"found": True, "value": 5})
    assert is_correct({"type": "text", "keywords": ["Jayant Agrawal"]}, {"found": True, "answer": "The promoter is Jayant Agrawal."})


def _fact(key, value, unit="lakhs", page=1):
    crore = value * {"lakhs": 0.01, "million": 0.1}.get(unit, 1) if unit in ("lakhs", "million") else None
    return {"key": key, "found": True, "value": value, "unit": unit, "crore": crore, "page": page, "answer": str(value)}


def test_red_flag_rules():
    facts = [_fact("pat_fy26", -1488.81, "million", 83), _fact("revenue_fy26", 1058.27, "million", 80), _fact("revenue_fy25", 1399.89, "million", 80),
             _fact("equity_fy26", 11789.73, "lakhs", 84), _fact("current_borrowings_fy26", 18628.02, "lakhs", 85),
             _fact("pbt_fy26", 1000.00, "lakhs", 86), _fact("finance_costs_fy26", 1847.29, "lakhs", 86),
             _fact("receivables_fy26", 8020.52, "lakhs", 84), _fact("receivables_fy25", 4172.94, "lakhs", 84)]
    rules = {f["rule"] for f in red_flags({"facts": facts})["flags"]}
    assert {"Loss-making", "Revenue decline", "High leverage", "Thin interest cover", "Trade receivables outgrowing revenue"} <= rules


def test_memo_guardrail_drops_unverified_numbers():
    state = {"doc": "madhur_steel", "facts": [_fact("revenue_fy26", 44401.61, "lakhs", 86)], "flags": [],
             "memo": {"headline": "Revenue of ₹444.02 crore", "summary": "Revenue was ₹444.02 crore [p. 86]. Margins are 12.7% [p. 90].",
                      "red_flags": ["Order book of ₹900 crore [p. 12]"], "questions_for_management": ["Why did revenue grow?"]}}
    out = check_memo(state)
    assert out["memo"]["summary"] == "Revenue was ₹444.02 crore [p. 86]."
    assert out["memo"]["red_flags"] == [] and len(out["dropped"]) == 2


def test_api_validates_input(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import redflag.api as api

    monkeypatch.setattr(api, "FEEDBACK", tmp_path / "fb.jsonl")
    c = TestClient(api.app)
    assert c.get("/health").json()["status"] == "ok"
    assert c.post("/ask", json={"doc": "nope", "question": "What is revenue?"}).status_code == 404
    assert c.post("/ask", json={"doc": "atomberg", "question": "hi"}).status_code == 422
    assert c.post("/feedback", json={"doc": "atomberg", "question": "q", "answer": "a", "correct": False}).json()["logged"]
    assert (tmp_path / "fb.jsonl").read_text().count("\n") == 1


def test_pages_are_available():
    assert len(load_pages("atomberg")) == 505
