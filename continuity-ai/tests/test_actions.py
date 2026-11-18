import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.database.connection import get_db, init_db
from app.llm.client import HeuristicExtractor
from app.main import app
from app.services import action_service as act, conversation_service as cs, extraction_service as ex, handover_service as hs


@pytest.fixture
def analysed(db, case_id):
    ex.process_case(db, case_id, HeuristicExtractor(), "A103")
    return db, case_id


def test_analysis_creates_pending_actions_with_keys(analysed):
    db, cid = analysed
    actions = act.list_actions(db, cid)
    assert len(actions) == 4 and all(a["status"] == "pending" and a["source"] == "ai" and a["action_key"] for a in actions)


def test_mark_done_persists_through_reanalysis(analysed):
    db, cid = analysed
    target = next(a for a in act.list_actions(db, cid) if "billing reference" in a["description"])
    act.set_action_status(db, target["action_id"], True, "A103")
    ex.process_case(db, cid, HeuristicExtractor(), "A103")
    after = act.list_actions(db, cid)
    done = [a for a in after if a["status"] == "done"]
    assert len(after) == 4 and len(done) == 1 and done[0]["completed_by"] == "A103"
    assert sum("billing reference" in a["description"] for a in after) == 1   # not duplicated


def test_reopen_and_manual_actions_survive_reanalysis(analysed):
    db, cid = analysed
    a = act.add_manual_action(db, cid, "Call the customer on Tuesday", "A103")
    with pytest.raises(ValueError):
        act.add_manual_action(db, cid, "call the customer on  tuesday", "A103")   # duplicate (normalised)
    ex.process_case(db, cid, HeuristicExtractor(), "A103")
    manual = [x for x in act.list_actions(db, cid) if x["source"] == "manual"]
    assert len(manual) == 1 and manual[0]["action_id"] == a["action_id"]
    act.set_action_status(db, a["action_id"], True, "A103")
    act.set_action_status(db, a["action_id"], False, "A103")
    assert next(x for x in act.list_actions(db, cid) if x["action_id"] == a["action_id"])["status"] == "pending"


def test_checklist_ticks_are_saved_and_survive_reanalysis(analysed):
    db, cid = analysed
    item = hs.build_handover(db, cid)["verify_items"][0]
    assert item["checked"] is False
    act.set_checklist(db, cid, item["text"], True, "A103")
    ex.process_case(db, cid, HeuristicExtractor(), "A103")
    assert hs.build_handover(db, cid)["verify_items"][0]["checked"] is True


def test_handover_counts_and_commitment_action_status(analysed):
    db, cid = analysed
    h = hs.build_handover(db, cid)
    assert h["action_counts"] == {"pending": 4, "done": 0}
    first = h["actions"][0]
    act.set_action_status(db, first["action_id"], True, "A103")
    h = hs.build_handover(db, cid)
    assert h["action_counts"] == {"pending": 3, "done": 1}
    assert any(c["action_status"] == "done" for c in h["commitments"])


def test_events_are_logged_in_order(analysed):
    db, cid = analysed
    a = act.list_actions(db, cid)[0]
    act.set_action_status(db, a["action_id"], True, "A103")
    cs.transfer_case(db, cid, "A101", "A103")
    cs.set_status(db, cid, "resolved", "A101")
    types = [e["event_type"] for e in act.get_events(db, cid)]
    assert types == ["status_changed", "transferred", "action_done", "analysed"]
    assert act.get_events(db, cid)[0]["actor_name"] == "Priya"


def test_old_database_is_migrated(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.executescript("""CREATE TABLE actions (action_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL,
        description TEXT NOT NULL, status TEXT DEFAULT 'pending', assigned_agent TEXT, source_message_id INTEGER,
        verified INTEGER DEFAULT 0);
        CREATE TABLE case_memory (case_id INTEGER PRIMARY KEY, issue TEXT, summary TEXT, sentiment TEXT,
        concerns_json TEXT, troubleshooting_json TEXT, verify_json TEXT, evidence_coverage REAL, processed_at TEXT);""")
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(actions)")}
    assert {"action_key", "source", "completed_at", "completed_by", "created_at"} <= cols


def test_endpoints(analysed):
    db, cid = analysed
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    aid = c.get(f"/cases/{cid}/actions").json()[0]["action_id"]
    assert c.post(f"/actions/{aid}/status", json={"done": True, "by": "A103"}).json()["status"] == "done"
    assert c.post(f"/cases/{cid}/actions", json={"description": "Send a follow-up email", "by": "A103"}).status_code == 200
    assert c.post(f"/cases/{cid}/actions", json={"description": "Send a follow-up email"}).status_code == 400
    assert c.post(f"/cases/{cid}/checklist", json={"item": "x check", "checked": True}).status_code == 200
    assert c.post("/actions/999/status", json={"done": True}).status_code == 404
    row = c.get("/cases").json()[0]
    assert row["open_actions"] == 4 and row["done_actions"] == 1   # 4 pending after +1 manual, -1 done
    assert len(c.get(f"/cases/{cid}/events").json()) >= 3
    app.dependency_overrides.clear()
