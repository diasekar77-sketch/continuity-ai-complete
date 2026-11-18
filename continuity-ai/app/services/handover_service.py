import json
from app.services import action_service
from app.services.extraction_service import fetch_messages


def get_history(conn, case_id: int) -> list[dict]:
    """Full transcript grouped by interaction, straight from SQLite (source of truth)."""
    inter = conn.execute(
        """SELECT i.interaction_id, i.timestamp, i.agent_id, a.name AS agent_name
           FROM interactions i LEFT JOIN agents a ON a.agent_id = i.agent_id
           WHERE i.case_id=? ORDER BY i.timestamp, i.interaction_id""", (case_id,)).fetchall()
    msgs = fetch_messages(conn, case_id)
    return [{**dict(i), "messages": [m for m in msgs if m["interaction_id"] == i["interaction_id"]]} for i in inter]


def gather_policy_evidence(issue: str | None, commitments: list[dict], policy_search) -> dict:
    """One search for the overall issue plus one per agent statement, merged by section.
    Each hit records which statements triggered it, so the agent sees WHY a policy applies."""
    merged: dict[tuple, dict] = {}
    queries = [("issue", issue or "")] + [(f"commitment:{c['commitment_id']}", c["statement"]) for c in commitments]
    for tag, q in queries:
        if not q.strip():
            continue
        for hit in policy_search(q)["hits"]:
            key = (hit["filename"], hit["section"])
            entry = merged.setdefault(key, {**hit, "triggered_by": []})
            entry["score"] = max(entry["score"], hit["score"])
            entry["triggered_by"].append(tag)
    hits = sorted(merged.values(), key=lambda h: -h["score"])
    return {"found": bool(hits), "hits": hits}


def build_handover(conn, case_id: int, policy_search=None) -> dict | None:
    case = conn.execute(
        """SELECT c.*, cu.name AS customer_name, cu.email AS customer_email, a.name AS assigned_agent_name
           FROM cases c JOIN customers cu ON cu.customer_id = c.customer_id
           LEFT JOIN agents a ON a.agent_id = c.assigned_agent_id WHERE c.case_id=?""", (case_id,)).fetchone()
    if not case:
        return None
    mem = conn.execute("SELECT * FROM case_memory WHERE case_id=?", (case_id,)).fetchone()
    commitments = [dict(r) for r in conn.execute(
        """SELECT cm.*, a.name AS agent_name FROM commitments cm LEFT JOIN agents a ON a.agent_id = cm.agent_id
           WHERE cm.case_id=? ORDER BY cm.source_message_id""", (case_id,))]
    actions = action_service.list_actions(conn, case_id)
    status_by_key = {a["action_key"]: a["status"] for a in actions}
    for c in commitments:
        c["action_status"] = status_by_key.get(action_service.action_key(c["statement"]))
    checks = action_service.get_checklist(conn, case_id)
    verify = json.loads(mem["verify_json"]) if mem else []
    verify_items = [{"text": t, "key": action_service.action_key(t), "checked": checks.get(action_service.action_key(t), False)}
                    for t in verify]
    max_id = conn.execute(
        """SELECT MAX(m.message_id) FROM messages m JOIN interactions i ON i.interaction_id = m.interaction_id
           WHERE i.case_id=?""", (case_id,)).fetchone()[0]
    stale = bool(mem and mem["last_message_id"] is not None and max_id and max_id > mem["last_message_id"])
    policy_evidence = {"found": False, "hits": []}
    if policy_search and mem:
        policy_evidence = gather_policy_evidence(mem["issue"], commitments, policy_search)
    return {
        "case": dict(case),
        "processed": mem is not None,
        "stale": stale,
        "summary": mem["summary"] if mem else None,
        "issue": mem["issue"] if mem else case["issue"],
        "sentiment": mem["sentiment"] if mem else None,
        "concerns": json.loads(mem["concerns_json"]) if mem else [],
        "troubleshooting": json.loads(mem["troubleshooting_json"]) if mem else [],
        "commitments": commitments,
        "pending_actions": actions,  # kept for compatibility; same list as "actions"
        "actions": actions,
        "action_counts": {"pending": sum(a["status"] == "pending" for a in actions),
                          "done": sum(a["status"] == "done" for a in actions)},
        "verify_before_responding": verify,
        "verify_items": verify_items,
        "events": action_service.get_events(conn, case_id, 40),
        "evidence_coverage": mem["evidence_coverage"] if mem else None,
        "policy_evidence": policy_evidence,
        "history": get_history(conn, case_id),
    }
