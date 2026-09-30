"""Human review queue (MongoDB): answers the agent could not verify are routed to an analyst instead of the user.

This is the human-in-the-loop half of the workflow. The agent answers what it can verify against the source page;
anything unverified becomes a review case. An analyst approves, corrects or rejects it, every decision is kept in an
audit trail on the case, and corrected answers become new test questions for the evaluation set.

Document design (collection `review_cases`):
    {_id, doc, question, agent_answer, reason, status: pending|approved|corrected|rejected,
     created_at, decided_at, reviewer, final_answer, page, history: [{at, action, by, note}]}
Indexes: (status, created_at) for the oldest-first queue, (doc, created_at) for a document's history.
"""
import os
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument

Decision = Literal["approved", "corrected", "rejected"]


def _now():
    return datetime.now(timezone.utc)


class ReviewQueue:
    def __init__(self, collection=None):
        if collection is None:
            from pymongo import MongoClient

            collection = MongoClient(os.getenv("REDFLAG_MONGO_URI", "mongodb://localhost:27017"))["redflag"]["review_cases"]
        self.col = collection
        self.col.create_index([("status", ASCENDING), ("created_at", ASCENDING)], name="queue")
        self.col.create_index([("doc", ASCENDING), ("created_at", DESCENDING)], name="by_doc")

    def route(self, doc: str, question: str, result: dict) -> str | None:
        """Called after every answer. Verified answers go straight to the user; the rest open a case (returns its id)."""
        if result.get("verified"):
            return None
        case = {"doc": doc, "question": question, "agent_answer": result.get("answer", ""),
                "reason": "declined" if not result.get("found") else "citation not verified",
                "page": result.get("page"), "status": "pending", "created_at": _now(),
                "history": [{"at": _now(), "action": "opened", "by": "agent", "note": result.get("answer", "")}]}
        return str(self.col.insert_one(case).inserted_id)

    def pending(self, doc: str | None = None, limit: int = 50) -> list[dict]:
        q = {"status": "pending", **({"doc": doc} if doc else {})}
        return [self._out(c) for c in self.col.find(q).sort("created_at", ASCENDING).limit(limit)]

    def decide(self, case_id: str, decision: Decision, reviewer: str, final_answer: str = "", page: int | None = None,
               note: str = "") -> dict:
        if decision == "corrected" and not final_answer:
            raise ValueError("a corrected case needs the correct answer")
        update = {"$set": {"status": decision, "decided_at": _now(), "reviewer": reviewer,
                           "final_answer": final_answer or None, **({"page": page} if page else {})},
                  "$push": {"history": {"at": _now(), "action": decision, "by": reviewer, "note": note}}}
        case = self.col.find_one_and_update({"_id": ObjectId(case_id), "status": "pending"}, update,
                                            return_document=ReturnDocument.AFTER)
        if case is None:
            raise KeyError("case not found or already decided")
        return self._out(case)

    def stats(self) -> dict:
        counts = {r["_id"]: r["n"] for r in self.col.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
        decided = sum(counts.get(s, 0) for s in ("approved", "corrected", "rejected"))
        return {"by_status": counts, "agent_right_when_unsure": round(counts.get("approved", 0) / decided, 2) if decided else None}

    def new_test_questions(self) -> list[dict]:
        """Corrected cases, in the evaluation set's format, so every human correction becomes a regression test."""
        return [{"doc": c["doc"], "question": c["question"], "expected": c["final_answer"], "page": c.get("page"),
                 "source": f"review:{c['_id']}"} for c in self.col.find({"status": "corrected"})]

    @staticmethod
    def _out(c: dict) -> dict:
        return {**{k: v for k, v in c.items() if k != "_id"}, "id": str(c["_id"])}
