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
os.environ.setdefault("LLM_MAX_ATTEMPTS", "3")  # a person is waiting: fail fast to a clear message instead of long back-offs

# On Streamlit Cloud, keys come from the app's Secrets settings (never from the repo). Accept keys at the top level or
# inside a [section], in any letter case.
SECRETS_STATUS = "no secrets set"
try:
    _names = []
    for _k, _v in st.secrets.items():
        for _kk, _vv in (_v.items() if hasattr(_v, "items") else [(_k, _v)]):
            _names.append(_kk)
            if isinstance(_vv, str) and _vv.strip():
                os.environ[_kk.upper()] = _vv.strip().strip('"').strip("'").strip("“”")
    if _names:
        SECRETS_STATUS = "secret names found: " + ", ".join(_names)
except Exception as _e:  # usually a TOML format error, e.g. a value without quotes
    SECRETS_STATUS = f"secrets could not be read ({type(_e).__name__}): check the format"

from redflag.config import DOCS, REPORTS  # noqa: E402

st.set_page_config(page_title="RedFlag", layout="wide")
st.title("RedFlag")
st.caption("Diligence answers from Indian IPO prospectuses (DRHPs filed with SEBI). Every answer cites its page, "
           "and is automatically checked against that page before it is shown.")

st.sidebar.caption("Model key detected: " + ("yes" if os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") else
                                              "no (example questions still work)"))
doc = st.selectbox("Prospectus", list(DOCS), format_func=lambda d: f"{DOCS[d]['company']} (filed {DOCS[d]['filed']})")
ask_tab, memo_tab, eval_tab = st.tabs(["Ask", "Red-flag memo", "How reliable is it?"])

with ask_tab:
    examples = ["What were current borrowings as at March 31, 2026 in the restated balance sheet?", "By what percentage did revenue grow from Fiscal 2025 to Fiscal 2026?",
                "What was revenue from operations in Fiscal 2026 expressed in rupees crore?", "Who are the promoters of the company?",
                "What revenue does the company forecast for Fiscal 2028?"]
    st.caption("Example questions (answered instantly, even without an API key):")
    labels = ["Current borrowings", "Revenue growth %", "Revenue in ₹ crore", "Who are the promoters?", "FY2028 forecast (not in the document)"]
    cols = st.columns(len(examples))
    for i, (col, ex, label) in enumerate(zip(cols, examples, labels)):
        if col.button(label, key=f"ex{i}", help=ex, use_container_width=True):
            st.session_state["q"] = ex
            st.session_state["go"] = True
    st.session_state.setdefault("q", examples[0])
    q = st.text_input("Or type your own question", key="q")
    go = st.button("Ask", type="primary") or st.session_state.pop("go", False)
    if go and q.strip():
        from redflag.ingest import load_pages
        from redflag.qa import ask

        from redflag.llm import MissingKey

        try:
            with st.spinner("Retrieving, extracting and checking the citation..."):
                r = ask(q, doc)
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ in ("RateLimitError", "ServiceUnavailableError", "Timeout", "APIConnectionError"):
                st.warning("The free model quota for this demo is used up for now (the provider's daily/minute limit). "
                           "The example questions above still answer instantly; new questions will work again after the limit resets.")
                st.stop()
            if not isinstance(e, MissingKey):
                raise

            st.info("This question isn't in the demo's saved answers, and no model API key is configured on this deployment. "
                    "Try one of the example questions above, or see the Red-flag memo and reliability tabs. "
                    f"(Owner: add GEMINI_API_KEY under the app's Settings → Secrets. Status: {SECRETS_STATUS}.)")
            st.stop()
        if r.get("trace"):
            with st.expander(f"How this answer was produced ({len(r['trace'])} agent steps, {r['attempts']} model call(s), "
                             f"${r['cost_usd']:.5f})", expanded=r["attempts"] > 1):
                st.dataframe(pd.DataFrame(r["trace"]).rename(columns={"ms": "time (ms)"}), hide_index=True, use_container_width=True)
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
        n_gold = len(json.loads((REPORTS.parent / "evals" / "gold.json").read_text(encoding="utf-8")))
        st.markdown(f"{n_gold} questions with known answers across the three prospectuses (numbers in tables, text facts, "
                    "growth calculations, unit conversions, and questions whose answer is not in the document). "
                    "Rows are configurations and models; see the README for what each fix changed.")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    rp = REPORTS / "retrieval.json"
    if rp.exists():
        st.markdown("**Retrieval: does the right passage reach the model?** (recall@k)")
        st.dataframe(pd.DataFrame([{"retriever": k, **{kk: vv for kk, vv in v.items() if kk != "missed"}} for k, v in json.loads(rp.read_text()).items()]),
                     hide_index=True, use_container_width=True)
