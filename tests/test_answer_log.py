"""Answer log on SQLite, and on PostgreSQL / MySQL when REDFLAG_TEST_PG_URL / REDFLAG_TEST_MYSQL_URL are set (CI)."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from redflag.answer_log import AnswerLog, metadata

URLS = ["sqlite://"] + [os.environ[k] for k in ("REDFLAG_TEST_PG_URL", "REDFLAG_TEST_MYSQL_URL") if os.getenv(k)]
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(params=URLS, ids=lambda u: u.split(":")[0])
def log(request):
    lg = AnswerLog(request.param)
    metadata.drop_all(lg.engine)
    metadata.create_all(lg.engine)
    return lg


def _fill(log):
    rows = [("atomberg", True, 1.8, 0.0004), ("atomberg", False, 2.2, 0.0005), ("madhur_steel", True, 1.5, 0.0003),
            ("madhur_steel", True, 9.0, 0.0006)]
    for i, (doc, ok, lat, cost) in enumerate(rows):
        log.record(doc, f"question {i}", {"answer": "x", "verified": ok, "page": 10 + i, "latency_s": lat, "tokens": 900,
                                          "cost_usd": cost}, model="gemini-3.5-flash-lite",
                   review_case=None if ok else "case-1", asked_at=T0 + timedelta(minutes=i))


def test_report_by_document(log):
    _fill(log)
    rep = {r["doc"]: r for r in log.report()}
    assert rep["atomberg"]["answers"] == 2 and rep["atomberg"]["verified_rate"] == 0.5
    assert rep["madhur_steel"]["verified_rate"] == 1.0 and rep["madhur_steel"]["max_latency_s"] == 9.0
    assert round(rep["madhur_steel"]["cost_usd"], 4) == 0.0009


def test_recent_answers_newest_first_and_review_link(log):
    _fill(log)
    recent = log.recent("atomberg")
    assert [r["question"] for r in recent] == ["question 1", "question 0"]
    assert recent[0]["review_case"] == "case-1" and not recent[0]["verified"]


def test_latency_percentiles(log):
    _fill(log)
    assert log.latency_percentiles() == {"p50": 2.2, "p95": 9.0}
