from fastapi.testclient import TestClient
from app.database.connection import get_db
from app.llm.client import HeuristicExtractor
from app.main import app
import app.api.case_routes as routes


def test_handover_api(db, case_id, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(routes, "get_extractor", lambda: HeuristicExtractor())
    client = TestClient(app)
    cid = case_id

    assert client.get(f"/cases/{cid}/handover").json()["processed"] is False
    assert client.post(f"/cases/{cid}/process").status_code == 200

    h = client.get(f"/cases/{cid}/handover").json()
    assert h["processed"] and h["case"]["customer_name"] == "Aarav Menon"
    assert h["case"]["assigned_agent_name"] == "Meera"
    assert {c["status"] for c in h["commitments"]} >= {"conditional", "promised", "discussed"}
    assert len(h["history"]) == 2 and h["verify_before_responding"]
    assert client.get("/cases").json()[0]["open_commitments"] >= 3
    assert client.get("/cases/999/handover").status_code == 404
    app.dependency_overrides.clear()
