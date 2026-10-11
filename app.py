"""
LeadPilot - Streamlit front end.  Run:  streamlit run app.py
"""
import os

import pandas as pd
import requests
import streamlit as st

from config import SELLER
from llm import LLM, PROVIDERS
from orchestrator import REQUIRED_COLUMNS, run_pipeline
from rag import get_kbs

BASE = os.path.dirname(os.path.abspath(__file__))
TIER_ICON = {"Hot": "🔥", "Warm": "🌤️", "Cold": "❄️", "Disqualified": "⛔"}

LOGO = os.path.join(BASE, "assets", "leadpilot_logo.png")
MARK = os.path.join(BASE, "assets", "leadpilot_mark.png")

st.set_page_config(page_title="LeadPilot | Multi-Agent Sales Automation", page_icon=MARK, layout="wide")
st.logo(LOGO, icon_image=MARK, size="large")
st.image(LOGO, width=300)
st.markdown(f"**Multi-agent B2B lead qualification & personalised outreach** · Seller: *{SELLER['product']}*")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Settings")
    provider = st.selectbox("LLM provider", list(PROVIDERS.keys()))
    if provider.startswith("ollama"):
        api_key = ""
        st.caption("Runs a local model via Ollama (no key). Start Ollama and run `ollama pull llama3.2` first.")
    else:
        api_key = st.text_input("API key (blank = Demo mode)", type="password")
    model_override = st.text_input("Model (optional override)", "",
                                   help="Leave blank for the default. On Groq: openai/gpt-oss-20b (fast, default) or openai/gpt-oss-120b (higher quality).")
    llm = LLM(provider, api_key or None, model_override.strip() or None)
    if llm.available and st.button("🔌 Test connection"):
        ok, msg = llm.test_connection()
        (st.success if ok else st.error)(msg)
    if llm.available:
        st.success(f"Live AI mode · {llm.model}")
    elif provider.startswith("ollama"):
        st.warning("Ollama not detected on localhost:11434 · using Demo mode")
    else:
        st.info("Demo mode · rule-based agents, no API key needed")
    sales_kb, policy_kb = get_kbs()
    st.caption(f"📚 Knowledge bases ({sales_kb.backend}): sales_kb {len(sales_kb.chunks)} chunks · "
               f"policy_kb {len(policy_kb.chunks)} chunks")
    st.divider()
    st.subheader("🤖 Agent team")
    st.markdown(
        "1. **Research Agent** – profiles the account, retrieves case study (RAG)\n"
        "2. **Qualification Agent** – ICP score & tier\n"
        "3. **Outreach Writer** – email + LinkedIn note grounded in product facts (RAG)\n"
        "4. **Compliance Reviewer** – policy check, fact-check, revise loop (RAG)\n"
        "5. **Sales Ops Router** – owner, next step, briefing\n\n"
        "👤 **Human-in-the-loop:** you approve every email · 📤 **n8n** sends it."
    )

# ---------------- Input ----------------
st.subheader("1 · Load leads")
source = st.radio("Lead source", ["Sample leads (20)", "Upload CSV"], horizontal=True)
if source == "Upload CSV":
    file = st.file_uploader("CSV with columns: " + ", ".join(REQUIRED_COLUMNS), type="csv")
    df = pd.read_csv(file) if file else None
else:
    df = pd.read_csv(os.path.join(BASE, "data", "sample_leads.csv"))

if df is not None:
    max_leads = st.slider("Number of leads to process", 1, len(df), len(df))
    with st.expander(f"Preview incoming leads ({len(df)})"):
        st.dataframe(df, width="stretch", hide_index=True)

    if st.button("🚀 Run the agent team", type="primary"):
        bar, status = st.progress(0.0), st.empty()

        def progress(i, n, company):
            bar.progress(i / n)
            status.write(f"Agents working on lead {i}/{n}: **{company}**")

        try:
            st.session_state.out = run_pipeline(df.head(max_leads), llm, progress)
            st.session_state.approved = {}
            status.success("Done. All five agents finished.")
        except ValueError as e:
            st.error(str(e))

