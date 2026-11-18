"""Shared look and feel: theme CSS plus small HTML helpers. All dynamic text is HTML-escaped."""
import html
import zlib

import streamlit as st

import frontend.api as api

esc = html.escape

COMMIT_COLORS = {"promised": "#16a34a", "conditional": "#d97706", "discussed": "#64748b", "completed": "#0891b2"}
COMMIT_ICONS = {"promised": "🤝", "conditional": "⚠️", "discussed": "💬", "completed": "✔️"}
CASE_COLORS = {"open": "#16a34a", "transferred": "#7c3aed", "resolved": "#64748b"}
GRADS = [("#6366f1", "#a855f7"), ("#ec4899", "#f97316"), ("#06b6d4", "#3b82f6"),
         ("#10b981", "#84cc16"), ("#f59e0b", "#ef4444")]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.6rem; max-width: 1280px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#ede9fe 0%,#fae8ff 55%,#ffe4e6 100%); }
header[data-testid="stHeader"] { background: transparent; }

.hero { background: linear-gradient(120deg,#4f46e5 0%,#7c3aed 45%,#db2777 100%); border-radius: 20px;
        padding: 26px 32px; margin-bottom: 22px; box-shadow: 0 10px 30px rgba(124,58,237,.28); }
.hero .t { color:#fff !important; font-size: 1.85rem; font-weight: 800; letter-spacing:-.02em; margin:0; }
.hero .s { color:rgba(255,255,255,.88) !important; font-size: 1rem; margin-top: 4px; }

.stat { display:flex; align-items:center; gap:14px; background:#fff; border-radius:16px; padding:16px 18px;
        border:1px solid #ede9fe; border-left:6px solid var(--c); box-shadow:0 4px 14px rgba(76,29,149,.07); }
.stat .ic { font-size:1.7rem; width:46px; height:46px; display:flex; align-items:center; justify-content:center;
            border-radius:12px; background:var(--bg); }
.stat .v { font-size:1.7rem; font-weight:800; line-height:1.1; color:#1e1b4b; }
.stat .l { font-size:.82rem; color:#6b7280; font-weight:500; }

.pill { display:inline-block; padding:3px 12px; border-radius:999px; font-size:.76rem; font-weight:700;
        color:#fff; letter-spacing:.02em; text-transform:capitalize; }
.chip { display:inline-block; padding:3px 11px; margin:3px 5px 3px 0; border-radius:999px; font-size:.78rem;
        font-weight:600; background:linear-gradient(90deg,#ede9fe,#fce7f3); color:#6d28d9; border:1px solid #ddd6fe; }
.muted { color:#6b7280; font-size:.84rem; }
.avatar { display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; border-radius:50%;
          flex-shrink:0; box-shadow:0 3px 8px rgba(0,0,0,.15); }
.row { display:flex; align-items:center; gap:12px; }
.name { font-weight:700; font-size:1.02rem; color:#1e1b4b; }

.handoff { border:1.5px solid #c4b5fd; border-radius:16px; padding:18px 20px; margin:6px 0 14px 0;
           background:linear-gradient(135deg,#faf5ff 0%,#fdf2f8 100%); box-shadow:0 4px 16px rgba(124,58,237,.10); }
.handoff .h { font-weight:800; color:#5b21b6; margin-bottom:6px; font-size:1.02rem; }

.cov { background:#fff; border:1px solid #ede9fe; border-radius:14px; padding:12px 16px; margin-bottom:14px; }
.cov .top { display:flex; justify-content:space-between; font-weight:700; color:#1e1b4b; font-size:.9rem; }
.cov .bar { height:10px; border-radius:999px; background:#ede9fe; margin:8px 0 6px 0; overflow:hidden; }
.cov .bar div { height:100%; border-radius:999px; background:linear-gradient(90deg,#10b981,#06b6d4,#6366f1); }

.sec { font-weight:800; font-size:1.08rem; color:#3730a3; margin:18px 0 8px 0; }
.ccard { border-left:5px solid var(--c); background:var(--bg); border-radius:12px; padding:10px 14px;
         margin-bottom:10px; border-top:1px solid rgba(0,0,0,.04); border-right:1px solid rgba(0,0,0,.04);
         border-bottom:1px solid rgba(0,0,0,.04); }
.ccard .q { color:#374151; font-style:italic; margin-top:6px; }
.pcard { border-left:5px solid #14b8a6; background:#f0fdfa; border-radius:12px; padding:12px 16px; margin-bottom:10px;
         border-top:1px solid #ccfbf1; border-right:1px solid #ccfbf1; border-bottom:1px solid #ccfbf1; }
.pcard .pt { font-weight:700; color:#115e59; }
.score { display:inline-block; padding:1px 9px; border-radius:999px; font-size:.74rem; font-weight:700; color:#fff; }
.ev { border-radius:10px; padding:8px 12px; margin-bottom:6px; background:#faf9ff; border:1px solid #ede9fe; font-size:.9rem; }
.ev.cited { border-color:#86efac; background:#f0fdf4; }
.who { display:inline-block; padding:0 8px; border-radius:6px; font-size:.72rem; font-weight:700; color:#fff; margin-right:6px; }
.ai-head { background:linear-gradient(120deg,#6366f1,#a855f7,#ec4899); color:#fff !important; font-weight:800;
           padding:10px 16px; border-radius:14px; margin-bottom:8px; }
.prog { background:#fff; border:1px solid #ede9fe; border-radius:14px; padding:10px 16px; margin-bottom:10px; }
.prog .top { display:flex; justify-content:space-between; font-weight:700; color:#1e1b4b; font-size:.9rem; }
.prog .bar { height:10px; border-radius:999px; background:#ede9fe; margin-top:8px; overflow:hidden; }
.prog .bar div { height:100%; border-radius:999px; background:linear-gradient(90deg,#f59e0b,#ec4899,#8b5cf6); }
.tl { display:flex; gap:12px; padding:10px 14px; margin-bottom:8px; background:#fff; border:1px solid #ede9fe;
      border-radius:12px; align-items:flex-start; }
.tl .i { font-size:1.2rem; }
.doc { display:flex; gap:12px; align-items:center; background:#fff; border:1px solid #ede9fe; border-radius:14px;
       padding:12px 14px; margin-bottom:10px; box-shadow:0 3px 10px rgba(76,29,149,.05); }
.doc .ic { font-size:1.6rem; }

[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; border:1px solid #e9e3ff !important;
        background:#fff; box-shadow:0 4px 14px rgba(76,29,149,.06); transition: box-shadow .2s, transform .2s; }
[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow:0 8px 24px rgba(124,58,237,.16); }
button[data-testid="stBaseButton-primary"], .stButton button[kind="primary"] {
        background:linear-gradient(90deg,#6366f1,#a855f7,#ec4899); border:none; color:#fff; font-weight:700;
        border-radius:12px; box-shadow:0 6px 16px rgba(168,85,247,.35); }
button[data-testid="stBaseButton-primary"]:hover { filter:brightness(1.08); transform:translateY(-1px); }
button[data-testid="stBaseButton-secondary"], .stButton button[kind="secondary"] {
        border-radius:12px; border:1px solid #ddd6fe; background:#fff; color:#4c1d95; font-weight:600; }
button[data-testid="stBaseButton-secondary"]:hover { border-color:#a855f7; background:#faf5ff; color:#6d28d9; }
[data-testid="stChatMessage"] { background:#fff; border:1px solid #ede9fe; border-radius:14px; }
button[data-baseweb="tab"] { font-weight:700; }
</style>
"""


def setup(title: str):
    st.set_page_config(page_title=f"ContinuityAI | {title}", page_icon="🧠", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    h = api.health()
    with st.sidebar:
        st.markdown("## 🧠 ContinuityAI")
        st.caption("Never make a customer repeat themselves.")
        if h is None:
            st.error("API not reachable")
        else:
            st.success("API online")
            st.caption(f"🤖 LLM: {h['llm_model']}" if h["llm_configured"] else "🧾 Offline evidence mode")
            agents = api.get("/agents")
            ids = [a["agent_id"] for a in agents]
            names = {a["agent_id"]: f"{a['name']} ({a['agent_id']})" for a in agents}
            default = st.session_state.get("me_id") or ("A103" if "A103" in ids else ids[0])
            st.session_state["me_id"] = st.selectbox(
                "👤 Working as", ids, index=ids.index(default) if default in ids else 0,
                format_func=names.get, key="me_select")
    if h is None:
        st.error("Cannot reach the backend. Start it first with `python run.py` "
                 f"(expected at {api.API_URL}).")
        st.stop()
    return h


def tint(hex_color: str, alpha: float = 0.08) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def hero(title: str, subtitle: str, icon: str = "🧠") -> None:
    st.markdown(f'<div class="hero"><div class="t">{icon} {esc(title)}</div>'
                f'<div class="s">{esc(subtitle)}</div></div>', unsafe_allow_html=True)


def stat_card(label: str, value, icon: str, color: str) -> str:
    return (f'<div class="stat" style="--c:{color};--bg:{tint(color, .12)}"><div class="ic">{icon}</div>'
            f'<div><div class="v">{esc(str(value))}</div><div class="l">{esc(label)}</div></div></div>')


def pill(text: str, color: str) -> str:
    return f'<span class="pill" style="background:{color}">{esc(text)}</span>'


def commit_pill(status: str) -> str:
    return pill(f"{COMMIT_ICONS.get(status, '')} {status}", COMMIT_COLORS.get(status, "#64748b"))


def case_pill(status: str) -> str:
    return pill(status, CASE_COLORS.get(status, "#64748b"))


def avatar(name: str, size: int = 44) -> str:
    a, b = GRADS[zlib.crc32(name.encode()) % len(GRADS)]
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return (f'<div class="avatar" style="width:{size}px;height:{size}px;font-size:{size * .38:.0f}px;'
            f'background:linear-gradient(135deg,{a},{b})">{esc(initials)}</div>')


def chips(items) -> str:
    return "".join(f'<span class="chip">{esc(i)}</span>' for i in items)


def coverage_bar(cov: float) -> str:
    return (f'<div class="cov"><div class="top"><span>🛡️ Evidence coverage</span><span>{cov:.0%}</span></div>'
            f'<div class="bar"><div style="width:{cov * 100:.0f}%"></div></div>'
            f'<div class="muted">Share of extracted items whose quote was found verbatim in the transcript.</div></div>')


def commit_card(c: dict) -> str:
    color = COMMIT_COLORS.get(c["status"], "#64748b")
    ok = "✓ verified" if c["verified"] else "⚠ unverified"
    who = esc(c.get("agent_name") or c.get("agent_id") or "agent")
    done_badge = (' &nbsp;<span class="pill" style="background:#0891b2">✔ follow-up done</span>'
                  if c.get("action_status") == "done" else "")
    return (f'<div class="ccard" style="--c:{color};--bg:{tint(color, .07)}">{commit_pill(c["status"])} '
            f'&nbsp;<b>{who}</b> <span class="muted">· message #{c["source_message_id"]} · {ok}</span>{done_badge}'
            f'<div class="q">“{esc(c["quote"])}”</div></div>')


def score_chip(score: float) -> str:
    color = "#16a34a" if score >= 0.4 else "#d97706" if score >= 0.2 else "#64748b"
    return f'<span class="score" style="background:{color}">relevance {score:.2f}</span>'


def policy_card(p: dict, note: str = "", compact: bool = False) -> str:
    text = p["text"]
    if compact and len(text) > 190:
        text = text[:187].rstrip() + "..."
    return (f'<div class="pcard"><div class="pt">📘 {esc(p["section"])}</div>'
            f'<div class="muted">{esc(p["filename"])} &nbsp;{score_chip(p["score"])}</div>'
            f'<div style="margin-top:6px">{esc(text)}</div>'
            f'{f"<div class=muted style=margin-top:6px>{esc(note)}</div>" if note else ""}</div>')


def evidence_line(m: dict) -> str:
    who_color = "#3b82f6" if m["speaker"] == "customer" else "#7c3aed"
    cls = "ev cited" if m.get("cited") else "ev"
    mark = "✅ " if m.get("cited") else ""
    return (f'<div class="{cls}">{mark}<span class="who" style="background:{who_color}">{esc(m["speaker"].title())}</span>'
            f'<span class="muted">#{m["message_id"]}</span><div>{esc(m["content"])}</div></div>')


EVENT_ICONS = {"case_created": "🆕", "conversation_added": "💬", "analysed": "✨", "action_done": "✅",
               "action_reopened": "↩️", "action_added": "➕", "transferred": "🔁", "status_changed": "🏷️"}
EVENT_LABELS = {"case_created": "Case created", "conversation_added": "Conversation added", "analysed": "AI analysis",
                "action_done": "Action completed", "action_reopened": "Action reopened", "action_added": "Action added",
                "transferred": "Case transferred", "status_changed": "Status changed"}


def fmt_time(iso: str | None) -> str:
    return (iso or "").replace("T", " ")[:16]


def action_progress(done: int, total: int) -> str:
    pct = (done / total * 100) if total else 0
    return (f'<div class="prog"><div class="top"><span>✅ Actions and follow-ups</span>'
            f'<span>{done} of {total} done</span></div><div class="bar"><div style="width:{pct:.0f}%"></div></div></div>')


def timeline_row(e: dict) -> str:
    who = esc(e.get("actor_name") or e.get("actor") or "system")
    return (f'<div class="tl"><div class="i">{EVENT_ICONS.get(e["event_type"], "•")}</div><div>'
            f'<div><b>{esc(EVENT_LABELS.get(e["event_type"], e["event_type"]))}</b></div>'
            f'<div>{esc(e.get("detail") or "")}</div>'
            f'<div class="muted">{who} · {fmt_time(e["created_at"])}</div></div></div>')
