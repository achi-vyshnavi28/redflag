"""Human review queue on MongoDB (tested with mongomock, no server needed)."""
import mongomock
import pytest

from redflag.review import ReviewQueue


@pytest.fixture
def queue():
    return ReviewQueue(mongomock.MongoClient()["redflag"]["review_cases"])


VERIFIED = {"verified": True, "found": True, "answer": "4,516.21 lakh", "page": 312}
DECLINED = {"verified": False, "found": False, "answer": "Not verified: quote not on the cited page"}


def test_only_unverified_answers_open_a_case(queue):
    assert queue.route("atomberg", "What was revenue in FY2026?", VERIFIED) is None
    case_id = queue.route("atomberg", "What were current borrowings?", DECLINED)
    assert case_id and [c["id"] for c in queue.pending()] == [case_id]
    assert queue.pending()[0]["reason"] == "declined"


def test_queue_is_oldest_first_and_filters_by_document(queue):
    a = queue.route("atomberg", "q1 about atomberg", DECLINED)
    b = queue.route("madhur_steel", "q2 about madhur", DECLINED)
    assert [c["id"] for c in queue.pending()] == [a, b]
    assert [c["id"] for c in queue.pending(doc="madhur_steel")] == [b]


def test_decision_is_audited_and_cannot_be_made_twice(queue):
    case_id = queue.route("madhur_steel", "What were unsecured loans?", DECLINED)
    case = queue.decide(case_id, "corrected", reviewer="analyst@fund", final_answer="9,123.93 lakh", page=440,
                        note="summary table mislabels them")
    assert case["status"] == "corrected" and case["page"] == 440
    assert [h["action"] for h in case["history"]] == ["opened", "corrected"]
    with pytest.raises(KeyError):
        queue.decide(case_id, "approved", reviewer="someone")
    assert queue.pending() == []


def test_corrections_become_regression_tests_and_stats(queue):
    c1 = queue.route("atomberg", "q1", DECLINED)
    c2 = queue.route("atomberg", "q2", DECLINED)
    queue.decide(c1, "corrected", "a", final_answer="42 crore", page=10)
    queue.decide(c2, "approved", "a")
    tests = queue.new_test_questions()
    assert tests == [{"doc": "atomberg", "question": "q1", "expected": "42 crore", "page": 10, "source": f"review:{c1}"}]
    assert queue.stats()["agent_right_when_unsure"] == 0.5


def test_corrected_needs_an_answer(queue):
    case_id = queue.route("atomberg", "q", DECLINED)
    with pytest.raises(ValueError):
        queue.decide(case_id, "corrected", "a")
