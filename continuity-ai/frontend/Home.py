import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

import frontend.api as api
from frontend.components.ui import avatar, case_pill, esc, hero, setup, stat_card

setup("Dashboard")
hero("Agent Dashboard", "Every customer case, what was promised, and what needs your attention today.", "📊")

cases = api.get("/cases")
unresolved = sum(1 for c in cases if c["status"] != "resolved")
follow_up = sum(1 for c in cases if c["status"] != "resolved" and c["open_actions"] > 0)
me = st.session_state.get("me_id")
mine = sum(1 for c in cases if c["assigned_agent_id"] == me and c["status"] != "resolved")
open_actions = sum(c["open_actions"] for c in cases if c["status"] != "resolved")

cols = st.columns(4)
cols[0].markdown(stat_card("Total cases", len(cases), "📁", "#6366f1"), unsafe_allow_html=True)
cols[1].markdown(stat_card("Open / unresolved", unresolved, "🔓", "#16a34a"), unsafe_allow_html=True)
cols[2].markdown(stat_card(f"Need follow-up ({open_actions} open actions)", follow_up, "⏰", "#d97706"), unsafe_allow_html=True)
cols[3].markdown(stat_card("Assigned to me", mine, "👤", "#db2777"), unsafe_allow_html=True)

st.markdown('<div class="sec">Cases</div>', unsafe_allow_html=True)
f1, f2, f3, f4 = st.columns([3, 1.3, 1.3, 1.5], vertical_alignment="bottom")
query = f1.text_input("🔍 Search", placeholder="Customer name or issue...")
status_filter = f2.selectbox("Status", ["all", "open", "transferred", "resolved"])
if f3.button("➕ New case", use_container_width=True):
    st.switch_page("pages/3_New_Case.py")
if f4.button("🎙️ Record call", type="primary", use_container_width=True):
    st.switch_page("pages/4_Record_Call.py")

shown = [c for c in cases
         if (status_filter == "all" or c["status"] == status_filter)
         and (not query or query.lower() in f"{c['customer_name']} {c['issue'] or ''}".lower())]
st.caption(f"Showing {len(shown)} of {len(cases)} case(s), most recently updated first.")
if not shown:
    st.info("No cases match. Use **New case** to log one.")
for c in shown:
    with st.container(border=True):
        a, b, d, e = st.columns([3.4, 1.2, 1.8, 1.2], vertical_alignment="center")
        a.markdown(f'<div class="row">{avatar(c["customer_name"])}<div><div class="name">{esc(c["customer_name"])}</div>'
                   f'<div class="muted">{esc(c["issue"] or "Not analysed yet")}</div></div></div>',
                   unsafe_allow_html=True)
        b.markdown(case_pill(c["status"]), unsafe_allow_html=True)
        d.markdown(f'<div class="muted">💬 {c["interactions"]} interaction(s)<br>'
                   f'⏳ {c["open_actions"]} open · ✅ {c["done_actions"]} done</div>', unsafe_allow_html=True)
        if e.button("Open case →", key=f"open_{c['case_id']}", type="primary", use_container_width=True):
            st.session_state["case_id"] = c["case_id"]
            st.switch_page("pages/1_Case_Workspace.py")
