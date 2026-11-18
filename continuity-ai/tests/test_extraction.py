from app.database.schemas import CaseMemory, Commitment
from app.llm.client import HeuristicExtractor
from app.services import extraction_service as svc


def _statuses(db, case_id):
    rows = db.execute("SELECT statement, status, verified FROM commitments WHERE case_id=?", (case_id,)).fetchall()
    return {r["statement"]: (r["status"], r["verified"]) for r in rows}


def test_refund_is_conditional_not_promised(db, case_id):
    svc.process_case(db, case_id, HeuristicExtractor())
    refund = [v for k, v in _statuses(db, case_id).items() if "eligible for a refund" in k]
    assert refund == [("conditional", 1)]


def test_status_classification(db, case_id):
    svc.process_case(db, case_id, HeuristicExtractor())
    s = _statuses(db, case_id)
    assert s["I will email you the billing reference number by tomorrow."][0] == "promised"
    assert any(v[0] == "discussed" and "free month" in k for k, v in s.items())


def test_all_extracted_items_verified(db, case_id):
    out = svc.process_case(db, case_id, HeuristicExtractor())
    assert out["evidence_coverage"] == 1.0


def test_fabricated_quote_is_flagged(db, case_id):
    msgs = svc.fetch_messages(db, case_id)
    agent_msg = next(m for m in msgs if m["speaker"] == "agent")
    fake = CaseMemory(issue="x", summary="x", commitments=[Commitment(
        description="Full refund approved", status="promised",
        source_message_id=agent_msg["message_id"], quote="Your full refund has been approved")])
    v = svc.verify_memory(fake, msgs)
    assert v["commitments"][0]["verified"] is False
    assert v["evidence_coverage"] == 0.0


def test_wrong_message_id_is_reanchored(db, case_id):
    msgs = svc.fetch_messages(db, case_id)
    target = next(m for m in msgs if "billing reference number by tomorrow" in m["content"])
    wrong = msgs[0]["message_id"]
    mem = CaseMemory(issue="x", summary="x", commitments=[Commitment(
        description="email ref", status="promised", source_message_id=wrong,
        quote="I will email you the billing reference number by tomorrow.")])
    c = svc.verify_memory(mem, msgs)["commitments"][0]
    assert c["verified"] and c["source_message_id"] == target["message_id"]


def test_customer_statement_never_becomes_commitment(db, case_id):
    msgs = svc.fetch_messages(db, case_id)
    cust = next(m for m in msgs if m["speaker"] == "customer")
    mem = CaseMemory(issue="x", summary="x", commitments=[Commitment(
        description="customer says refund", status="promised", source_message_id=cust["message_id"],
        quote="Both charges show on my card statement.")])
    assert svc.verify_memory(mem, msgs)["commitments"] == []


def test_reprocess_does_not_touch_transcript(db, case_id):
    before = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    svc.process_case(db, case_id, HeuristicExtractor())
    svc.process_case(db, case_id, HeuristicExtractor())
    assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == before
    n = db.execute("SELECT COUNT(*) FROM commitments WHERE case_id=?", (case_id,)).fetchone()[0]
    assert n == len(_statuses(db, case_id))
