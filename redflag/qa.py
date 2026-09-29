"""Question answering over one prospectus, as a LangGraph agent:

    retrieve -> extract -> [compute] -> verify -> (retry extract once | finalise)

Four switches turn each reliability step on, so each one's effect can be measured (evals/run.py):
  hybrid   BM25 + embeddings instead of embeddings alone
  units    each passage is labelled with its page's reporting unit (₹ lakhs / million / crore)
  compute  the model extracts operands with citations; Python does the arithmetic and unit conversion
  verify   the quote must exist on the cited page and contain the number; otherwise retry once, then abstain
"""

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, field_validator

from redflag.config import DEFAULT_MODEL
from redflag.index import search
from redflag.ingest import load_pages
from redflag.llm import call

TO_CRORE = {"lakhs": 0.01, "million": 0.1, "crore": 1.0, "billion": 100.0}


@dataclass(frozen=True)
class Config:
    name: str = "full"
    hybrid: bool = True
    units: bool = True
    compute: bool = True
    verify: bool = True
    k: int = 8
    model: str = DEFAULT_MODEL
    embedder: str = "minilm"
    force_compute: bool = False  # growth / conversion questions must go through Python, never a number the model copied


CONFIGS = {
    "naive": Config("naive", hybrid=False, units=False, compute=False, verify=False, k=5),
    "hybrid": Config("hybrid", hybrid=True, units=False, compute=False, verify=False),
    "units_compute": Config("units_compute", hybrid=True, units=True, compute=True, verify=False),
    "full_v1": Config("full_v1"),
    # v2: retrieval chosen by measurement (evals/retrieval.py: dense BGE recall@8 0.95 vs hybrid 0.88) + forced compute
    "full": Config("full", hybrid=False, embedder="bge", force_compute=True, k=12),
}
NEEDS_COMPUTE = re.compile(r"(percent|percentage|growth|grow|change|increase|decrease|in (rupees )?crore|expressed in)", re.I)


def _num(v):
    """Models return numbers as 18628.02, "18,628.02", "(1,488.81)" or "₹ 4,500.00 million"; normalise all of them."""
    if v is None or isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    m = re.search(r"\d[\d,]*\.?\d*", s)
    return None if not m else (-1 if neg else 1) * float(m.group(0).replace(",", ""))


class Operand(BaseModel):
    label: str = ""
    value: float
    unit: str | None = None
    page: int
    quote: str = ""

    _v = field_validator("value", "page", mode="before")(lambda cls, v: _num(v))


class Extraction(BaseModel):
    found: bool = Field(description="false if the passages do not contain the answer")
    answer: str = ""
    value: float | None = None
    unit: str | None = None
    page: int | None = None
    quote: str | None = None
    operation: Literal["none", "growth_pct", "convert_to_crore"] = "none"
    operands: list[Operand] = []

    _v = field_validator("value", "page", mode="before")(lambda cls, v: _num(v))
    _op = field_validator("operation", mode="before")(lambda cls, v: v if v in ("growth_pct", "convert_to_crore") else "none")
    _ops = field_validator("operands", mode="before")(lambda cls, v: v or [])
    _s = field_validator("answer", mode="before")(lambda cls, v: "" if v is None else str(v))


SYSTEM = """You are a diligence analyst reading an Indian IPO prospectus (DRHP). Answer ONLY from the passages given.
Rules:
- If the passages do not contain the answer, return found=false. Never guess or use outside knowledge.
- page: the page number shown in the passage header you used. quote: a short verbatim span copied exactly from that passage, containing the answer.
- value: the number exactly as the document states it (negative for a loss); unit: the unit it is stated in.
- Tables list several years side by side; read the column for the year asked.
Return JSON with keys: found, answer, value, unit, page, quote{extra_keys}."""
COMPUTE_RULES = """
- If the question needs arithmetic (growth %, change %) or a unit conversion (e.g. to crore), do NOT calculate.
  Set operation to "growth_pct" or "convert_to_crore" and list the raw numbers in operands, each with label, value, unit, page and quote.
  For growth_pct give operands in order [earlier period, later period]."""
