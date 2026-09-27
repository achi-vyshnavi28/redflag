"""Red-flag diligence memo for one prospectus, as a multi-agent LangGraph workflow.

    financials ─┐
    leverage   ─┤
    litigation ─┼─> red_flags (Python rules on verified numbers) -> write_memo (LLM) -> check_memo (no new numbers)
    offer      ─┘

Each section agent asks its checklist through the verified QA agent (redflag.qa), so every fact carries a page.
Balance-sheet and P&L questions name the restated statements: a DRHP prints several "borrowings" figures under different
definitions (short-term only, incl. leases, as per the lender certificate), and mixing them makes ratios meaningless.
The memo writer may only use those facts; any number in the memo that is not in a fact is caught and removed.

    python -m redflag.memo madhur_steel
"""

import json
import operator
import re
import sys
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from redflag.config import DEFAULT_MODEL, DOCS, REPORTS
from redflag.llm import call
from redflag.qa import TO_CRORE, _norm_unit, ask, numbers_in

CHECKLIST = {
    "financials": [
        ("revenue_fy26", "What was revenue from operations in Fiscal 2026 in the restated statement of profit and loss?"),
        ("revenue_fy25", "What was revenue from operations in Fiscal 2025 in the restated statement of profit and loss?"),
        ("revenue_fy24", "What was revenue from operations in Fiscal 2024 in the restated statement of profit and loss?"),
        ("pat_fy26", "What was the restated profit or loss after tax for Fiscal 2026?"),
        ("pat_fy25", "What was the restated profit or loss after tax for Fiscal 2025?"),
        ("pbt_fy26", "What was the restated profit or loss before tax for Fiscal 2026?"),
        ("finance_costs_fy26", "What were the finance costs in Fiscal 2026 in the restated statement of profit and loss?"),
    ],
    "leverage": [
        ("equity_fy26", "What was total equity as at March 31, 2026 in the restated statement of assets and liabilities (balance sheet)?"),
        ("current_borrowings_fy26", "What were current borrowings (financial liabilities) as at March 31, 2026 in the restated statement of assets and liabilities (balance sheet)?"),
        ("noncurrent_borrowings_fy26", "What were non-current borrowings (financial liabilities) as at March 31, 2026 in the restated statement of assets and liabilities (balance sheet)?"),
        ("receivables_fy26", "What were trade receivables as at March 31, 2026 in the restated statement of assets and liabilities (balance sheet)?"),
        ("receivables_fy25", "What were trade receivables as at March 31, 2025 in the restated statement of assets and liabilities (balance sheet)?"),
        ("inventories_fy26", "What were inventories as at March 31, 2026 in the restated statement of assets and liabilities (balance sheet)?"),
        ("inventories_fy25", "What were inventories as at March 31, 2025 in the restated statement of assets and liabilities (balance sheet)?"),
    ],
    "litigation": [
        ("litigation_against_company", "What is the aggregate amount involved in outstanding litigation against the Company?"),
        ("criminal_against_promoters", "How many criminal proceedings are pending against the Promoters?"),
        ("litigation_against_promoters", "How many material civil litigations are pending against the Promoters?"),
    ],
    "offer": [
        ("promoters", "Who are the promoters of the company?"),
        ("fresh_issue", "What is the size of the fresh issue?"),
        ("offer_for_sale", "How many equity shares are offered in the offer for sale by selling shareholders?"),
        ("objects", "What are the objects of the issue, i.e. how will the fresh issue proceeds be used?"),
    ],
}


class Memo(BaseModel):
    headline: str
    summary: str
    red_flags: list[str]
    questions_for_management: list[str]


class State(TypedDict, total=False):
    doc: str
    model: str
    facts: Annotated[list[dict], operator.add]
    flags: list[dict]
    memo: dict
    dropped: list[str]


def _section(name: str):
    def run(state: State) -> State:
        facts = []
        for key, q in CHECKLIST[name]:
            r = ask(q, state["doc"], "full", state.get("model"))
            crore = None
            if r["found"] and r.get("value") is not None and (u := _norm_unit(r.get("unit"))):
                crore = round(r["value"] * TO_CRORE[u], 2)
            facts.append({"section": name, "key": key, "question": q, "found": r["found"], "answer": r["answer"],
                          "value": r.get("value"), "unit": r.get("unit"), "crore": crore, "page": r.get("page"),
                          "quote": r.get("quote"), "cost_usd": r["cost_usd"], "latency_s": r["latency_s"]})
        return {"facts": facts}
    return run


