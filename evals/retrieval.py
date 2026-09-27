"""Which retriever finds the evidence? For every gold question with evidence, does any of the top-k passages contain
the expected figure or name? (recall@k; the answer model cannot cite what retrieval never showed it.)

    python -m evals.retrieval
"""

import json
import time

from evals.run import GOLD
from redflag.config import REPORTS
from redflag.index import search
from redflag.qa import squash

SETUPS = [("bm25", "bm25", "minilm"), ("dense MiniLM", "dense", "minilm"), ("dense BGE-small", "dense", "bge"),
          ("hybrid BM25+MiniLM", "hybrid", "minilm"), ("hybrid BM25+BGE", "hybrid", "bge")]


def recall(mode: str, embedder: str, k: int) -> tuple[float, float, list[str]]:
    hits, misses, t = 0, [], time.time()
    gold = [g for g in GOLD if g["evidence"]]
    for g in gold:
        found = any(squash(g["evidence"]) in squash(p["text"]) for p in search(g["q"], g["doc"], mode, k, embedder))
        hits += found
        if not found:
            misses.append(g["id"])
    return hits / len(gold), (time.time() - t) / len(gold), misses


def main() -> None:
    out = {}
    for label, mode, emb in SETUPS:
        for k in (5, 8):
            try:
                r, sec, misses = recall(mode, emb, k)
            except Exception as e:
                print(label, "skipped:", type(e).__name__, str(e)[:120])
                break
            out[f"{label} @{k}"] = {"recall": round(r, 3), "ms_per_query": round(sec * 1000), "missed": misses}
            print(f"{label:22s} recall@{k} = {r:.3f}  ({sec * 1000:.0f} ms/query)  missed {misses}", flush=True)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "retrieval.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
