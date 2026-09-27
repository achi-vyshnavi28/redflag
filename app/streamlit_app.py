"""RedFlag demo: ask a prospectus a question and see the cited page; read the red-flag memos; see the evals.

    streamlit run app/streamlit_app.py
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# On Streamlit Cloud, keys come from the app's Secrets settings (never from the repo).
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

from redflag.config import DOCS, REPORTS  # noqa: E402

st.set_page_config(page_title="RedFlag", layout="wide")
st.title("RedFlag")
st.caption("Diligence answers from Indian IPO prospectuses (DRHPs filed with SEBI). Every answer cites its page, "
           "and is automatically checked against that page before it is shown.")

doc = st.selectbox("Prospectus", list(DOCS), format_func=lambda d: f"{DOCS[d]['company']} (filed {DOCS[d]['filed']})")
ask_tab, memo_tab, eval_tab = st.tabs(["Ask", "Red-flag memo", "How reliable is it?"])

with ask_tab:
    examples = ["What were current borrowings as at March 31, 2026?", "By what percentage did revenue grow from Fiscal 2025 to Fiscal 2026?",
                "What was revenue from operations in Fiscal 2026 expressed in rupees crore?", "Who are the promoters of the company?",
                "What revenue does the company forecast for Fiscal 2028?"]
    q = st.text_input("Question", value=examples[0])
    st.caption("Try: " + " · ".join(examples[1:]))
    if st.button("Ask", type="primary") and q.strip():
        from redflag.ingest import load_pages
        from redflag.qa import ask

        with st.spinner("Retrieving, extracting and checking the citation..."):
            r = ask(q, doc)
        if r["found"]:
            st.success(r["answer"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Cited page", r["page"])
            c2.metric("Verified", "yes" if r["verified"] else "no")
            c3.metric("Time", f"{r['latency_s']} s")
            for o in r.get("operands") or []:
                st.markdown(f"- operand **{o['label']}**: {o['value']:,} {o.get('unit') or ''} (p. {o['page']})")
            with st.expander(f"Page {r['page']} of the prospectus"):
                text = load_pages(doc).get(r["page"], "")
                st.text(text.replace(r["quote"] or "\u0000", f">>> {r['quote']} <<<") if r.get("quote") else text)
        else:
            st.warning(f"No verified answer: {r['answer'] or 'not found in the document'}. RedFlag declines rather than guesses.")

with memo_tab:
    md = REPORTS / f"memo_{doc}.md"
    st.markdown(md.read_text(encoding="utf-8") if md.exists() else "Memo not generated yet: `python -m redflag.memo " + doc + "`")

with eval_tab:
    rows = []
    for f in sorted(REPORTS.glob("eval_*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        rows.append({"config": s["config"], "model": s["model"], **{k: v for k, v in s["summary"].items() if k != "accuracy_by_type"}})
    if rows:
        st.markdown("46 questions with known answers across the three prospectuses (numbers in tables, text facts, "
                    "growth calculations, unit conversions, and questions whose answer is not in the document).")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    rp = REPORTS / "retrieval.json"
    if rp.exists():
        st.markdown("**Retrieval: does the right passage reach the model?** (recall@k)")
        st.dataframe(pd.DataFrame([{"retriever": k, **{kk: vv for kk, vv in v.items() if kk != "missed"}} for k, v in json.loads(rp.read_text()).items()]),
                     hide_index=True, use_container_width=True)