def red_flags(state: State) -> State:
    f = {x["key"]: x for x in state["facts"] if x["found"]}
    v = {k: x["crore"] if x["crore"] is not None else x["value"] for k, x in f.items()}
    flags = []

    def flag(rule: str, detail: str, keys: list[str], severity: str) -> None:
        flags.append({"rule": rule, "detail": detail, "severity": severity, "pages": sorted({f[k]["page"] for k in keys if k in f and f[k]["page"]})})

    if "pat_fy26" in v and v["pat_fy26"] < 0:
        flag("Loss-making", f"Restated loss of ₹{abs(v['pat_fy26']):,.2f} crore in Fiscal 2026.", ["pat_fy26"], "high")
    if {"revenue_fy26", "revenue_fy25"} <= v.keys():
        g = (v["revenue_fy26"] / v["revenue_fy25"] - 1) * 100
        if g < 0:
            flag("Revenue decline", f"Revenue fell {abs(g):.1f}% from Fiscal 2025 to Fiscal 2026.", ["revenue_fy26", "revenue_fy25"], "high")
        for item, label in (("receivables", "Trade receivables"), ("inventories", "Inventories")):
            if {f"{item}_fy26", f"{item}_fy25"} <= v.keys() and v[f"{item}_fy25"]:
                gi = (v[f"{item}_fy26"] / v[f"{item}_fy25"] - 1) * 100
                if gi - g > 20:
                    flag(f"{label} outgrowing revenue", f"{label} grew {gi:.1f}% vs revenue {g:.1f}%: check collection / stock build-up.",
                         [f"{item}_fy26", f"{item}_fy25", "revenue_fy26", "revenue_fy25"], "medium")
    debt = sum(v.get(k, 0) or 0 for k in ("current_borrowings_fy26", "noncurrent_borrowings_fy26"))
    if v.get("equity_fy26") and debt:
        de = debt / v["equity_fy26"]
        if de > 1.0:
            flag("High leverage", f"Borrowings are {de:.2f}x total equity (₹{debt:,.2f} crore vs ₹{v['equity_fy26']:,.2f} crore).",
                 ["current_borrowings_fy26", "noncurrent_borrowings_fy26", "equity_fy26"], "high" if de > 2 else "medium")
    if {"pbt_fy26", "finance_costs_fy26"} <= v.keys() and v["finance_costs_fy26"]:
        icr = (v["pbt_fy26"] + v["finance_costs_fy26"]) / v["finance_costs_fy26"]
        if icr < 2.5:
            flag("Thin interest cover", f"EBIT covers finance costs {icr:.2f}x in Fiscal 2026.", ["pbt_fy26", "finance_costs_fy26"], "high" if icr < 1.5 else "medium")
    if v.get("litigation_against_company") and v.get("equity_fy26"):
        share = v["litigation_against_company"] / v["equity_fy26"] * 100
        if share > 10:
            flag("Litigation exposure", f"Claims against the company equal {share:.0f}% of total equity.", ["litigation_against_company", "equity_fy26"], "high" if share > 50 else "medium")
    for k, label in (("criminal_against_promoters", "criminal"), ("litigation_against_promoters", "material civil")):
        if (v.get(k) or 0) > 0:
            flag("Promoter litigation", f"{int(v[k])} {label} proceeding(s) pending against the promoters.", [k], "medium")
    if "offer_for_sale" in f and (v.get("offer_for_sale") or 0) > 0:
        flag("Selling shareholders", f"Part of the IPO is an offer for sale: {f['offer_for_sale']['answer']}", ["offer_for_sale"], "info")
    return {"flags": flags}


WRITER = """You write the first page of an investment diligence memo for a private equity / credit committee.
Use ONLY the facts and red flags given. Every sentence with a number must end with its page citation like [p. 86].
Do not introduce any number that is not in the facts or red flags. Be concise, neutral and specific.
Return JSON: headline (one line), summary (4-6 sentences), red_flags (list, most severe first, each with [p. X]),
questions_for_management (4-6 sharp questions a diligence team would ask, grounded in the facts)."""


