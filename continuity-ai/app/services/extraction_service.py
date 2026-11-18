"""Extract case memory, VERIFY it against the stored transcript, persist it.

Verification is the anti-hallucination layer: every extracted item must carry a quote that
actually exists in the cited message. Items that fail are kept but flagged unverified."""
import json
import re
from datetime import datetime, timezone

from app.database.schemas import CaseMemory
from app.services import action_service


def fetch_messages(conn, case_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT m.message_id, m.interaction_id, m.speaker, m.content, m.timestamp, i.agent_id
           FROM messages m JOIN interactions i ON i.interaction_id = m.interaction_id
           WHERE i.case_id = ? ORDER BY m.timestamp, m.message_id""", (case_id,)).fetchall()
    return [dict(r) for r in rows]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def verify_quote(quote: str, source_id: int, by_id: dict[int, dict]) -> tuple[bool, int]:
    """True if the quote appears in the cited message. If it appears in a different message of
    the same case, re-anchor to that message (LLMs often get the id off by one)."""
    q = _norm(quote)
    if not q:
        return False, source_id
    cited = by_id.get(source_id)
    if cited and q in _norm(cited["content"]):
        return True, source_id
    for mid, m in by_id.items():
        if q in _norm(m["content"]):
            return True, mid
    return False, source_id


def verify_memory(memory: CaseMemory, messages: list[dict]) -> dict:
    by_id = {m["message_id"]: m for m in messages}
    out = {"commitments": [], "troubleshooting": [], "pending_actions": []}

    for c in memory.commitments:
        ok, mid = verify_quote(c.quote, c.source_message_id, by_id)
        msg = by_id.get(mid)
        if ok and msg["speaker"] != "agent":
            continue  # customer statements are never commitments
        out["commitments"].append({**c.model_dump(), "source_message_id": mid, "verified": ok,
                                   "agent_id": msg["agent_id"] if msg else None})
    for t in memory.troubleshooting:
        ok, mid = verify_quote(t.quote, t.source_message_id, by_id)
        out["troubleshooting"].append({**t.model_dump(), "source_message_id": mid, "verified": ok})
    for p in memory.pending_actions:
        ok, mid = verify_quote(p.quote, p.source_message_id, by_id)
        out["pending_actions"].append({**p.model_dump(), "source_message_id": mid, "verified": ok})

    items = [i for k in out.values() for i in k]
    out["evidence_coverage"] = round(sum(i["verified"] for i in items) / len(items), 2) if items else 1.0
    return out


def process_case(conn, case_id: int, extractor, by: str | None = None) -> dict:
    messages = fetch_messages(conn, case_id)
    if not messages:
        raise ValueError("Case has no messages to process")
    memory = extractor.extract(messages)
    v = verify_memory(memory, messages)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Re-processing replaces derived data only; transcripts are never touched.
    conn.execute("DELETE FROM commitments WHERE case_id=?", (case_id,))
    # Actions: pending AI actions are rebuilt; DONE ones and manually added ones are kept.
    done_keys = {r["action_key"] or action_service.action_key(r["description"]) for r in conn.execute(
        "SELECT * FROM actions WHERE case_id=? AND COALESCE(source,'ai')='ai' AND status='done'", (case_id,))}
    conn.execute("DELETE FROM actions WHERE case_id=? AND COALESCE(source,'ai')='ai' AND status!='done'", (case_id,))
    for c in v["commitments"]:
        conn.execute(
            "INSERT INTO commitments (case_id, statement, status, source_message_id, quote, verified, agent_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (case_id, c["description"], c["status"], c["source_message_id"], c["quote"], int(c["verified"]), c["agent_id"]))
    seen = set(done_keys)
    manual_keys = {r["action_key"] for r in conn.execute(
        "SELECT action_key FROM actions WHERE case_id=? AND source='manual'", (case_id,))}
    for p in v["pending_actions"]:
        key = action_service.action_key(p["description"])
        if key in seen or key in manual_keys:
            continue
        seen.add(key)
        conn.execute(
            "INSERT INTO actions (case_id, description, status, source_message_id, verified, source, action_key, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (case_id, p["description"], "pending", p["source_message_id"], int(p["verified"]), "ai", key, now))
    conn.execute(
        """INSERT OR REPLACE INTO case_memory
           (case_id, issue, summary, sentiment, concerns_json, troubleshooting_json, verify_json, evidence_coverage, processed_at, last_message_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (case_id, memory.issue, memory.summary, memory.sentiment, json.dumps(memory.concerns),
         json.dumps(v["troubleshooting"]), json.dumps(memory.verify_before_responding),
         v["evidence_coverage"], now, max(m["message_id"] for m in messages)))
    conn.execute("UPDATE cases SET issue=COALESCE(issue, ?), updated_at=? WHERE case_id=?", (memory.issue, now, case_id))
    action_service.log_event(conn, case_id, "analysed",
                             f"AI analysis ({getattr(extractor, 'name', 'unknown')}): {len(v['commitments'])} commitments, "
                             f"evidence coverage {v['evidence_coverage']:.0%}", by, commit=False)
    conn.commit()
    return {"case_id": case_id, "extractor": getattr(extractor, "name", "unknown"),
            "commitments": len(v["commitments"]), "evidence_coverage": v["evidence_coverage"]}
