import pytest
from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.llm.client import HeuristicExtractor
from app.main import app
from app.rag import policy_retriever, text_splitter
from app.rag.embeddings import HashEmbedder
from app.rag.vector_store import VectorStore
import app.api.case_routes as case_routes
import app.api.document_routes as document_routes
from app.core.config import ROOT
from app.services import document_service

POLICIES = ROOT / "data" / "sample_policies"


@pytest.fixture
def store(tmp_path):
    return VectorStore(path=str(tmp_path / "chroma"), embedder=HashEmbedder())


@pytest.fixture
def loaded(db, store):
    for f in POLICIES.glob("*.md"):
        document_service.ingest_document(db, store, f.name, f.read_bytes(), "policy")
    return store


def test_split_keeps_sections():
    chunks = text_splitter.split_policy((POLICIES / "refund_and_billing_policy.md").read_text())
    titles = [c["section"] for c in chunks]
    assert "1. Duplicate charges" in titles and len(chunks) == 5


def test_duplicate_charge_query_finds_refund_section(loaded):
    r = policy_retriever.search(loaded, "customer charged twice duplicate payment refund eligibility")
    assert r["found"] and r["hits"][0]["section"] == "1. Duplicate charges"
    assert r["hits"][0]["filename"] == "refund_and_billing_policy.md"


def test_goodwill_query_finds_senior_agent_rule(loaded):
    r = policy_retriever.search(loaded, "can I offer a free month goodwill credit")
    assert r["hits"][0]["section"] == "4. Goodwill gestures"


def test_unrelated_query_abstains(loaded):
    r = policy_retriever.search(loaded, "best pasta recipe with tomatoes")
    assert r["found"] is False and r["hits"] == []


def test_pdf_ingestion(db, store):
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, "1. Replacement policy")
    c.drawString(72, 730, "Devices are replaced within 30 days if the defect is confirmed.")
    c.save()
    out = document_service.ingest_document(db, store, "replacement.pdf", buf.getvalue(), "policy")
    assert out["chunks"] >= 1
    assert policy_retriever.search(store, "device replacement defect confirmed")["found"]


def test_unsupported_file_rejected(db, store):
    with pytest.raises(ValueError):
        document_service.ingest_document(db, store, "x.exe", b"abc")


def test_handover_includes_policy_evidence(db, case_id, loaded, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(case_routes, "get_extractor", lambda: HeuristicExtractor())
    monkeypatch.setattr(case_routes, "get_vector_store", lambda: loaded)
    client = TestClient(app)
    client.post(f"/cases/{case_id}/process")
    h = client.get(f"/cases/{case_id}/handover").json()
    sections = {x["section"] for x in h["policy_evidence"]["hits"]}
    assert h["policy_evidence"]["found"] and {"1. Duplicate charges", "4. Goodwill gestures"} <= sections
    goodwill = next(x for x in h["policy_evidence"]["hits"] if x["section"] == "4. Goodwill gestures")
    assert any(t.startswith("commitment:") for t in goodwill["triggered_by"])
    app.dependency_overrides.clear()
