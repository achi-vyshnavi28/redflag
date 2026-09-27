"""Quality gate for CI: fail the build if a change makes RedFlag worse.

  retrieval  always runs (no API key needed): recall@8 of the production retriever (BGE) on the gold set >= 0.90
  answers    runs when GEMINI_API_KEY is available (e.g. a GitHub Actions secret): accuracy >= 0.85, and every
             not-in-the-document question declined. Answers already in the committed cache cost nothing.

    python -m evals.gate
"""

import json
import os
import sys

from evals.retrieval import recall
from evals.run import evaluate
from redflag.config import REPORTS
from redflag.qa import CONFIGS

MIN_RECALL, MIN_ACCURACY = 0.90, 0.85


def main() -> int:
    failures, report = [], {}
    r, ms, missed = recall("dense", "bge", 8)
    report["retrieval_recall_at_8"] = round(r, 3)
    print(f"retrieval recall@8 (BGE) = {r:.3f}  (min {MIN_RECALL})  missed {missed}")
    if r < MIN_RECALL:
        failures.append(f"retrieval recall {r:.3f} < {MIN_RECALL}")
    if os.getenv("GEMINI_API_KEY"):
        s = evaluate(CONFIGS["full"])["summary"]
        report["answers"] = s
        print(f"answer accuracy = {s['accuracy']}  (min {MIN_ACCURACY}); declined {s['declined_correctly']}")
        if s["accuracy"] < MIN_ACCURACY:
            failures.append(f"accuracy {s['accuracy']} < {MIN_ACCURACY}")
        n, total = map(int, s["declined_correctly"].split("/"))
        if n < total:
            failures.append(f"answered {total - n} question(s) that are not in the document")
    else:
        print("answer check skipped: no GEMINI_API_KEY (add it as a repository secret to enable)")
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "gate.json").write_text(json.dumps({**report, "failures": failures}, indent=2), encoding="utf-8")
    for f in failures:
        print("GATE FAILED:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
