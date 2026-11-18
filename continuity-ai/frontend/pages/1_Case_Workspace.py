import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

import frontend.api as api
from frontend.components.ui import (action_progress, avatar, case_pill, chips, commit_card, coverage_bar, esc,
                                    evidence_line, fmt_time, hero, policy_card, setup, timeline_row)

setup("Case Workspace")
hero("Case Workspace", "Handover summary, follow-up actions, evidence and an assistant that shows its sources.", "🗂️")
me = st.session_state.get("me_id")


def toggle_action(action_id: int, key: str):
    api.post(f"/actions/{action_id}/status", json={"done": bool(st.session_state[key]),
                                                  "by": st.session_state.get("me_id")})


def toggle_check(case_id: int, item: str, key: str):
    api.post(f"/cases/{case_id}/checklist", json={"item": item, "checked": bool(st.session_state[key]),
                                                  "by": st.session_state.get("me_id")})


cases = api.get("/cases")
if not cases:
    st.info("No cases available.")
    st.stop()
labels = {c["case_id"]: f"#{c['case_id']}  {c['customer_name']}" for c in cases}
ids = list(labels)
default = ids.index(st.session_state["case_id"]) if st.session_state.get("case_id") in ids else 0
cid = st.selectbox("Case", ids, index=default, format_func=labels.get)
st.session_state["case_id"] = cid

h = api.get(f"/cases/{cid}/handover")
case = h["case"]

top = st.columns([3, 1.1, 2.2, 1.7], vertical_alignment="center")
top[0].markdown(f'<div class="row">{avatar(case["customer_name"], 52)}<div><div class="name" style="font-size:1.25rem">'
                f'{esc(case["customer_name"])}</div><div class="muted">{esc(case["customer_email"] or "")}</div></div></div>',
                unsafe_allow_html=True)
top[1].markdown(case_pill(case["status"]), unsafe_allow_html=True)
if case.get("transferred_from"):
    top[2].markdown(f'<div class="muted">🔁 Transferred {esc(case["transferred_from"])} → '
                    f'<b>{esc(case["assigned_agent_name"] or "")}</b></div>', unsafe_allow_html=True)
if top[3].button("✨ Analyse with AI" if not h["processed"] else "🔄 Re-run analysis", type="primary",
                 use_container_width=True):
    with st.spinner("Extracting case memory and verifying quotes against the transcript..."):
        res = api.post(f"/cases/{cid}/process", params={"by": me})
    st.toast(f"Done ({res['extractor']}): {res['commitments']} commitments, evidence coverage {res['evidence_coverage']:.0%}")
    st.rerun()
if not h["processed"]:
    st.info("This case has not been analysed yet. Click **Analyse with AI** to build the handover.")
elif h.get("stale"):
    st.warning("New conversation added since the last analysis. Click **Re-run analysis** to update commitments and policies. "
               "Actions you already completed or added are kept.")

with st.expander("⚙️ Case actions: status and transfer"):
    a1, a2 = st.columns(2)
    with a1:
        if case["status"] == "resolved":
            if st.button("↩️ Reopen case", use_container_width=True):
                api.post(f"/cases/{cid}/status", json={"status": "open", "by": me})
                st.rerun()
        elif st.button("✅ Mark as resolved", use_container_width=True):
            api.post(f"/cases/{cid}/status", json={"status": "resolved", "by": me})
            st.rerun()
    with a2:
        agents = api.get("/agents")
        names = {a["agent_id"]: f"{a['name']} ({a['agent_id']}, {a['role']})" for a in agents}
        to = st.selectbox("Transfer to", list(names), format_func=names.get, key=f"to_{cid}")
        if st.button("🔁 Transfer case", use_container_width=True):
            try:
                api.post(f"/cases/{cid}/transfer", json={"to_agent_id": to, "by": me})
            except Exception as e:  # noqa: BLE001
                st.error(api.detail(e))
            else:
                st.rerun()

main, copilot = st.columns([2.2, 1.3], gap="large")

