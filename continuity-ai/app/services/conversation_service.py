"""Create cases, add conversations (pasted transcripts) and transfer cases."""
import re
from datetime import datetime, timedelta, timezone

from app.services import action_service

_LABEL = re.compile(r"^\s*(customer|client|cust|c|agent|support|a)\s*[:\-]\s*(.*)$", re.I)
_SPEAKER = {"customer": "customer", "client": "customer", "cust": "customer", "c": "customer",
            "agent": "agent", "support": "agent", "a": "agent"}
FORMAT_HINT = "Start every line with 'Customer:' or 'Agent:'."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_transcript(text: str) -> list[dict]:
    msgs: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _LABEL.match(line)
        if m:
            msgs.append({"speaker": _SPEAKER[m.group(1).lower()], "content": m.group(2).strip()})
        elif msgs:  # continuation of the previous message
            msgs[-1]["content"] += " " + line.strip()
        else:
            raise ValueError(f"Could not read the first line. {FORMAT_HINT}")
    msgs = [m for m in msgs if m["content"]]
    if not any(m["speaker"] == "customer" for m in msgs):
        raise ValueError(f"No customer message found. {FORMAT_HINT}")
    return msgs


def _check_agent(conn, agent_id: str) -> None:
    if not conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone():
        raise ValueError(f"Unknown agent: {agent_id}")


def _insert_interaction(conn, case_id: int, agent_id: str, messages: list[dict]) -> int:
    # Back-dated so the last message is 'now' (keeps ordering sane and avoids future timestamps).
    start = _now() - timedelta(seconds=20 * len(messages))
    cur = conn.execute("INSERT INTO interactions (case_id, agent_id, timestamp) VALUES (?,?,?)",
                       (case_id, agent_id, start.isoformat()))
    for i, m in enumerate(messages):
        conn.execute("INSERT INTO messages (interaction_id, speaker, content, timestamp) VALUES (?,?,?,?)",
                     (cur.lastrowid, m["speaker"], m["content"], (start + timedelta(seconds=20 * (i + 1))).isoformat()))
    return cur.lastrowid


def create_case(conn, customer_name: str, agent_id: str, transcript: str, customer_email: str | None = None) -> dict:
    _check_agent(conn, agent_id)
    messages = parse_transcript(transcript)
    row = None
    if customer_email:
        row = conn.execute("SELECT customer_id FROM customers WHERE email=?", (customer_email,)).fetchone()
    cust_id = row["customer_id"] if row else conn.execute(
        "INSERT INTO customers (name, email) VALUES (?,?)", (customer_name.strip(), customer_email)).lastrowid
    now = _now().isoformat()
    case_id = conn.execute(
        "INSERT INTO cases (customer_id, status, assigned_agent_id, created_at, updated_at) VALUES (?,?,?,?,?)",
        (cust_id, "open", agent_id, now, now)).lastrowid
    interaction_id = _insert_interaction(conn, case_id, agent_id, messages)
    action_service.log_event(conn, case_id, "case_created", f"Case opened with {len(messages)} messages", agent_id, commit=False)
    conn.commit()
    return {"case_id": case_id, "interaction_id": interaction_id, "messages": len(messages)}


def add_conversation(conn, case_id: int, agent_id: str, transcript: str) -> dict:
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise LookupError("Case not found")
    _check_agent(conn, agent_id)
    messages = parse_transcript(transcript)
    interaction_id = _insert_interaction(conn, case_id, agent_id, messages)
    conn.execute("UPDATE cases SET updated_at=? WHERE case_id=?", (_now().isoformat(), case_id))
    action_service.log_event(conn, case_id, "conversation_added", f"New conversation added ({len(messages)} messages)",
                             agent_id, commit=False)
    conn.commit()
    return {"case_id": case_id, "interaction_id": interaction_id, "messages": len(messages)}


def transfer_case(conn, case_id: int, to_agent_id: str, by: str | None = None) -> dict:
    case = conn.execute("SELECT assigned_agent_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not case:
        raise LookupError("Case not found")
    _check_agent(conn, to_agent_id)
    if case["assigned_agent_id"] == to_agent_id:
        raise ValueError("Case is already assigned to that agent")
    conn.execute("UPDATE cases SET transferred_from=?, assigned_agent_id=?, status='transferred', updated_at=? WHERE case_id=?",
                 (case["assigned_agent_id"], to_agent_id, _now().isoformat(), case_id))
    action_service.log_event(conn, case_id, "transferred", f"{case['assigned_agent_id']} → {to_agent_id}", by, commit=False)
    conn.commit()
    return {"case_id": case_id, "assigned_agent_id": to_agent_id}


def set_status(conn, case_id: int, status: str, by: str | None = None) -> dict:
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise LookupError("Case not found")
    conn.execute("UPDATE cases SET status=?, updated_at=? WHERE case_id=?", (status, _now().isoformat(), case_id))
    action_service.log_event(conn, case_id, "status_changed", f"Status set to {status}", by, commit=False)
    conn.commit()
    return {"case_id": case_id, "status": status}
