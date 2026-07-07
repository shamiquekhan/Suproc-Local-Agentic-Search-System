#!/usr/bin/env python3
import json
import streamlit as st
import sqlite3
from pathlib import Path

from agent.parser import parse_requirement
from agent.planner import build_plan
from agent.loop import run_agent
from agent.schemas import FinalResponse

_DB_PATH = Path(__file__).resolve().parent / "data" / "suproc.db"
if not _DB_PATH.exists():
    from scripts.seed_database import seed
    seed()

st.set_page_config(
    page_title="Suproc Agent Dashboard",
    page_icon="◆",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #F5F0E8;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #F5E6C8 0%, #D4AF37 50%, #F5E6C8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: 0.02em;
    }

    .stApp {
        background: #000000;
    }

    .main > div {
        background: #000000;
    }

    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(212, 175, 55, 0.03) 0%, transparent 70%),
            radial-gradient(ellipse 60% 40% at 80% 80%, rgba(212, 175, 55, 0.02) 0%, transparent 60%),
            radial-gradient(ellipse 40% 60% at 20% 90%, rgba(212, 175, 55, 0.015) 0%, transparent 50%);
        pointer-events: none;
        z-index: 0;
    }

    .stApp > header {
        background: rgba(0,0,0,0.9) !important;
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(212, 175, 55, 0.15);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(135deg, #0A0A0A 0%, #050505 100%) !important;
        border-right: 1px solid rgba(212, 175, 55, 0.12);
    }

    section[data-testid="stSidebar"] .stButton button {
        background: transparent !important;
        border: 1px solid rgba(212, 175, 55, 0.2) !important;
        color: #C9B88A !important;
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        font-size: 0.8rem;
        transition: all 0.4s ease;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        border-color: #D4AF37 !important;
        color: #F5E6C8 !important;
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.1);
        transform: translateX(4px);
    }

    .stTextArea textarea {
        background: rgba(10, 10, 10, 0.8) !important;
        border: 1px solid rgba(212, 175, 55, 0.15) !important;
        color: #F5F0E8 !important;
        font-family: 'Inter', sans-serif;
        font-weight: 300;
        border-radius: 8px;
        transition: all 0.4s ease;
    }

    .stTextArea textarea:focus {
        border-color: #D4AF37 !important;
        box-shadow: 0 0 25px rgba(212, 175, 55, 0.08);
    }

    .stTextArea textarea::placeholder {
        color: rgba(245, 240, 232, 0.25);
        font-style: italic;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #D4AF37 0%, #B8962E 100%) !important;
        color: #000000 !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 2rem !important;
        transition: all 0.4s ease !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.85rem !important;
    }

    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 30px rgba(212, 175, 55, 0.25) !important;
        transform: translateY(-1px);
    }

    div.stButton > button[kind="primary"]:active {
        transform: translateY(0);
    }

    .stAlert {
        background: rgba(10, 10, 10, 0.8) !important;
        border: 1px solid rgba(212, 175, 55, 0.1);
        border-radius: 8px;
    }

    .stAlert > div {
        color: #F5F0E8 !important;
    }

    div[data-testid="stExpander"] {
        background: rgba(10, 10, 10, 0.6) !important;
        border: 1px solid rgba(212, 175, 55, 0.08) !important;
        border-radius: 8px !important;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }

    div[data-testid="stExpander"]:hover {
        border-color: rgba(212, 175, 55, 0.2) !important;
    }

    div[data-testid="stExpander"] summary {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        color: #C9B88A;
    }

    div[data-testid="stExpander"] summary p {
        font-family: 'Playfair Display', serif;
        font-size: 1.1rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(10, 10, 10, 0.6);
        border: 1px solid rgba(212, 175, 55, 0.1);
        border-radius: 8px;
        padding: 1rem;
        transition: all 0.3s ease;
    }

    div[data-testid="stMetric"]:hover {
        border-color: rgba(212, 175, 55, 0.25);
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.05);
    }

    div[data-testid="stMetric"] label {
        color: #8A7F6B !important;
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.7rem !important;
    }

    div[data-testid="stMetric"] div {
        color: #F5E6C8 !important;
        font-family: 'Playfair Display', serif;
        font-weight: 700;
    }

    div.stDataFrame {
        background: rgba(10, 10, 10, 0.4) !important;
        border: 1px solid rgba(212, 175, 55, 0.08) !important;
        border-radius: 6px;
    }

    div.stDataFrame table {
        background: transparent !important;
    }

    div.stDataFrame thead tr th {
        background: rgba(212, 175, 55, 0.05) !important;
        color: #C9B88A !important;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    div.stDataFrame tbody tr td {
        color: #F5F0E8 !important;
        border-bottom: 1px solid rgba(212, 175, 55, 0.05);
    }

    .stSuccess {
        background: rgba(212, 175, 55, 0.08) !important;
        border: 1px solid rgba(212, 175, 55, 0.2) !important;
        color: #F5E6C8 !important;
    }

    .stWarning {
        background: rgba(212, 175, 55, 0.05) !important;
        border: 1px solid rgba(212, 175, 55, 0.12) !important;
        color: #C9B88A !important;
    }

    .stError {
        background: rgba(180, 60, 60, 0.08) !important;
        border: 1px solid rgba(180, 60, 60, 0.15) !important;
        color: #E8B4B4 !important;
    }

    .stInfo {
        background: rgba(212, 175, 55, 0.05) !important;
        border: 1px solid rgba(212, 175, 55, 0.12) !important;
        color: #C9B88A !important;
    }

    .stCheckbox label {
        color: #C9B88A !important;
        font-family: 'Inter', sans-serif;
        font-weight: 300;
    }

    .stCheckbox label span {
        border-color: rgba(212, 175, 55, 0.3) !important;
    }

    .stCheckbox label span[data-testid="check"] {
        background-color: #D4AF37 !important;
    }

    hr {
        border-color: rgba(212, 175, 55, 0.1) !important;
    }

    div[data-testid="stBlock"] {
        animation: fadeIn 0.6s ease forwards;
        opacity: 0;
    }

    div[data-testid="stBlock"]:nth-child(1) { animation-delay: 0.05s; }
    div[data-testid="stBlock"]:nth-child(2) { animation-delay: 0.1s; }
    div[data-testid="stBlock"]:nth-child(3) { animation-delay: 0.15s; }
    div[data-testid="stBlock"]:nth-child(4) { animation-delay: 0.2s; }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background: rgba(10, 10, 10, 0.4) !important;
        border: 1px solid rgba(212, 175, 55, 0.08) !important;
        border-radius: 8px !important;
        padding: 1rem;
        transition: all 0.3s ease;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div:hover {
        border-color: rgba(212, 175, 55, 0.2) !important;
        box-shadow: 0 0 25px rgba(212, 175, 55, 0.03);
    }

    .st-emotion-cache-1kyxreq {
        color: #8A7F6B !important;
    }

    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #050505;
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(212, 175, 55, 0.15);
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(212, 175, 55, 0.25);
    }

    .glow-text {
        text-shadow: 0 0 40px rgba(212, 175, 55, 0.08);
    }

    .subtitle-glow {
        animation: subtitleFade 1s ease forwards;
        opacity: 0;
    }

    @keyframes subtitleFade {
        from { opacity: 0; transform: translateY(8px); filter: blur(4px); }
        to { opacity: 0.6; transform: translateY(0); filter: blur(0); }
    }

    .stCodeBlock {
        background: rgba(0,0,0,0.8) !important;
        border: 1px solid rgba(212, 175, 55, 0.08) !important;
        border-radius: 6px;
    }

    .stCodeBlock code {
        color: #F5F0E8 !important;
    }