# ------------------------------------------------------------------ handover, transcript, activity
with main:
    tab_h, tab_t, tab_a = st.tabs(["📋 Handover", "💬 Transcript", "🕒 Activity"])

    with tab_h:
        if h["processed"]:
            st.markdown(f'<div class="handoff"><div class="h">📝 Handoff summary</div>'
                        f'{esc(h["summary"]).replace(chr(10), "<br>")}'
                        f'<div style="margin-top:10px">{chips(h["concerns"])}</div>'
                        f'<div class="muted" style="margin-top:6px">Customer sentiment: <b>{esc(h["sentiment"])}</b></div></div>',
                        unsafe_allow_html=True)
            st.markdown(coverage_bar(h["evidence_coverage"] or 0), unsafe_allow_html=True)

            # ---- actions
            counts = h["action_counts"]
            st.markdown(action_progress(counts["done"], counts["pending"] + counts["done"]), unsafe_allow_html=True)
            if not h["actions"]:
                st.caption("No follow-up actions yet.")
            for a in h["actions"]:
                key = f"act_{a['action_id']}"
                st.checkbox(a["description"], value=a["status"] == "done", key=key,
                            on_change=toggle_action, args=(a["action_id"], key))
                if a["status"] == "done":
                    meta = f"✔ Done by {a['completed_by_name'] or a['completed_by'] or 'someone'} · {fmt_time(a['completed_at'])}"
                elif a["source"] == "manual":
                    meta = f"Added manually by {a['assigned_agent'] or 'an agent'}"
                else:
                    meta = f"From message #{a['source_message_id']} · {'✓ verified' if a['verified'] else '⚠ unverified'}"
                st.markdown(f'<div class="muted" style="margin:-10px 0 8px 30px">{esc(meta)}</div>', unsafe_allow_html=True)
            with st.form(f"add_action_{cid}", clear_on_submit=True, border=False):
                f1, f2 = st.columns([4, 1.3], vertical_alignment="bottom")
                txt = f1.text_input("Add an action", placeholder="e.g. Call the customer back with the billing reference",
                                    label_visibility="collapsed")
                added = f2.form_submit_button("➕ Add action", use_container_width=True)
            if added and txt.strip():
                try:
                    api.post(f"/cases/{cid}/actions", json={"description": txt, "by": me})
                except Exception as e:  # noqa: BLE001
                    st.error(api.detail(e))
                else:
                    st.rerun()

            st.markdown('<div class="sec">🤝 Commitments</div>', unsafe_allow_html=True)
            st.caption("Promised = firm commitment · Conditional = only if a condition is met · Discussed = floated, not committed")
            for c in h["commitments"]:
                st.markdown(commit_card(c), unsafe_allow_html=True)

            if h["troubleshooting"]:
                st.markdown('<div class="sec">🛠️ Troubleshooting already done</div>', unsafe_allow_html=True)
                for t in h["troubleshooting"]:
                    st.markdown(f'- {esc(t["quote"])} <span class="muted">({esc(t["outcome"])})</span>', unsafe_allow_html=True)

            st.markdown('<div class="sec">☑️ Verify before responding</div>', unsafe_allow_html=True)
            for it in h["verify_items"]:
                key = f"verify_{cid}_{it['key']}"
                st.checkbox(it["text"], value=it["checked"], key=key, on_change=toggle_check, args=(cid, it["text"], key))

            st.markdown('<div class="sec">📘 Applicable company policy</div>', unsafe_allow_html=True)
            pe = h["policy_evidence"]
            if not pe["hits"]:
                st.warning("No relevant policy found in the uploaded documents. Upload policies in the Knowledge Base.")
            for p in pe["hits"]:
                trig = [t for t in p.get("triggered_by", []) if t != "issue"]
                note = f"Relevant to {len(trig)} agent statement(s) in this case" if trig else ""
                st.markdown(policy_card(p, note), unsafe_allow_html=True)

    with tab_t:
        for inter in h["history"]:
            st.markdown(f'**🎧 Interaction with {esc(inter["agent_name"] or inter["agent_id"])}** '
                        f'<span class="muted">· {esc(inter["timestamp"])}</span>', unsafe_allow_html=True)
            for m in inter["messages"]:
                with st.chat_message("user" if m["speaker"] == "customer" else "assistant",
                                     avatar="🙂" if m["speaker"] == "customer" else "🎧"):
                    st.write(m["content"])
                    st.caption(f"#{m['message_id']} · {m['timestamp']}")

    with tab_a:
        st.caption("Everything that happened on this case, newest first.")
        if not h["events"]:
            st.info("No activity recorded yet.")
        st.markdown("".join(timeline_row(e) for e in h["events"]), unsafe_allow_html=True)

# ------------------------------------------------------------------ assistant panel
with copilot:
    st.markdown('<div class="ai-head">✨ Assistant</div>', unsafe_allow_html=True)
    st.caption("Answers come from this case's transcript and the uploaded policies, with sources.")
    key = f"chat_{cid}"
    st.session_state.setdefault(key, [])

    suggestions = ["What did the previous agent tell this customer?",
                   "Which troubleshooting steps are already done?",
                   "Was a refund actually promised?",
                   "Can I offer a free month?",
                   "What should I verify before responding?"]
    question = None
    for i, s in enumerate(suggestions):
        if st.button(s, key=f"sug_{i}", use_container_width=True):
            question = s
    typed = st.chat_input("Ask about this case or company policy")
    question = typed or question

    if question:
        st.session_state[key].append({"role": "user", "text": question})
        with st.spinner("Searching the transcript and policies..."):
            try:
                st.session_state[key].append({"role": "assistant", "data": api.post(
                    "/assistant/query", json={"case_id": cid, "question": question})})
            except Exception as e:  # noqa: BLE001
                st.session_state[key].append({"role": "assistant", "error": str(e)})

    box = st.container(height=520)
    with box:
        for msg in st.session_state[key]:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["text"])
                continue
            with st.chat_message("assistant"):
                if "error" in msg:
                    st.error(msg["error"])
                    continue
                d = msg["data"]
                st.write(d["answer"])
                st.caption("🤖 LLM answer, citations validated against evidence" if d["mode"] == "llm"
                           else "🧾 Offline evidence mode")
                for v in d["verify_before_responding"]:
                    st.markdown(f"☐ {v}")
                with st.expander("🔎 Evidence"):
                    st.markdown("**What was said**")
                    st.markdown("".join(evidence_line(m) for m in d["conversation_evidence"]), unsafe_allow_html=True)
                    st.markdown("**What the policy says**")
                    if not d["policy_found"]:
                        st.caption("Not found in the uploaded policies.")
                    for p in d["policy_evidence"]:
                        st.markdown(policy_card(p, compact=True), unsafe_allow_html=True)
