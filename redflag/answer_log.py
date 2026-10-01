"""Relational answer log (SQLAlchemy Core; PostgreSQL or MySQL in production, SQLite locally).

Every /ask answer is recorded with what the analyst needs to trust and operate the service: whether the citation was
verified, the page, the model, latency, tokens and cost, and the review case it opened if it was not verified.
Access patterns: recent answers per document (index on doc, asked_at), and service-level reporting in SQL
(verification rate, latency, cost per document) that runs unchanged on PostgreSQL and MySQL.
"""
import os
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, Index, Integer, MetaData, String, Table, Text, case,
                        create_engine, func, insert, select)

metadata = MetaData()
answers = Table(
    "rf_answers", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("doc", String(60), nullable=False),
    Column("question", Text, nullable=False),
    Column("answer", Text),
    Column("verified", Boolean, nullable=False),
    Column("page", Integer),
    Column("model", String(80)),
    Column("latency_s", Float),
    Column("tokens", Integer),
    Column("cost_usd", Float),
    Column("review_case", String(40)),
    Column("asked_at", DateTime(timezone=True), nullable=False),
    Index("ix_rf_answers_doc_time", "doc", "asked_at"),
)


class AnswerLog:
    def __init__(self, url: str | None = None):
        self.engine = create_engine(url or os.getenv("REDFLAG_DB_URL", "sqlite:///reports/answers.sqlite3"), future=True)
        metadata.create_all(self.engine)

    def record(self, doc: str, question: str, result: dict, model: str | None = None, review_case: str | None = None,
               asked_at: datetime | None = None) -> None:
        with self.engine.begin() as c:
            c.execute(insert(answers).values(
                doc=doc, question=question, answer=result.get("answer"), verified=bool(result.get("verified")),
                page=result.get("page"), model=model, latency_s=result.get("latency_s"), tokens=result.get("tokens"),
                cost_usd=result.get("cost_usd"), review_case=review_case, asked_at=asked_at or datetime.now(timezone.utc)))

    def recent(self, doc: str, limit: int = 20) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(answers).where(answers.c.doc == doc).order_by(answers.c.asked_at.desc()).limit(limit))
            return [dict(r._mapping) for r in rows]

    def report(self) -> list[dict]:
        """Per document: answers, verification rate, average and worst latency, total cost."""
        q = (select(answers.c.doc, func.count().label("answers"),
                    func.avg(case((answers.c.verified, 1.0), else_=0.0)).label("verified_rate"),
                    func.avg(answers.c.latency_s).label("avg_latency_s"), func.max(answers.c.latency_s).label("max_latency_s"),
                    func.sum(answers.c.cost_usd).label("cost_usd"))
             .group_by(answers.c.doc).order_by(answers.c.doc))
        out = []
        with self.engine.connect() as c:
            for r in c.execute(q):
                row = dict(r._mapping)
                out.append({k: (round(float(v), 4) if k not in ("doc", "answers") and v is not None else v)
                            for k, v in row.items()})
        return out

    def latency_percentiles(self) -> dict:
        """p50 / p95 computed in Python over the latencies SQL returns (PERCENTILE_CONT is not available in MySQL)."""
        with self.engine.connect() as c:
            xs = sorted(v for (v,) in c.execute(select(answers.c.latency_s).where(answers.c.latency_s.is_not(None))))
        if not xs:
            return {"p50": None, "p95": None}

        def pick(p):
            return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]

        return {"p50": pick(0.5), "p95": pick(0.95)}
