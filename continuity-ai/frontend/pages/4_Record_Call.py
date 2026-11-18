import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

import frontend.api as api
from frontend.components.speech import LANGUAGES, lines_to_text, speech_recorder
from frontend.components.ui import hero, setup

setup("Record Call")
hero("Record Call", "Talk to the customer. The call is transcribed live, saved to the case, and summarised for the next agent.", "🎙️")

st.session_state.setdefault("rec_n", 0)
agents = api.get("/agents")
agent_names = {a["agent_id"]: f"{a['name']} ({a['agent_id']})" for a in agents}
cases = api.get("/cases")

mode = st.radio("Save this call as", ["🆕 A new case", "💬 A new conversation on an existing case"], horizontal=True)
c1, c2, c3 = st.columns([1.3, 1.3, 1])
if mode.startswith("🆕"):
    name = c1.text_input("Customer name", key="rc_name")
    email = c2.text_input("Customer email (optional)", key="rc_email")
    case_id = None
else:
    labels = {c["case_id"]: f"#{c['case_id']}  {c['customer_name']}  ({c['status']})" for c in cases}
    ids = list(labels)
    pre = ids.index(st.session_state["case_id"]) if st.session_state.get("case_id") in ids else 0
    case_id = c1.selectbox("Case", ids, index=pre, format_func=labels.get, key="rc_case") if ids else None
    name = email = None
agent = c3.selectbox("Your agent ID", list(agent_names), format_func=agent_names.get, key="rc_agent")
lang_label = st.selectbox("Spoken language", list(LANGUAGES), key="rc_lang")

st.markdown('<div class="sec">1 · Record</div>', unsafe_allow_html=True)
st.caption("Works in Google Chrome or Microsoft Edge. Allow the microphone when asked. "
           "Speech is converted to text by your browser's speech service, so you need an internet connection.")
value = speech_recorder(key=f"rec_{st.session_state.rec_n}", lang=LANGUAGES[lang_label])
if value and value.get("seq") != st.session_state.get("rec_seen"):
    st.session_state["rec_seen"] = value["seq"]
    st.session_state["rc_text"] = lines_to_text(value["lines"])

st.markdown('<div class="sec">2 · Check the transcript</div>', unsafe_allow_html=True)
st.caption("Fix any words the microphone got wrong. You can also type or paste a transcript here "
           "(one message per line, starting with Customer: or Agent:).")
transcript = st.text_area("Transcript", height=220, key="rc_text", label_visibility="collapsed",
                          placeholder="Customer: ...\nAgent: ...")

st.markdown('<div class="sec">3 · Save and summarise</div>', unsafe_allow_html=True)
analyse = st.checkbox("Generate the summary for the next agent after saving", value=True, key="rc_analyse")
saved = None
if st.button("💾 Save call", type="primary"):
    if not transcript.strip():
        st.error("There is no transcript yet. Record the call or type it in.")
    elif name is not None and not name.strip():
        st.error("Enter the customer name.")
    elif name is None and case_id is None:
        st.error("Choose a case.")
    else:
        try:
            if name is not None:
                saved = api.post("/cases", json={"customer_name": name, "customer_email": email or None,
                                                 "agent_id": agent, "transcript": transcript})
            else:
                saved = api.post(f"/cases/{case_id}/conversations", json={"agent_id": agent, "transcript": transcript})
            if analyse:
                with st.spinner("Summarising the conversation for the next agent..."):
                    api.post(f"/cases/{saved['case_id']}/process")
        except Exception as e:  # noqa: BLE001
            saved = None
            st.error(api.detail(e))
if saved:
    st.session_state["case_id"] = saved["case_id"]
    st.session_state["rec_n"] += 1          # fresh, empty recorder next time
    st.session_state["rec_seen"] = None
    st.switch_page("pages/1_Case_Workspace.py")
