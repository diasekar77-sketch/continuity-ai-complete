"""Evidence-based answers. Conversation evidence (what was said), tracked commitments, and policy
evidence (what the company permits) are retrieved separately and handed to the LLM as labelled,
separate groups. Citations returned by the LLM are validated against the evidence actually supplied."""
import re

from pydantic import ValidationError

from app.core.prompts import ASSISTANT_SYSTEM
from app.database.schemas import LLMAnswer
from app.llm.client import HeuristicExtractor, _clean_json
from app.rag import conversation_retriever, policy_retriever
from app.services import extraction_service

_STOP = set("a an the and or of to in on for is are was were be by with as at it this that from what which "
            "who did does do was has have had customer previous agent told me about actually".split())


def _stems(text: str) -> set[str]:
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w
            for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP}


def _relevant_commitments(question: str, commitments: list[dict]) -> list[dict]:
    q = _stems(question)
    scored = [c for c in commitments if q & _stems(c["statement"])]
    return scored or commitments


def _offline_answer(question: str, commitments: list[dict], policy: dict) -> str:
    rel = _relevant_commitments(question, commitments)
    parts = ["(Offline evidence mode: no LLM configured, so this lists the evidence without synthesis.)"]
    if rel:
        asks_promise = re.search(r"promis|commit|approv|guarantee", question, re.I)
        statuses = {c["status"] for c in rel}
        if asks_promise:
            if "promised" in statuses or "completed" in statuses:
                parts.append("An agent made a firm commitment on this topic (see below).")
            else:
                parts.append("No unconditional promise on this topic was found; the statements are only "
                             "conditional or discussed.")
        for c in rel:
            who = c.get("agent_name") or c.get("agent_id") or "agent"
            parts.append(f'- {c["status"].upper()} ({who}): "{c["quote"]}"')
    if policy["found"]:
        top = policy["hits"][0]
        parts.append(f'Most relevant policy: {top["filename"]} > {top["section"]}.')
    else:
        parts.append("No matching section was found in the uploaded policies.")
    return "\n".join(parts)


def _format_evidence(conv, commitments, policy_hits) -> str:
    lines = ["CONVERSATION:"]
    for m in conv:
        lines.append(f"[M{m['message_id']}] {m['speaker'].upper()} ({m.get('agent_id') or 'customer'}, "
                     f"{m['timestamp']}): {m['content']}")
    lines.append("\nCOMMITMENTS (tracked by the system):")
    for c in commitments:
        lines.append(f"[C{c['commitment_id']}] status={c['status']} by {c.get('agent_id')} "
                     f"{'(verified)' if c['verified'] else '(UNVERIFIED)'}: \"{c['quote']}\"")
    lines.append("\nPOLICY:")
    if not policy_hits:
        lines.append("(no relevant policy section was found)")
    for i, h in enumerate(policy_hits, 1):
        lines.append(f"[P{i}] {h['filename']} > {h['section']}: {h['text']}")
    return "\n".join(lines)


def answer_question(conn, store, case_id: int, question: str, llm=None, extractor=None, k: int = 4) -> dict:
    if not conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
        raise LookupError("Case not found")
    if not conn.execute("SELECT 1 FROM case_memory WHERE case_id=?", (case_id,)).fetchone():
        extraction_service.process_case(conn, case_id, extractor or HeuristicExtractor())

    conversation_retriever.index_case(conn, store, case_id)
    conv = conversation_retriever.retrieve(conn, store, case_id, question, k=k)
    policy = policy_retriever.search(store, question, k=2)
    commitments = [dict(r) for r in conn.execute(
        """SELECT cm.*, a.name AS agent_name FROM commitments cm LEFT JOIN agents a ON a.agent_id = cm.agent_id
           WHERE cm.case_id=? ORDER BY cm.source_message_id""", (case_id,))]

    valid_ids = ({f"M{m['message_id']}" for m in conv} | {f"C{c['commitment_id']}" for c in commitments}
                 | {f"P{i}" for i in range(1, len(policy["hits"]) + 1)})
    answer, citations, verify, mode = None, [], [], "offline"
    if llm is not None:
        try:
            raw = llm.chat(ASSISTANT_SYSTEM, f"Question: {question}\n\n" + _format_evidence(conv, commitments, policy["hits"]),
                           json_mode=True)
            parsed = LLMAnswer.model_validate_json(_clean_json(raw))
            if parsed.answer.strip():
                answer, verify, mode = parsed.answer.strip(), parsed.verify_before_responding, "llm"
                citations = [c for c in dict.fromkeys(parsed.citations) if c in valid_ids]  # drop invented ids
        except (ValidationError, Exception) as e:  # noqa: BLE001 - never fail the agent because the LLM did
            print(f"[ContinuityAI] assistant LLM failed ({type(e).__name__}); using offline evidence mode")
    if answer is None:
        answer = _offline_answer(question, commitments, policy)
        citations = [f"M{m['message_id']}" for m in conv if m["matched"]] + \
                    [f"P{i}" for i in range(1, len(policy["hits"]) + 1)]

    cited = set(citations)
    return {
        "answer": answer, "mode": mode, "citations": citations, "verify_before_responding": verify,
        "conversation_evidence": [{**m, "cited": f"M{m['message_id']}" in cited} for m in conv],
        "commitments": [{**c, "cited": f"C{c['commitment_id']}" in cited} for c in commitments],
        "policy_evidence": [{**h, "ref": f"P{i}", "cited": f"P{i}" in cited}
                            for i, h in enumerate(policy["hits"], 1)],
        "policy_found": policy["found"],
    }
