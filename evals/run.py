"""Evaluate answers on the 46-question gold set.

Metrics (per configuration and model):
  accuracy            numeric answers within 0.5% (sign-insensitive: "loss of 67.09" == -67.09); text answers contain
                      every expected name; not-disclosed questions must be declined
  citation accuracy   of answered questions, share whose cited page really contains the expected figure or name
  unsupported rate    answered questions whose answer or citation is wrong (the costly failure in diligence)
  declined correctly  not-disclosed questions the system refused to answer
  latency, cost       per question (cost at list prices; runs used the free tier)

    python -m evals.run naive hybrid units_compute full          # ablation on the default model
    python -m evals.run full --models gemini-3.5-flash-lite gemini-3.8-flash gemma-4-31b
"""

import argparse
import json
import re
import statistics
import time

from redflag.config import REPORTS, ROOT
from redflag.ingest import load_pages
from redflag.qa import CONFIGS, Config, ask, squash

GOLD = json.loads((ROOT / "evals" / "gold.json").read_text(encoding="utf-8"))


def is_correct(g: dict, r: dict) -> bool:
    if g["type"] == "not_disclosed":
        return not r["found"]
    if not r["found"]:
        return False
    if g["type"] == "text":
        text = (r.get("answer") or "").lower()
        return all(k.lower() in text for k in g["keywords"])
    v = r.get("value")
    if v is None:
        return False
    return any(abs(abs(v) - abs(t)) <= max(0.005 * abs(t), 0.011) for t in [g["value"], *g.get("also_accept", [])])


def citation_ok(g: dict, r: dict) -> bool | None:
    if g["type"] == "not_disclosed" or not r["found"]:
        return None
    pages = load_pages(g["doc"])
    cited = {o["page"] for o in r.get("operands") or []} | ({r["page"]} if r.get("page") else set())
    return any(squash(g["evidence"]) in squash(pages.get(p, "")) for p in cited)


def evaluate(cfg: Config, gold: list[dict] = GOLD) -> dict:
    rows = []
    for g in gold:
        t = time.time()
        try:
            r = ask(g["q"], g["doc"], cfg)
        except Exception as e:  # a crash is a wrong answer, and is recorded as such
            r = {"found": False, "answer": f"ERROR {type(e).__name__}: {e}"[:300], "latency_s": round(time.time() - t, 2),
                 "cost_usd": 0, "tokens": 0, "attempts": 0}
        ok, cite = is_correct(g, r), citation_ok(g, r)
        rows.append({"id": g["id"], "type": g["type"], "q": g["q"], "expected": g.get("value", g.get("keywords")),
                     "answer": r.get("answer"), "value": r.get("value"), "unit": r.get("unit"), "page": r.get("page"),
                     "found": r["found"], "correct": ok, "citation_ok": cite, "attempts": r.get("attempts"),
                     "latency_s": r.get("latency_s"), "cost_usd": r.get("cost_usd"), "tokens": r.get("tokens")})
        print(f"  {g['id']} {'OK ' if ok else 'BAD'} cite={cite} {str(r.get('answer'))[:90]}", flush=True)
    return {"config": cfg.name, "model": cfg.model, "summary": summarise(rows), "rows": rows}


def summarise(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["found"] and r["type"] != "not_disclosed"]
    nd = [r for r in rows if r["type"] == "not_disclosed"]
    by_type = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r["correct"])
    lat = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    return {
        "questions": len(rows),
        "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 3),
        "answered": len(answered),
        "citation_accuracy": round(sum(bool(r["citation_ok"]) for r in answered) / len(answered), 3) if answered else None,
        "unsupported_rate": round(sum((not r["correct"]) or (not r["citation_ok"]) for r in answered) / len(answered), 3) if answered else None,
        "declined_correctly": f"{sum(not r['found'] for r in nd)}/{len(nd)}",
        "accuracy_by_type": {t: round(sum(v) / len(v), 2) for t, v in by_type.items()},
        "latency_p50_s": round(statistics.median(lat), 2) if lat else None,
        "cost_per_question_usd": round(sum(r["cost_usd"] or 0 for r in rows) / len(rows), 6),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="*", default=["full"])
    ap.add_argument("--models", nargs="*", default=[None])
    args = ap.parse_args()
    REPORTS.mkdir(exist_ok=True)
    for model in args.models:
        for name in args.configs:
            cfg = CONFIGS[name] if not model else Config(**{**CONFIGS[name].__dict__, "model": model})
            print(f"== {name} / {cfg.model}", flush=True)
            res = evaluate(cfg)
            out = REPORTS / f"eval_{name}_{re.sub(r'[^a-z0-9.-]', '_', cfg.model)}.json"
            out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(res["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
