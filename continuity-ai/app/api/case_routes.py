from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.database.connection import get_db
from app.database.schemas import (InteractionCreate, MessageCreate, NewCase, NewConversation,
                                  StatusUpdate, TransferRequest)
from app.llm.client import get_extractor
from app.rag import policy_retriever
from app.rag.vector_store import get_vector_store
from app.services import conversation_service, extraction_service, handover_service

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.get("/cases")
def list_cases(status: str | None = None, conn=Depends(get_db)):
    q = """SELECT c.case_id, c.issue, c.status, c.assigned_agent_id, c.transferred_from, c.updated_at,
                  cu.name AS customer_name,
                  (SELECT COUNT(*) FROM interactions i WHERE i.case_id = c.case_id) AS interactions,
                  (SELECT COUNT(*) FROM commitments m WHERE m.case_id = c.case_id
                     AND m.status IN ('promised','conditional')) AS open_commitments,
                  (SELECT COUNT(*) FROM actions a WHERE a.case_id = c.case_id AND a.status = 'pending') AS open_actions,
                  (SELECT COUNT(*) FROM actions a WHERE a.case_id = c.case_id AND a.status = 'done') AS done_actions
           FROM cases c JOIN customers cu ON cu.customer_id = c.customer_id"""
    args = []
    if status:
        q += " WHERE c.status = ?"
        args.append(status)
    return [dict(r) for r in conn.execute(q + " ORDER BY c.updated_at DESC", args)]


@router.get("/cases/{case_id}")
def get_case(case_id: int, conn=Depends(get_db)):
    data = handover_service.build_handover(conn, case_id)
    if not data:
        raise HTTPException(404, "Case not found")
    return data["case"]


@router.get("/cases/{case_id}/history")
def history(case_id: int, conn=Depends(get_db)):
    return handover_service.get_history(conn, case_id)


@router.post("/cases/{case_id}/interactions")
def start_interaction(case_id: int, body: InteractionCreate, conn=Depends(get_db)):
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise HTTPException(404, "Case not found")
    cur = conn.execute("INSERT INTO interactions (case_id, agent_id, timestamp) VALUES (?,?,?)",
                       (case_id, body.agent_id, body.timestamp or _now()))
    conn.commit()
    return {"interaction_id": cur.lastrowid}


@router.post("/interactions/{interaction_id}/messages")
def add_message(interaction_id: int, body: MessageCreate, conn=Depends(get_db)):
    if not conn.execute("SELECT 1 FROM interactions WHERE interaction_id=?", (interaction_id,)).fetchone():
        raise HTTPException(404, "Interaction not found")
    cur = conn.execute("INSERT INTO messages (interaction_id, speaker, content, timestamp) VALUES (?,?,?,?)",
                       (interaction_id, body.speaker, body.content, body.timestamp or _now()))
    conn.commit()
    return {"message_id": cur.lastrowid}


@router.post("/cases/{case_id}/process")
def process(case_id: int, by: str | None = None, conn=Depends(get_db)):
    try:
        return extraction_service.process_case(conn, case_id, get_extractor(), by)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/cases/{case_id}/handover")
def handover(case_id: int, conn=Depends(get_db)):
    data = handover_service.build_handover(
        conn, case_id, policy_search=lambda q: policy_retriever.search(get_vector_store(), q, k=2))
    if not data:
        raise HTTPException(404, "Case not found")
    return data


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/agents")
def agents(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT agent_id, name, role FROM agents ORDER BY agent_id")]


@router.post("/cases")
def create_case(body: NewCase, conn=Depends(get_db)):
    return _run(conversation_service.create_case, conn, body.customer_name, body.agent_id, body.transcript,
                body.customer_email)


@router.post("/cases/{case_id}/conversations")
def add_conversation(case_id: int, body: NewConversation, conn=Depends(get_db)):
    return _run(conversation_service.add_conversation, conn, case_id, body.agent_id, body.transcript)


@router.post("/cases/{case_id}/transfer")
def transfer(case_id: int, body: TransferRequest, conn=Depends(get_db)):
    return _run(conversation_service.transfer_case, conn, case_id, body.to_agent_id, body.by)


@router.post("/cases/{case_id}/status")
def status(case_id: int, body: StatusUpdate, conn=Depends(get_db)):
    return _run(conversation_service.set_status, conn, case_id, body.status, body.by)