def write_memo(state: State) -> State:
    facts = [{k: x[k] for k in ("key", "answer", "value", "unit", "crore", "page")} for x in state["facts"] if x["found"]]
    user = json.dumps({"company": DOCS[state["doc"]]["company"], "sector": DOCS[state["doc"]]["sector"],
                       "note": "Money values are also given converted to ₹ crore in 'crore'.", "facts": facts,
                       "red_flags": state["flags"]}, ensure_ascii=False)
    memo, _ = call(state.get("model") or DEFAULT_MODEL, WRITER, user, Memo)
    return {"memo": memo.model_dump()}


def _allowed_numbers(state: State) -> set[float]:
    nums = set()
    for x in state["facts"]:
        for n in [x.get("value"), x.get("crore"), x.get("page")] + numbers_in(x.get("answer") or ""):
            if isinstance(n, (int, float)):
                nums |= {round(abs(n), 2), round(abs(n), 1), round(abs(n))}
    for fl in state["flags"]:
        nums |= {round(n, 2) for n in numbers_in(fl["detail"])} | {round(n, 1) for n in numbers_in(fl["detail"])}
        nums |= set(fl["pages"])
    return nums | {2024, 2025, 2026, 2027, 2028, 31}


def check_memo(state: State) -> State:
    """Guardrail: drop any memo sentence containing a number that is not in the verified facts."""
    allowed, memo, dropped = _allowed_numbers(state), dict(state["memo"]), []

    def clean(text: str) -> str | None:
        bad = [n for n in numbers_in(text) if not ({round(n, 2), round(n, 1), round(n)} & allowed)]
        if bad:
            dropped.append(f"{text} (unverified: {bad})")
            return None
        return text

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z₹])", memo["summary"])  # not inside "[p. 90]"
    memo["summary"] = " ".join(s for s in sentences if clean(s))
    for key in ("red_flags", "questions_for_management"):
        memo[key] = [s for s in memo[key] if clean(s)]
    memo["headline"] = clean(memo["headline"]) or DOCS[state["doc"]]["company"]
    return {"memo": memo, "dropped": dropped}


def build_graph():
    g = StateGraph(State)
    for name in CHECKLIST:
        g.add_node(name, _section(name))
        g.add_edge(START, name)
    g.add_node("red_flags", red_flags)
    g.add_node("write_memo", write_memo)
    g.add_node("check_memo", check_memo)
    for name in CHECKLIST:
        g.add_edge(name, "red_flags")
    g.add_edge("red_flags", "write_memo")
    g.add_edge("write_memo", "check_memo")
    g.add_edge("check_memo", END)
    return g.compile()


def to_markdown(doc: str, s: State) -> str:
    m, info = s["memo"], DOCS[doc]
    lines = [f"# {info['company']}: red-flag memo", "",
             f"*Source: Draft Red Herring Prospectus filed with SEBI on {info['filed']} ({info['basis']} financials). "
             f"Generated by RedFlag; every figure cites its DRHP page and passed automatic citation checks. Not investment advice.*", "",
             f"**{m['headline']}**", "", m["summary"], "", "## Red flags"]
    lines += [f"- {x}" for x in m["red_flags"]] or ["- None found by the rules."]
    lines += ["", "## Questions for management"] + [f"- {x}" for x in m["questions_for_management"]]
    lines += ["", "## Verified facts", "", "| Item | Answer | Page |", "|---|---|---|"]
    lines += [f"| {x['key']} | {x['answer'][:120]} | {x['page'] or '–'} |" for x in s["facts"] if x["found"]]
    missing = [x["key"] for x in s["facts"] if not x["found"]]
    if missing:
        lines += ["", f"*Not found or not verifiable (left out rather than guessed): {', '.join(missing)}.*"]
    if s.get("dropped"):
        lines += ["", f"*Guardrail removed {len(s['dropped'])} memo sentence(s) containing unverified numbers.*"]
    cost = sum(x["cost_usd"] for x in s["facts"])
    lines += ["", f"*{len(s['facts'])} checklist questions; estimated model cost ${cost:.4f} at list prices.*"]
    return "\n".join(lines)


def run(doc: str, model: str | None = None) -> tuple[dict, str]:
    state = build_graph().invoke({"doc": doc, "model": model or DEFAULT_MODEL, "facts": []})
    md = to_markdown(doc, state)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"memo_{doc}.md").write_text(md, encoding="utf-8")
    (REPORTS / f"memo_{doc}.json").write_text(json.dumps({k: state[k] for k in ("facts", "flags", "memo", "dropped")}, indent=2, ensure_ascii=False), encoding="utf-8")
    return state, md


if __name__ == "__main__":
    print(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)[1])