# ---------------- Output ----------------
out = st.session_state.get("out")
if out:
    res, m = out["results"], out["metrics"]
    st.subheader("2 · Results")
    c = st.columns(6)
    c[0].metric("Leads processed", m["leads"])
    c[1].metric("🔥 Hot", m["hot"])
    c[2].metric("🌤️ Warm", m["warm"])
    c[3].metric("❄️ Cold / ⛔ DQ", m["cold"] + m["disqualified"])
    c[4].metric("Drafts auto-approved", f"{m['auto_approved']}/{m['drafts']}")
    c[5].metric("Est. SDR time saved", f"{(m['manual_minutes'] - m['seconds'] / 60) / 60:.1f} hrs",
                help=f"Assumes ~23 min of manual work per lead; agents took {m['seconds']} s")

    if m.get("llm_failed"):
        st.error("The AI calls failed, so the agents used rule-based Demo logic. Error from the API: "
                 f"{m.get('llm_error') or 'unknown'}. Click 'Test connection' in the sidebar.")
    st.caption(f"Mode: {res['mode'].iloc[0]} · LLM calls: {m['llm_calls']} · schema repairs: {m['schema_repairs']} · "
               f"RAG retrievals: {m['rag_retrievals']} · reviewer revisions: {m['revisions']} · run time: {m['seconds']} s")
    # A remembered view selector instead of st.tabs: tabs reset to the first tab on every rerun,
    # which threw reps back to "Lead pipeline" each time they approved a draft (found while testing).
    VIEWS = ["📊 Lead pipeline", "✉️ Outreach approval", "🧠 Agent activity log",
             "📋 Manager briefing", "📚 Knowledge base (RAG)"]
    view = st.segmented_control("View", VIEWS, default=VIEWS[0], key="view", label_visibility="collapsed") or VIEWS[0]
    t1, t2, t3, t4, t5 = (view == v for v in VIEWS)

    if t1:
        view = res[["lead_id", "company", "contact_name", "title", "industry", "score", "tier",
                    "priority", "owner", "next_action", "justification"]].copy()
        view["tier"] = view["tier"].map(lambda t: f"{TIER_ICON[t]} {t}")
        st.dataframe(view.sort_values("score", ascending=False), width="stretch", hide_index=True,
                     column_config={"score": st.column_config.ProgressColumn("score", min_value=0, max_value=100,
                                                                             format="%d")})
        left, right = st.columns(2)
        left.markdown("**Leads by tier**")
        left.bar_chart(res["tier"].value_counts(), color="#C4561F")
        right.markdown("**Average ICP factor scores (out of 20)**")
        right.bar_chart(res[[col for col in res.columns if col.startswith("score_")]].mean()
                        .rename(lambda x: x.replace("score_", "").replace("_", " ")), color="#17212B")

    if t2:
        drafts = res[res["email_body"] != ""].sort_values("score", ascending=False)
        st.caption("Edit any draft, then tick Approve. Nothing is sent without human approval.")
        for _, r in drafts.iterrows():
            with st.expander(f"{TIER_ICON[r['tier']]} {r['company']} · {r['contact_name']} · "
                             f"score {r['score']} · {r['review_status']}"):
                st.caption(f"Hook: {r['hook']}  |  Angle: {r['angle']}")
                if r["case_study"]:
                    st.caption(f"📚 Retrieved case study: {r['case_study'][:160]}...")
                if r["review_issues"]:
                    st.warning("Reviewer flags: " + r["review_issues"])
                subj = st.text_input("Subject", r["subject"], key=f"s_{r['lead_id']}")
                body = st.text_area("Email", r["email_body"], height=260, key=f"b_{r['lead_id']}")
                note = st.text_area("LinkedIn note", r["linkedin_note"], height=80, key=f"n_{r['lead_id']}")
                if st.checkbox("✅ Approve for sending", key=f"a_{r['lead_id']}"):
                    st.session_state.approved[r["lead_id"]] = {
                        "lead_id": r["lead_id"], "contact": r["contact_name"], "company": r["company"],
                        "subject": subj, "email_body": body, "linkedin_note": note, "owner": r["owner"]}
                else:
                    st.session_state.approved.pop(r["lead_id"], None)
        approved = pd.DataFrame(st.session_state.approved.values())
        st.write(f"**{len(approved)} of {len(drafts)} drafts approved**")
        if len(approved):
            st.download_button("⬇️ Download approved outreach (CSV)", approved.to_csv(index=False),
                               "approved_outreach.csv", "text/csv")
            st.markdown("##### 📤 Send approved emails via n8n (Webhook → SMTP)")
            hook_url = st.text_input("n8n webhook URL", "http://localhost:5678/webhook-test/leadpilot")
            demo_to = st.text_input("Demo recipient (your own email; sample prospects are fictional)")
            if st.button("Send approved emails via n8n", disabled=not demo_to):
                payload = {"emails": [{
                    "to": demo_to, "subject": a["subject"],
                    "email_body": f"[DEMO - written for {a['contact']} at {a['company']}]\n\n{a['email_body']}",
                    "lead_id": a["lead_id"], "company": a["company"], "contact": a["contact"], "owner": a["owner"],
                } for a in st.session_state.approved.values()]}
                try:
                    resp = requests.post(hook_url, json=payload, timeout=20)
                    if resp.ok:
                        st.success(f"Sent {len(payload['emails'])} email(s) to n8n (HTTP {resp.status_code}).")
                    else:
                        st.error(f"n8n returned HTTP {resp.status_code}: {resp.text[:200]}")
                except requests.RequestException as e:
                    st.error(f"Could not reach n8n: {e}. Is n8n running and the webhook listening?")

    if t3:
        agent = st.multiselect("Filter by agent", sorted(out["logs"]["agent"].unique()))
        logs = out["logs"] if not agent else out["logs"][out["logs"]["agent"].isin(agent)]
        st.dataframe(logs, width="stretch", hide_index=True)

    if t4:
        st.markdown(out["summary"])

    if t5:
        st.caption("Try the same vector search the agents use. sales_kb = product, case studies, objections; "
                   "policy_kb = brand voice and compliance.")
        kb_name = st.radio("Knowledge base", ["sales_kb", "policy_kb"], horizontal=True)
        q = st.text_input("Search query", "logistics payroll attendance")
        kb = sales_kb if kb_name == "sales_kb" else policy_kb
        for h in kb.search(q, k=3):
            st.markdown(f"**{h['section']}** · `{h['source']}` · similarity {h['score']}")
            st.caption(h["text"])

    st.download_button("⬇️ Download full results (CSV)", res.to_csv(index=False), "leadpilot_results.csv", "text/csv")
