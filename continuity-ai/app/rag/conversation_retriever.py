"""Conversation RAG: find the transcript messages relevant to a question, scoped to ONE case
(metadata filter), then expand each hit with its neighbouring turns from SQLite for context."""
from app.services.extraction_service import fetch_messages


def index_case(conn, store, case_id: int) -> int:
    msgs = fetch_messages(conn, case_id)
    store.upsert_messages(case_id, msgs)  # idempotent
    return len(msgs)


def retrieve(conn, store, case_id: int, question: str, k: int = 4, context: int = 1) -> list[dict]:
    msgs = fetch_messages(conn, case_id)  # source of truth, ordered
    pos = {m["message_id"]: i for i, m in enumerate(msgs)}
    matched = {h["message_id"]: h["score"] for h in store.query_messages(question, case_id, k)}
    keep = set()
    for mid in matched:
        i = pos[mid]
        keep.update(range(max(0, i - context), min(len(msgs), i + context + 1)))
    return [{**msgs[i], "matched": msgs[i]["message_id"] in matched,
             "score": matched.get(msgs[i]["message_id"])} for i in sorted(keep)]
