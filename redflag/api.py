"""HTTP API so RedFlag can be wired into a customer's tools (deal CRM, data room, Slack bot, n8n).

    uvicorn redflag.api:app --port 8900
    POST /ask        {"doc": "madhur_steel", "question": "..."}   -> verified answer with page and quote
    POST /memo       {"doc": "madhur_steel"}                        -> red-flag memo (markdown + facts)
    POST /feedback   {"doc", "question", "answer", "correct", "comment"} -> appended to the improvement log
    GET  /docs_list  available prospectuses
"""

import json
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from redflag.config import DOCS, MODELS, REPORTS

app = FastAPI(title="RedFlag", description="Cited Q&A and red-flag memos over Indian IPO prospectuses")
FEEDBACK = REPORTS / "feedback.jsonl"


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
    return {**r, "wall_s": round(time.time() - t, 2)}


@app.post("/memo")
def memo_endpoint(body: MemoIn) -> dict:
    from redflag.memo import run

    _check(body.doc, body.model)
    state, md = run(body.doc, body.model)
    return {"markdown": md, "flags": state["flags"], "facts": state["facts"]}


@app.post("/feedback")
def feedback(body: FeedbackIn) -> dict:
    REPORTS.mkdir(exist_ok=True)
    with FEEDBACK.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**body.model_dump(), "at": datetime.now(timezone.utc).isoformat()}) + "\n")
    return {"logged": True}
