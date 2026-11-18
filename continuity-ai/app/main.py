import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import action_routes, assistant_routes, case_routes, document_routes
from app.core import config
from app.core.config import ROOT
from app.database.connection import connect, init_db


def bootstrap_demo_data():
    """First run convenience: load the sample case and sample policies if the stores are empty."""
    from scripts.seed import seed
    from app.rag.vector_store import get_vector_store
    from app.services import document_service
    conn = connect()
    init_db(conn)
    if conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0:
        seed(conn)
    store = get_vector_store()
    if store.col.count() == 0:
        conn.execute("DELETE FROM documents")
        for f in sorted((ROOT / "data" / "sample_policies").glob("*.md")):
            document_service.ingest_document(conn, store, f.name, f.read_bytes(), "policy")
    conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect()
    init_db(conn)
    conn.close()
    if os.getenv("AUTO_SEED", "1") == "1":
        bootstrap_demo_data()
    yield


app = FastAPI(title="ContinuityAI", version="0.3.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": bool(config.LLM_API_KEY), "llm_model": config.LLM_MODEL}


app.include_router(case_routes.router)
app.include_router(document_routes.router)
app.include_router(assistant_routes.router)
app.include_router(action_routes.router)
