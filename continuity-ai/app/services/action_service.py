"""Actions (follow-ups), saved checklist ticks and the case activity log."""
import hashlib
import re
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def action_key(text: str) -> str:
    """Stable id for a statement, so state survives re-analysis (same wording = same key)."""
    norm = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def log_event(conn, case_id: int, event_type: str, detail: str = "", actor: str | None = None, commit: bool = True):
    conn.execute("INSERT INTO events (case_id, event_type, detail, actor, created_at) VALUES (?,?,?,?,?)",
                 (case_id, event_type, detail, actor, _now()))
    if commit:
        conn.commit()


def get_events(conn, case_id: int, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT e.*, a.name AS actor_name FROM events e LEFT JOIN agents a ON a.agent_id = e.actor
           WHERE e.case_id=? ORDER BY e.event_id DESC LIMIT ?""", (case_id, limit)).fetchall()
    return [dict(r) for r in rows]


def list_actions(conn, case_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT a.*, ag.name AS completed_by_name FROM actions a
           LEFT JOIN agents ag ON ag.agent_id = a.completed_by
           WHERE a.case_id=? ORDER BY CASE a.status WHEN 'pending' THEN 0 ELSE 1 END, a.action_id""",
        (case_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["action_key"] = d["action_key"] or action_key(d["description"])
        d["source"] = d["source"] or "ai"
        out.append(d)
    return out


def set_action_status(conn, action_id: int, done: bool, by: str | None = None) -> dict:
    row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
    if not row:
        raise LookupError("Action not found")
    if done:
        conn.execute("UPDATE actions SET status='done', completed_at=?, completed_by=? WHERE action_id=?",
                     (_now(), by, action_id))
    else:
        conn.execute("UPDATE actions SET status='pending', completed_at=NULL, completed_by=NULL WHERE action_id=?",
                     (action_id,))
    log_event(conn, row["case_id"], "action_done" if done else "action_reopened",
              row["description"][:140], by, commit=False)
    conn.commit()
    return {"action_id": action_id, "status": "done" if done else "pending"}


def add_manual_action(conn, case_id: int, description: str, by: str | None = None,
                      assigned_agent: str | None = None) -> dict:
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise LookupError("Case not found")
    description = description.strip()
    key = action_key(description)
    if any(a["action_key"] == key for a in list_actions(conn, case_id)):
        raise ValueError("That action already exists on this case")
    cur = conn.execute(
        """INSERT INTO actions (case_id, description, status, assigned_agent, source, action_key, created_at, verified)
           VALUES (?,?,?,?,?,?,?,1)""", (case_id, description, "pending", assigned_agent or by, "manual", key, _now()))
    log_event(conn, case_id, "action_added", description[:140], by, commit=False)
    conn.commit()
    return {"action_id": cur.lastrowid}


def set_checklist(conn, case_id: int, item: str, checked: bool, by: str | None = None) -> dict:
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise LookupError("Case not found")
    conn.execute(
        """INSERT INTO checklist (case_id, item_key, checked, updated_by, updated_at) VALUES (?,?,?,?,?)
           ON CONFLICT(case_id, item_key) DO UPDATE SET checked=excluded.checked,
           updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
        (case_id, action_key(item), int(checked), by, _now()))
    conn.commit()
    return {"item_key": action_key(item), "checked": checked}


def get_checklist(conn, case_id: int) -> dict[str, bool]:
    return {r["item_key"]: bool(r["checked"])
            for r in conn.execute("SELECT item_key, checked FROM checklist WHERE case_id=?", (case_id,))}
