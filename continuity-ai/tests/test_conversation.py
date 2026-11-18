import pytest
from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.llm.client import HeuristicExtractor
from app.main import app
from app.services import conversation_service as cs, extraction_service, handover_service

TRANSCRIPT = """Customer: Hi, my payment failed twice and I was still charged.
Agent: Sorry about that. If the payment shows as duplicated, we can refund it.
Customer: How long will that take?
Agent: I will email you the reference number today."""


def test_parse_transcript_and_continuations():
    msgs = cs.parse_transcript("Customer: Hello\nthere\nA: Hi\n\nc: bye")
    assert [m["speaker"] for m in msgs] == ["customer", "agent", "customer"]
    assert msgs[0]["content"] == "Hello there"


@pytest.mark.parametrize("bad", ["just some text", "Agent: hi only agent"])
def test_parse_rejects_unusable_transcripts(bad):
    with pytest.raises(ValueError):
        cs.parse_transcript(bad)


def test_create_case_analyse_not_stale(db):
    out = cs.create_case(db, "Nina Rao", "A101", TRANSCRIPT, "nina@example.com")
    assert out["messages"] == 4
    extraction_service.process_case(db, out["case_id"], HeuristicExtractor())
    h = handover_service.build_handover(db, out["case_id"])
    assert h["processed"] and h["stale"] is False
    assert {c["status"] for c in h["commitments"]} == {"conditional", "promised"}


def test_adding_conversation_makes_analysis_stale(db):
    cid = cs.create_case(db, "Nina Rao", "A101", TRANSCRIPT)["case_id"]
    extraction_service.process_case(db, cid, HeuristicExtractor())
    cs.add_conversation(db, cid, "A102", "Customer: Still no email.\nAgent: I will call you back tomorrow.")
    h = handover_service.build_handover(db, cid)
    assert h["stale"] is True and len(h["history"]) == 2


def test_customer_reused_by_email(db):
    a = cs.create_case(db, "Nina Rao", "A101", TRANSCRIPT, "nina@example.com")["case_id"]
    b = cs.create_case(db, "Nina R.", "A101", TRANSCRIPT, "nina@example.com")["case_id"]
    cust = [r[0] for r in db.execute("SELECT customer_id FROM cases WHERE case_id IN (?,?)", (a, b))]
    assert cust[0] == cust[1]


def test_transfer_and_status(db, case_id):
    cs.transfer_case(db, case_id, "A101")
    row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
    assert row["assigned_agent_id"] == "A101" and row["transferred_from"] == "A103"
    with pytest.raises(ValueError):
        cs.transfer_case(db, case_id, "A101")
    assert cs.set_status(db, case_id, "resolved")["status"] == "resolved"


def test_endpoints(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    assert len(c.get("/agents").json()) == 3
    r = c.post("/cases", json={"customer_name": "Nina", "agent_id": "A101", "transcript": TRANSCRIPT})
    assert r.status_code == 200
    cid = r.json()["case_id"]
    assert c.post("/cases", json={"customer_name": "X", "agent_id": "NOPE", "transcript": TRANSCRIPT}).status_code == 400
    assert c.post("/cases", json={"customer_name": "X", "agent_id": "A101", "transcript": "no labels"}).status_code == 400
    assert c.post(f"/cases/{cid}/conversations", json={"agent_id": "A102", "transcript": "Customer: hi\nAgent: hello"}).status_code == 200
    assert c.post("/cases/999/conversations", json={"agent_id": "A102", "transcript": "Customer: hi"}).status_code == 404
    assert c.post(f"/cases/{cid}/status", json={"status": "resolved"}).json()["status"] == "resolved"
    assert c.post(f"/cases/{cid}/status", json={"status": "bogus"}).status_code == 422
    app.dependency_overrides.clear()