UNIT_RULE = "\n- Each passage header states its reporting unit (e.g. ₹ lakhs or ₹ million). Use it as the unit of numbers from that passage."


class State(TypedDict, total=False):
    question: str
    doc: str
    cfg: Config
    passages: list[dict]
    ex: Extraction
    result: dict
    feedback: str
    attempts: int
    calls: list[dict]
    trace: list[dict]


def _context(passages: list[dict], units: bool) -> str:
    parts = []
    for p in passages:
        head = f"[page {p['page']}" + (f" | unit: ₹ {p['unit']}" if units and p.get("unit") else "") + "]"
        parts.append(f"{head}\n{p['text']}")
    return "\n\n".join(parts)


def retrieve(state: State) -> State:
    cfg = state["cfg"]
    return {"passages": search(state["question"], state["doc"], "hybrid" if cfg.hybrid else "dense", cfg.k, cfg.embedder)}


def extract(state: State) -> State:
    cfg = state["cfg"]
    system = SYSTEM.format(extra_keys=", operation, operands" if cfg.compute else "") + (UNIT_RULE if cfg.units else "") + (COMPUTE_RULES if cfg.compute else "")
    user = f"Question: {state['question']}\n\nPassages:\n{_context(state['passages'], cfg.units)}"
    if state.get("feedback"):
        user += f"\n\nYour previous answer failed verification: {state['feedback']} Re-read the passages and answer again, or return found=false."
    ex, meta = call(cfg.model, system, user, Extraction)
    return {"ex": ex, "attempts": state.get("attempts", 0) + 1, "calls": state.get("calls", []) + [meta]}


def compute(state: State) -> State:
    ex = state["ex"]
    ops = ex.operands
    try:
        if ex.operation == "growth_pct" and len(ops) >= 2:
            a, b = ops[0], ops[-1]
            value, unit = (b.value / a.value - 1) * 100, "percent"
        elif ex.operation == "convert_to_crore" and ops:
            src = _norm_unit(ops[0].unit) or _page_unit(state, ops[0].page)
            value, unit = ops[0].value * TO_CRORE[src], "crore"
        else:
            return {}
    except (KeyError, ZeroDivisionError, TypeError):
        return {"ex": ex.model_copy(update={"found": False, "answer": "Could not compute from the cited figures."})}
    return {"ex": ex.model_copy(update={"found": True, "value": round(value, 2), "unit": unit, "page": ops[-1].page, "quote": ops[-1].quote,
                                        "answer": f"{value:,.2f} {unit} (computed from cited figures)"})}


def _page_unit(state: State, page: int) -> str | None:
    return next((p.get("unit") for p in state["passages"] if p["page"] == page and p.get("unit")), None)


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    u = u.lower()
    return next((k for k in TO_CRORE if k.rstrip("s") in u), None)


@lru_cache(maxsize=8)
def _pages(doc: str) -> dict[int, str]:
    return load_pages(doc)


def squash(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s).lower()


