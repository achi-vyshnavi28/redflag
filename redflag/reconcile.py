"""Reconciliation agent: does the filing agree with itself?

A diligence analyst's most valuable catch is often not a single number but two numbers that should match and don't.
Single-question RAG can't see this, because each section is internally consistent. This agent, for each key figure:

  retrieve   every passage that could state the figure (several phrasings, broad recall)
  extract    every statement of it: value, unit, as-of date, the label exactly as printed, page, verbatim quote
  verify     each quote must be on its page and contain the value (same check as the Q&A agent)
  normalise  to ₹ crore in Python; group statements by as-of date
  judge      where values for the same date disagree, the LLM classifies the gap:
               definition   different line items / scope (e.g. short-term borrowings vs incl. current maturities)
               conflict     the filing states the same thing two different ways -> red flag, with both pages

    python -m redflag.reconcile madhur_steel
    python -m evals.reconcile_eval
"""

import json
import sys
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, field_validator

from redflag.config import DEFAULT_MODEL, DOCS, REPORTS
from redflag.index import search
from redflag.llm import call
from redflag.qa import TO_CRORE, _norm_unit, _num, check_citation

TARGETS = [
    {"key": "borrowings_breakdown", "label": "total borrowings outstanding at the latest date, and how much of it is secured vs unsecured",
     "queries": ["total secured borrowings outstanding", "unsecured borrowings sub-total", "total outstanding borrowings fund based"]},
    {"key": "tax_proceedings", "label": "number of tax proceedings (direct and indirect) pending against the Company itself",
     "queries": ["number of tax proceedings pending against the company", "direct tax indirect tax cases company amount involved"]},
    {"key": "litigation_against_company", "label": "aggregate amount involved in litigation against the Company",
     "queries": ["aggregate amount involved litigation against the company", "outstanding litigation against our company amount"]},
    {"key": "revenue_fy26", "label": "revenue from operations for Fiscal 2026 (year ended March 31, 2026)",
     "queries": ["revenue from operations fiscal 2026", "revenue from operations March 31, 2026"]},
    {"key": "equity_fy26", "label": "total equity as at March 31, 2026",
     "queries": ["total equity as at March 31, 2026", "net worth March 31 2026"]},
]


# ~4.5k tokens of context: fits free-tier per-minute limits (Groq: 8k tokens/min), so one call can always go through
MAX_PASSAGES = 12


class Mention(BaseModel):
    value: float
    unit: str | None = None  # lakhs / million / crore / count
    as_of: str = ""  # e.g. "2026-03-31", "2026-08-31", "Fiscal 2026"
    label: str = ""  # the row / line label exactly as printed
    page: int
    quote: str

    _v = field_validator("value", "page", mode="before")(lambda cls, v: _num(v))


class Mentions(BaseModel):
    mentions: list[Mention] = []


class Verdict(BaseModel):
    verdict: Literal["definition", "conflict"]
    explanation: str


EXTRACT = """You are reconciling an Indian IPO prospectus (DRHP). Find EVERY statement of this figure in the passages:
  {label}
For each statement give: value (number as printed), unit (lakhs / million / crore, or count for a number of cases),
as_of (the date or fiscal year it refers to), label (the row or line label exactly as printed, including words like
Secured, Unsecured, Sub-Total, Total, Direct tax), page (the [page N] header), quote (short verbatim span containing the value).
Include partial figures that make up the total (sub-totals, secured / unsecured parts, direct / indirect tax cases).
Return JSON {{"mentions": [...]}}; empty list if the figure is not stated."""

JUDGE = """Two statements in the same Indian IPO prospectus give different numbers for what looks like the same figure.
Decide:
  "definition" if they measure different things (different line item, scope, basis, or one is a part of the other),
  "conflict" if the document states the SAME thing inconsistently (e.g. a total labelled "secured" that includes
  amounts shown elsewhere as unsecured, or two different counts for the same set of cases).
Return JSON {"verdict": "definition" | "conflict", "explanation": "<one or two sentences citing both pages>"}."""


def to_common(m: dict, page_unit: str | None) -> float | None:
    if (m.get("unit") or "").lower().startswith(("count", "case", "number")):
        return m["value"]
    u = _norm_unit(m.get("unit")) or page_unit
    return round(m["value"] * TO_CRORE[u], 2) if u in TO_CRORE else None


def reconcile_target(doc: str, target: dict, model: str) -> dict:
    seen, passages = set(), []
    ranked = [search(q, doc, "hybrid", 12, "bge") for q in target["queries"]]
    for rank in range(12):  # interleave the queries' results so each phrasing gets its best passages in
        for hits in ranked:
            if rank < len(hits) and hits[rank]["id"] not in seen:
                seen.add(hits[rank]["id"])
                passages.append(hits[rank])
    passages = passages[:MAX_PASSAGES]
    context = "\n\n".join(f"[page {p['page']}" + (f" | unit: ₹ {p['unit']}" if p.get("unit") else "") + f"]\n{p['text']}" for p in passages)
    found, _ = call(model, EXTRACT.format(label=target["label"]), context, Mentions)
    unit_of = {p["page"]: p.get("unit") for p in passages}
    verified, dropped = [], 0
    for m in found.mentions:
        if check_citation(doc, m.page, m.quote, m.value) is None:
            d = m.model_dump()
            d["common"] = to_common(d, unit_of.get(m.page))
            verified.append(d)
        else:
            dropped += 1
    # compare statements that share a label-free as-of date; only the headline (non-part) figures are compared directly,
    # parts are shown to the judge as context
    findings, judged = [], set()
    for a, b in combinations([m for m in verified if m["common"] is not None], 2):
        if a["as_of"].strip().lower() != b["as_of"].strip().lower() or a["page"] == b["page"]:
            continue
        if abs(a["common"] - b["common"]) <= max(0.005 * max(abs(a["common"]), abs(b["common"])), 0.011):
            continue
        pair = tuple(sorted([(a["page"], a["value"]), (b["page"], b["value"])]))
        if pair in judged:
            continue
        judged.add(pair)
        parts = [f"p. {m['page']}: {m['label']} = {m['value']} {m['unit'] or ''} ({m['as_of']})" for m in verified]
        user = (f"Figure: {target['label']}\nStatement A (p. {a['page']}): \"{a['quote']}\" -> {a['label']} = {a['value']} {a['unit'] or ''}\n"
                f"Statement B (p. {b['page']}): \"{b['quote']}\" -> {b['label']} = {b['value']} {b['unit'] or ''}\n"
                f"All verified statements of this figure in the filing:\n" + "\n".join(parts))
        v, _ = call(model, JUDGE, user, Verdict)
        findings.append({"pages": [a["page"], b["page"]], "a": a, "b": b, **v.model_dump()})
    conflicts = [f for f in findings if f["verdict"] == "conflict"]
    return {"target": target["key"], "statements": len(verified), "dropped_unverified": dropped,
            "differences": len(findings), "conflicts": conflicts, "definition_differences": [f for f in findings if f["verdict"] == "definition"]}


def reconcile(doc: str, model: str = DEFAULT_MODEL) -> dict:
    out = {"doc": doc, "company": DOCS[doc]["company"], "targets": [reconcile_target(doc, t, model) for t in TARGETS]}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"reconciliation_{doc}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    res = reconcile(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL)
    for t in res["targets"]:
        print(f"{t['target']}: {t['statements']} statements, {t['differences']} differences, {len(t['conflicts'])} conflicts")
        for c in t["conflicts"]:
            print("   CONFLICT", c["pages"], c["explanation"])
        for c in t["definition_differences"]:
            print("   definition", c["pages"], c["explanation"][:140])
