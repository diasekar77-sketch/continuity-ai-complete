import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

import frontend.api as api
from frontend.components.ui import chips, esc, hero, policy_card, setup

setup("Knowledge Base")
hero("Knowledge Base", "Company policies and procedures, split into sections and indexed for grounded answers.", "📚")

left, right = st.columns([1, 1.4], gap="large")

with left:
    st.markdown('<div class="sec">⬆️ Upload a document</div>', unsafe_allow_html=True)
    cat = st.selectbox("Category", ["policy", "troubleshooting", "manual", "procedure"])
    up = st.file_uploader("PDF, Markdown or text", type=["pdf", "md", "txt"])
    if up and st.button("Upload and index", type="primary"):
        try:
            r = api.post("/documents/upload", files={"file": (up.name, up.getvalue())}, data={"category": cat})
            st.success(f"Indexed {r['filename']} into {r['chunks']} section(s).")
        except Exception as e:  # noqa: BLE001
            st.error(f"Upload failed: {e}")

    st.markdown('<div class="sec">🗄️ Indexed documents</div>', unsafe_allow_html=True)
    docs = api.get("/documents")
    if not docs:
        st.info("No documents yet.")
    for d in docs:
        icon = "📕" if d["filename"].lower().endswith(".pdf") else "📄"
        sections = f"{d['chunk_count']} sections"
        st.markdown(f'<div class="doc"><div class="ic">{icon}</div><div><div class="name">{esc(d["filename"])}</div>'
                    f'{chips([d["category"] or "document", sections])}</div></div>',
                    unsafe_allow_html=True)

with right:
    st.markdown('<div class="sec">🔍 Search the policies</div>', unsafe_allow_html=True)
    q = st.text_input("Ask a policy question", placeholder="e.g. Who can offer a goodwill credit?")
    if q:
        res = api.get("/documents/search", q=q, k=3)
        if not res["found"]:
            st.warning("Not found in the uploaded policies. (Nothing scored above the relevance threshold, "
                       "so the system will not guess.)")
        for h in res["hits"]:
            st.markdown(policy_card(h), unsafe_allow_html=True)