def numbers_in(s: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", s or "") if x.replace(",", "").replace(".", "")]


def check_citation(doc: str, page: int | None, quote: str | None, value: float | None) -> str | None:
    """Return a reason if the citation fails, None if it holds."""
    if not page or not quote:
        return "no page or quote given."
    text = _pages(doc).get(page)
    if text is None:
        return f"page {page} does not exist."
    if squash(quote) not in squash(text):
        return f"the quote was not found on page {page}."
    if value is not None and not any(abs(abs(n) - abs(value)) < 0.006 for n in numbers_in(quote)):
        return f"the value {value} does not appear in the quote."
    return None


def verify(state: State) -> State:
    ex, doc = state["ex"], state["doc"]
    if not ex.found:
        return {"feedback": ""}
    if state["cfg"].force_compute and NEEDS_COMPUTE.search(state["question"]) and ex.operation == "none":
        return {"feedback": "this question needs a calculation. Do not copy a percentage or converted figure from the text "
                            "(it may be for a different line item); return the raw figures as operands with operation set."}
    if ex.operation != "none" and ex.operands:
        reasons = [r for o in ex.operands if (r := check_citation(doc, o.page, o.quote, o.value))]
    else:
        reasons = [r] if (r := check_citation(doc, ex.page, ex.quote, ex.value)) else []
    return {"feedback": " ".join(reasons)}


def after_verify(state: State) -> str:
    if not state.get("feedback"):
        return "finalise"
    return "extract" if state["attempts"] < 2 else "abstain"


def abstain(state: State) -> State:
    return {"ex": state["ex"].model_copy(update={"found": False, "answer": f"Not verified: {state['feedback']}"})}


def finalise(state: State) -> State:
    ex = state["ex"]
    calls = state.get("calls", [])
    return {"result": {**ex.model_dump(), "verified": state["cfg"].verify and ex.found,
                       "attempts": state.get("attempts", 1), "latency_s": round(sum(c["latency_s"] for c in calls), 2),
                       "cost_usd": round(sum(c["cost_usd"] for c in calls), 6),
                       "tokens": sum(c["tokens_in"] + c["tokens_out"] for c in calls),
                       "pages_retrieved": [p["page"] for p in state["passages"]], "trace": state.get("trace", [])}}


def _summary(step: str, state: State, out: State) -> str:
    """One readable line per step for the trace (shown under every answer in the app and returned by the API)."""
    if step == "retrieve":
        pages = sorted({p["page"] for p in out["passages"]})
        return f"{len(out['passages'])} passages from pages {', '.join(map(str, pages[:10]))}{' ...' if len(pages) > 10 else ''}"
    if step == "extract":
        ex, meta = out["ex"], out["calls"][-1]
        what = f"operands for {ex.operation}" if ex.operation != "none" else (f"value {ex.value} {ex.unit or ''} on p. {ex.page}" if ex.found else "not found")
        return (f"attempt {out['attempts']} with {meta.get('model', state['cfg'].model)}{' (cached)' if meta.get('cached') else ''}: "
                f"{what}; {meta.get('tokens_in', 0) + meta.get('tokens_out', 0)} tokens, ${meta.get('cost_usd', 0):.5f}")
    if step == "compute":
        return f"Python computed {out['ex'].value} {out['ex'].unit}" if out else "nothing to compute"
    if step == "verify":
        return "citation verified: quote found on the page and contains the number" if not out["feedback"] else f"failed: {out['feedback']}"
    if step == "abstain":
        return "declined: could not verify an answer"
    return ""


def traced(step: str, fn):
    def run(state: State) -> State:
        t = time.perf_counter()
        out = fn(state) or {}
        if step == "finalise":
            return out
        entry = {"step": step, "ms": round((time.perf_counter() - t) * 1000), "detail": _summary(step, state, out)}
        return {**out, "trace": state.get("trace", []) + [entry]}
    return run


@lru_cache(maxsize=None)
def graph(verify_on: bool, compute_on: bool):
    g = StateGraph(State)
    for name, fn in (("retrieve", retrieve), ("extract", extract), ("compute", compute), ("verify", verify),
                     ("abstain", abstain), ("finalise", finalise)):
        g.add_node(name, traced(name, fn))
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "extract")
    g.add_edge("extract", "compute" if compute_on else ("verify" if verify_on else "finalise"))
    if compute_on:
        g.add_edge("compute", "verify" if verify_on else "finalise")
    if verify_on:
        g.add_conditional_edges("verify", after_verify, {"extract": "extract", "abstain": "abstain", "finalise": "finalise"})
        g.add_edge("abstain", "finalise")
    g.add_edge("finalise", END)
    return g.compile()


def ask(question: str, doc: str, cfg: Config | str = "full", model: str | None = None) -> dict:
    cfg = CONFIGS[cfg] if isinstance(cfg, str) else cfg
    if model:
        cfg = Config(**{**cfg.__dict__, "model": model})
    return graph(cfg.verify, cfg.compute).invoke({"question": question, "doc": doc, "cfg": cfg})["result"]


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(ask(sys.argv[2], sys.argv[1]), indent=2, ensure_ascii=False))