</style>
""", unsafe_allow_html=True)

EXAMPLE_REQUESTS = [
    "We need three food-grade biodegradable packaging suppliers in South India with a capacity of at least 10,000 units, delivery within 30 days, preferably sustainable and startup-friendly.",
    "Find a logistics provider in Karnataka that handles freight delivery.",
    "I need a packaging supplier with ISO-9001 certification.",
    "Find a textile manufacturer in Tamil Nadu.",
    "Show me available business opportunities.",
    "Find a mechanical engineer in South India.",
]


def display_response(resp: FinalResponse):
    req = resp.interpreted_requirement
    hc = req.hard_constraints
    pr = req.preferences

    col1, col2, col3 = st.columns(3)
    col1.metric("Validation", resp.validation_status)
    col2.metric("Attempts", f"{resp.validation_attempts}/3")
    col3.metric("Approval", resp.approval_status)

    with st.expander("Interpreted Requirement", expanded=True):
        rcol1, rcol2 = st.columns(2)
        rcol1.markdown(f"**Objective:** {req.objective}")
        rcol1.markdown(f"**Entity Type:** {req.entity_type}")
        rcol1.markdown(f"**Requested Results:** {req.requested_results}")

        rcol2.markdown("**Hard Constraints:**")
        rcol2.markdown(f"- Locations: {hc.locations or 'any'}")
        rcol2.markdown(f"- Certifications: {hc.certifications or 'none required'}")
        rcol2.markdown(f"- Min Capacity: {hc.minimum_capacity or 'not specified'}")
        rcol2.markdown(f"- Max Delivery: {f'{hc.maximum_delivery_days} days' if hc.maximum_delivery_days else 'not specified'}")
        rcol2.markdown(f"- Availability: {hc.availability or 'any'}")

        st.markdown("**Preferences:**")
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        pcol1.markdown(f"Sustainable: {'✦' if pr.sustainable_materials else '○'}")
        pcol2.markdown(f"Startup Friendly: {'✦' if pr.startup_friendly else '○'}")
        pcol3.markdown(f"Min Rating: {pr.min_rating or 'any'}")
        pcol4.markdown(f"Category: {pr.category or 'any'}")

    with st.expander("Execution Plan", expanded=False):
        for i, step in enumerate(resp.plan_followed.steps, 1):
            st.markdown(f"**{i}.** {step}")

    st.markdown("## Recommendations")
    if not resp.recommendations:
        st.warning("No valid recommendations found.")

    for rec in resp.recommendations:
        e = rec.entity
        s = rec.score
        score_pct = s.total / 100

        with st.container(border=True):
            rank_title = f"#{rec.rank}: {e.name} ({e.id}) — {s.total:.0f}/100"
            st.markdown(f"<h3>{rank_title}</h3>", unsafe_allow_html=True)

            st.progress(score_pct)

            info_cols = st.columns(4)
            info_cols[0].markdown(f"**Location:** {e.location}, {e.state}")
            info_cols[1].markdown(f"**Certifications:** {', '.join(e.certifications) if e.certifications else 'none'}")
            info_cols[2].markdown(f"**Capacity:** {e.capacity_units or 'unknown'} units")
            info_cols[3].markdown(f"**Delivery:** {e.delivery_days or 'unknown'} days")

            info_cols2 = st.columns(3)
            info_cols2[0].markdown(f"**Availability:** {e.availability}")
            info_cols2[1].markdown(f"**Rating:** {e.rating or 'n/a'}/5")
            info_cols2[2].markdown(f"**Contact:** {e.contact_email or 'N/A'}")

            st.markdown(f"**Why Suitable:** {rec.why_suitable}")

            score_data = {
                "Dimension": ["Product Relevance", "Location Suitability", "Constraint Compliance", "Availability/Capacity", "Reputation"],
                "Score": [s.product_relevance, s.location_suitability, s.constraint_compliance, s.availability_capacity, s.reputation],
                "Max": [30, 20, 25, 15, 10],
            }
            st.dataframe(score_data, use_container_width=True, hide_index=True)

            evidence_text = "\n".join(f"- **{k}:** {v}" for k, v in s.evidence.items())
            st.markdown(f"**Evidence:**\n{evidence_text}")

            if rec.missing_information:
                st.warning(f"Missing info: {', '.join(rec.missing_information)}")
            if rec.risks:
                st.error(f"Risks: {', '.join(rec.risks)}")

    if resp.validation_failures:
        with st.expander("Validation Failures", expanded=False):
            for f in resp.validation_failures:
                st.error(f"**[{f.entity_id}]** {f.failure_type}: {f.detail}")

    if resp.draft_outreach_messages:
        with st.expander("Draft Outreach Messages", expanded=False):
            for msg in resp.draft_outreach_messages:
                with st.container(border=True):
                    st.markdown(f"**To:** {msg.recipient_name} ({msg.recipient_id})")
                    st.markdown(f"**Subject:** {msg.subject}")
                    st.code(msg.body, language="text")

    if resp.warnings:
        with st.expander("Warnings", expanded=False):
            for w in resp.warnings:
                st.warning(w)

    st.markdown("---")
    st.markdown("### ⚜ Human Approval Required")
    st.info(resp.recommended_next_action)
    st.error(f"**Status: {resp.approval_status}**")


def main():
    st.markdown("<h1 class='glow-text'>◆ Suproc</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle-glow' style='color: rgba(245,240,232,0.6); font-weight: 300; margin-top: -0.5rem;'>Local Agentic Search System</p>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### ◆ About")
        st.markdown(
            "**Suproc** is a local AI agent that parses business requirements, searches a SQLite dataset, "
            "scores candidates across 5 dimensions, validates results, and drafts outreach — all with a "
            "mandatory human approval gate."
        )

        st.markdown("### ⚙ Quick Examples")
        for ex in EXAMPLE_REQUESTS:
            label = ex[:50] + "…" if len(ex) > 50 else ex
            if st.button(label, key=ex, use_container_width=True, type="secondary"):
                st.session_state.request_text = ex

        st.markdown("### ◇ Dataset")
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM entities")
            entities = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM professionals")
            profs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM opportunities")
            opps = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM interactions")
            ints = cur.fetchone()[0]
            conn.close()
            st.markdown(f"- Entities: **{entities}**")
            st.markdown(f"- Professionals: **{profs}**")
            st.markdown(f"- Opportunities: **{opps}**")
            st.markdown(f"- Interactions: **{ints}**")
        except Exception:
            st.warning("Could not read database.")

        st.markdown("### 🔗 Links")
        st.markdown("[GitHub Repo](https://github.com/shamiquekhan/Suproc-Local-Agentic-Search-System)")

    request_text = st.text_area(
        "Enter your business requirement:",
        value=st.session_state.get("request_text", ""),
        height=120,
        placeholder="e.g. We need three food-grade biodegradable packaging suppliers in South India...",
    )

    col_btn, col_json = st.columns([1, 5])
    run_clicked = col_btn.button("⟢ Run Search", type="primary")
    show_json = col_json.checkbox("Show raw JSON output", value=False)

    if run_clicked and request_text.strip():
        st.session_state.request_text = request_text

        with st.spinner("Parsing requirement..."):
            req = parse_requirement(request_text)
        with st.spinner("Building execution plan..."):
            plan = build_plan(req)
        with st.spinner("Running agent (search → filter → score → validate)..."):
            response = run_agent(req, plan)

        st.success("Search complete.")

        if show_json:
            st.subheader("Raw JSON Output")
            st.code(response.model_dump_json(indent=2), language="json")
        else:
            display_response(response)

    elif run_clicked:
        st.warning("Please enter a business requirement.")


if __name__ == "__main__":
    main()
