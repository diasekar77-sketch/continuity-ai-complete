import json
import pytest
from fastapi.testclient import TestClient

from app.core.config import ROOT
from app.database.connection import get_db
from app.llm.client import HeuristicExtractor
from app.main import app
from app.rag.embeddings import HashEmbedder
from app.rag.vector_store import VectorStore
from app.services import assistant_service, document_service, extraction_service
import app.api.assistant_routes as assistant_routes


@pytest.fixture
def ready(db, case_id, tmp_path):
    store = VectorStore(path=str(tmp_path / "chroma"), embedder=HashEmbedder())
    for f in (ROOT / "data" / "sample_policies").glob("*.md"):
        document_service.ingest_document(db, store, f.name, f.read_bytes(), "policy")
    extraction_service.process_case(db, case_id, HeuristicExtractor())
    return db, case_id, store


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, system, user, json_mode=False):
        self.last_user = user
        return json.dumps(self.payload)


def test_offline_answer_says_refund_was_conditional(ready):
    db, cid, store = ready
    r = assistant_service.answer_question(db, store, cid, "Was a refund actually promised?")
    assert r["mode"] == "offline"
    assert "No unconditional promise" in r["answer"]
    assert any("eligible for a refund" in m["content"] for m in r["conversation_evidence"])
    assert any(c["status"] == "conditional" for c in r["commitments"])


def test_policy_question_returns_policy_with_source(ready):
    db, cid, store = ready
    r = assistant_service.answer_question(db, store, cid, "What is the goodwill credit policy for a free month?")
    assert r["policy_found"] and r["policy_evidence"][0]["section"] == "4. Goodwill gestures"


def test_unrelated_policy_question_is_reported_as_not_found(ready):
    db, cid, store = ready
    r = assistant_service.answer_question(db, store, cid, "best pasta recipe with tomatoes")
    assert r["policy_found"] is False and "No matching section" in r["answer"]


def test_llm_citations_are_validated(ready):
    db, cid, store = ready
    llm = FakeLLM({"answer": "Only a conditional refund was mentioned.", "citations": ["C1", "M99999", "P1", "Z9"],
                   "verify_before_responding": ["Check billing verification"]})
    r = assistant_service.answer_question(db, store, cid, "Was a refund promised?", llm=llm)
    assert r["mode"] == "llm"
    assert "M99999" not in r["citations"] and "Z9" not in r["citations"]
    assert "P1" in r["citations"]
    assert "[M" in llm.last_user and "[C" in llm.last_user  # evidence groups reached the prompt


def test_llm_failure_falls_back_to_offline(ready):
    db, cid, store = ready

    class Broken:
        def chat(self, *a, **k):
            raise RuntimeError("boom")

    r = assistant_service.answer_question(db, store, cid, "Was a refund promised?", llm=Broken())
    assert r["mode"] == "offline" and r["answer"]


def test_retrieval_is_scoped_to_one_case(ready):
    db, cid, store = ready
    from scripts.seed import seed
    other = seed(db)
    r = assistant_service.answer_question(db, store, other, "refund", extractor=HeuristicExtractor())
    ids = {m["message_id"] for m in r["conversation_evidence"]}
    own = {row[0] for row in db.execute(
        "SELECT m.message_id FROM messages m JOIN interactions i USING(interaction_id) WHERE i.case_id=?", (other,))}
    assert ids <= own


def test_assistant_endpoint(ready, monkeypatch):
    db, cid, store = ready
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(assistant_routes, "get_vector_store", lambda: store)
    monkeypatch.setattr(assistant_routes, "get_llm", lambda: None)
    client = TestClient(app)
    ok = client.post("/assistant/query", json={"case_id": cid, "question": "What should I verify?"})
    assert ok.status_code == 200 and ok.json()["answer"]
    assert client.post("/assistant/query", json={"case_id": 999, "question": "hello there"}).status_code == 404
    app.dependency_overrides.clear()
