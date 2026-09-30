"""HTTP API so RedFlag can be wired into a customer's tools (deal CRM, data room, Slack bot, n8n).

    uvicorn redflag.api:app --port 8900
    POST /ask        {"doc": "madhur_steel", "question": "..."}   -> verified answer with page and quote
    POST /memo       {"doc": "madhur_steel"}                        -> red-flag memo (markdown + facts)
    POST /feedback   {"doc", "question", "answer", "correct", "comment"} -> appended to the improvement log
    GET  /docs_list  available prospectuses
    GET  /reviews?doc=              pending human-review cases (unverified answers), oldest first   [MongoDB]
    POST /reviews/{id}/decision     analyst approves, corrects or rejects a case (audited)
    GET  /reviews/stats             decisions by status, and how often the agent was right when unsure
    GET  /memos/{doc}               stored memos for a document                                     [local or AWS S3]
"""

import json
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from redflag.config import DOCS, MODELS, REPORTS

app = FastAPI(title="RedFlag", description="Cited Q&A and red-flag memos over Indian IPO prospectuses")
# the React review console (web/) calls this API from the browser
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("REDFLAG_CORS", "http://localhost:5174").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
FEEDBACK = REPORTS / "feedback.jsonl"


@lru_cache
def review_queue():
    from redflag.review import ReviewQueue

    if os.getenv("REDFLAG_MONGO_URI"):
        return ReviewQueue()
    import mongomock  # no Mongo configured: in-memory queue so the API still runs locally and in CI

    return ReviewQueue(mongomock.MongoClient()["redflag"]["review_cases"])


class DecisionIn(BaseModel):
    decision: Literal["approved", "corrected", "rejected"]
    reviewer: str = Field(min_length=1, max_length=80)
    final_answer: str = ""
    page: int | None = None
    note: str = ""


class AskIn(BaseModel):
    doc: str
    question: str = Field(min_length=5, max_length=500)
    model: str | None = None


class MemoIn(BaseModel):
    doc: str
    model: str | None = None


class FeedbackIn(BaseModel):
    doc: str
    question: str
    answer: str
    correct: bool
    comment: str = ""


def _check(doc: str, model: str | None) -> None:
    if doc not in DOCS:
        raise HTTPException(404, f"unknown doc '{doc}'; choose from {list(DOCS)}")
    if model and model not in MODELS:
        raise HTTPException(422, f"unknown model '{model}'; choose from {list(MODELS)}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "docs": len(DOCS)}


@app.get("/docs_list")
def docs_list() -> dict:
    return DOCS


@app.post("/ask")
def ask_endpoint(body: AskIn) -> dict:
    from redflag.qa import ask

    _check(body.doc, body.model)
    t = time.time()
    r = ask(body.question, body.doc, "full", body.model)
    case = review_queue().route(body.doc, body.question, r)  # unverified answers go to a human, not to the user
    return {**r, "wall_s": round(time.time() - t, 2), "review_case": case}


@app.post("/memo")
def memo_endpoint(body: MemoIn) -> dict:
    from redflag.memo import run

    from redflag.storage import get_store

    _check(body.doc, body.model)
    state, md = run(body.doc, body.model)
    stored = get_store().put_memo(body.doc, md)
    return {"markdown": md, "flags": state["flags"], "facts": state["facts"], "stored": stored}


@app.get("/memos/{doc}")
def memos(doc: str) -> list[str]:
    from redflag.storage import get_store

    _check(doc, None)
    return get_store().list_memos(doc)


@app.get("/reviews")
def reviews(doc: str | None = None) -> list[dict]:
    return review_queue().pending(doc)


@app.get("/reviews/stats")
def review_stats() -> dict:
    return review_queue().stats()


@app.post("/reviews/{case_id}/decision")
def decide(case_id: str, body: DecisionIn) -> dict:
    try:
        return review_queue().decide(case_id, body.decision, body.reviewer, body.final_answer, body.page, body.note)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/feedback")
def feedback(body: FeedbackIn) -> dict:
    REPORTS.mkdir(exist_ok=True)
    with FEEDBACK.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**body.model_dump(), "at": datetime.now(timezone.utc).isoformat()}) + "\n")
    return {"logged": True}
