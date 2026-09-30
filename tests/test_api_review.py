"""API: the review workflow end to end, without calling an LLM."""
from fastapi.testclient import TestClient

from redflag import api

client = TestClient(api.app)


def test_review_workflow_over_http():
    q = api.review_queue()
    case_id = q.route("atomberg", "What were trade receivables in FY2026?", {"verified": False, "found": False, "answer": "Not verified"})
    pending = client.get("/reviews", params={"doc": "atomberg"}).json()
    assert case_id in [c["id"] for c in pending]

    bad = client.post(f"/reviews/{case_id}/decision", json={"decision": "corrected", "reviewer": "analyst"})
    assert bad.status_code == 422  # a correction needs the right answer

    ok = client.post(f"/reviews/{case_id}/decision",
                     json={"decision": "corrected", "reviewer": "analyst", "final_answer": "310.4 crore", "page": 288})
    assert ok.status_code == 200 and ok.json()["status"] == "corrected"
    assert client.post(f"/reviews/{case_id}/decision", json={"decision": "approved", "reviewer": "x"}).status_code == 404
    assert client.get("/reviews/stats").json()["by_status"]["corrected"] >= 1


def test_unknown_document_is_rejected():
    assert client.get("/memos/not_a_doc").status_code == 404
