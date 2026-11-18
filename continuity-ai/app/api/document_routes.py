from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.database.connection import get_db
from app.rag import policy_retriever
from app.rag.vector_store import get_vector_store
from app.services import document_service

router = APIRouter()


@router.post("/documents/upload")
async def upload(file: UploadFile = File(...), category: str = Form("policy"), conn=Depends(get_db)):
    try:
        return document_service.ingest_document(conn, get_vector_store(), file.filename, await file.read(), category)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/documents")
def documents(conn=Depends(get_db)):
    return document_service.list_documents(conn)


@router.get("/documents/search")
def search(q: str, k: int = 3):
    return policy_retriever.search(get_vector_store(), q, k)
