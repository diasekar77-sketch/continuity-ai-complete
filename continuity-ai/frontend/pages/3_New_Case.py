import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

import frontend.api as api
from frontend.components.ui import hero, setup

setup("New Case")
hero("New Case", "Log a conversation as a new case, or add another conversation to an existing case.", "➕")

EXAMPLE = """Customer: Hi, I upgraded to the annual plan yesterday but my card was charged twice.
Agent: I'm sorry about that. Let me look into it. Can you share the last four digits of the card?
Customer: It ends in 8821. I need the extra payment back, this is the second time this has happened.
Agent: If billing confirms the duplicate payment, you would be eligible for a refund. I will raise this with the billing team today.
Customer: So is the refund approved?
Agent: Not yet, billing has to verify it first. I might be able to offer a free month as a goodwill gesture, but I can't confirm that.
Agent: I will email you the billing reference number by tomorrow."""

HINT = "One message per line, starting with **Customer:** or **Agent:**. Wrapped lines are joined automatically."
agents = api.get("/agents")
agent_names = {a["agent_id"]: f"{a['name']} ({a['agent_id']})" for a in agents}


def load_example():
    st.session_state["nc_transcript"] = EXAMPLE
    st.session_state["nc_name"] = "Diya Nair"
    st.session_state["nc_email"] = "diya.nair@example.com"


tab_new, tab_add = st.tabs(["🆕 Create a new case", "💬 Add a conversation to an existing case"])

with tab_new:
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    name = c1.text_input("Customer name", key="nc_name")
    email = c2.text_input("Customer email (optional)", key="nc_email")
    agent = c3.selectbox("Handled by", list(agent_names), format_func=agent_names.get, key="nc_agent")
    st.caption(HINT)
    transcript = st.text_area("Conversation transcript", height=280, key="nc_transcript",
                              placeholder="Customer: Hi, I was charged twice...\nAgent: I'm sorry about that...")
    b1, b2, b3 = st.columns([1.3, 1.1, 2.6], vertical_alignment="center")
    analyse = b3.checkbox("Analyse with AI after saving", value=True, key="nc_analyse")
    b2.button("Load example", on_click=load_example, use_container_width=True)
    saved = None
    if b1.button("💾 Save case", type="primary", use_container_width=True):
        if not name.strip() or not transcript.strip():
            st.error("Customer name and transcript are required.")
        else:
            try:
                saved = api.post("/cases", json={"customer_name": name, "customer_email": email or None,
                                                 "agent_id": agent, "transcript": transcript})
                if analyse:
                    with st.spinner("Analysing the conversation..."):
                        api.post(f"/cases/{saved['case_id']}/process")
            except Exception as e:  # noqa: BLE001
                saved = None
                st.error(api.detail(e))
    if saved:
        st.session_state["case_id"] = saved["case_id"]
        st.switch_page("pages/1_Case_Workspace.py")

with tab_add:
    cases = api.get("/cases")
    if not cases:
        st.info("No cases yet. Create one first.")
    else:
        labels = {c["case_id"]: f"#{c['case_id']}  {c['customer_name']}  ({c['status']})" for c in cases}
        ids = list(labels)
        pre = ids.index(st.session_state["case_id"]) if st.session_state.get("case_id") in ids else 0
        a1, a2 = st.columns([1.6, 1])
        cid = a1.selectbox("Case", ids, index=pre, format_func=labels.get, key="add_case")
        agent2 = a2.selectbox("Handled by", list(agent_names), format_func=agent_names.get, key="add_agent")
        st.caption(HINT)
        t2 = st.text_area("New conversation", height=220, key="add_transcript",
                          placeholder="Customer: Hi, it's been two days and I still have no reply...\nAgent: I'm sorry, let me check...")
        if st.button("➕ Add conversation", type="primary"):
            if not t2.strip():
                st.error("Transcript is required.")
            else:
                try:
                    r = api.post(f"/cases/{cid}/conversations", json={"agent_id": agent2, "transcript": t2})
                    st.success(f"Added {r['messages']} messages. Re-run the analysis in the Case Workspace to update the handover.")
                    st.session_state["case_id"] = cid
                    st.page_link("pages/1_Case_Workspace.py", label="Open in Case Workspace →", icon="🗂️")
                except Exception as e:  # noqa: BLE001
                    st.error(api.detail(e))
