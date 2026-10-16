"""Optional web UI.  Run:  streamlit run app.py"""
import json

import streamlit as st

from fpa import data_tools, guardrails
from fpa.pipeline import render_draft, run_pipeline
from fpa.rag import DocIndex
from fpa.report import render_report

st.set_page_config(page_title="FP&A Commentary Copilot", layout="wide")
st.title("FP&A Commentary Copilot")
st.caption("Budget and Forecast in this demo are simulated. Output is a draft for FP&A review.")


@st.cache_resource
def load():
    return data_tools.PnLData(), DocIndex()


data, index = load()
c1, c2, c3 = st.columns(3)
period = c1.selectbox("Period", data.periods, index=len(data.periods) - 1)
compare = c2.selectbox("Compare to", data_tools.COMPARES)
scope = c3.selectbox("Scope", data_tools.SCOPES)
note = st.text_area("Analyst note (optional, treated as unverified)")

if st.button("Generate commentary", type="primary"):
    with st.spinner("Computing, retrieving, drafting, reviewing..."):
        st.session_state["result"] = run_pipeline(period, compare, scope, note, data=data, index=index,
                                                  progress=lambda *_: None)

r = st.session_state.get("result")
if r:
    t1, t2, t3, t4, t5 = st.tabs(["Leadership Summary", "Commentary", "Review Mode", "Facts", "Download"])
    with t1:
        st.markdown(guardrails.strip_citations("\n".join(f"- {b}" for b in r["summary"].get("bullets", []))))
    with t2:
        st.markdown(render_draft(r["draft"]))
    with t3:
        for f in r["review"]["flags"]:
            icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(f.get("severity"), "⚪")
            st.markdown(f"{icon} **{f.get('category')}** ({f.get('source')}): {f.get('issue')}")
        st.subheader("Follow-up questions")
        for q in r["review"]["questions"]:
            st.markdown(f"- {q}")
    with t4:
        for f in r["facts"]:
            with st.expander(f"[{f['fact_id']}] {f['tool']} {f['args']}"):
                st.json(f["result"])
    with t5:
        st.download_button("Download report (.md)", render_report(r), file_name="commentary.md")
        st.download_button("Download raw JSON", json.dumps(r, indent=2), file_name="commentary.json")
