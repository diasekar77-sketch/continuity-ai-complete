from fastapi import APIRouter, Depends, HTTPException

from app.database.connection import get_db
from app.database.schemas import AssistantQuery
from app.llm.client import get_extractor, get_llm
from app.rag.vector_store import get_vector_store
from app.services import assistant_service

router = APIRouter()


@router.post("/assistant/query")
def query(body: AssistantQuery, conn=Depends(get_db)):
    try:
        return assistant_service.answer_question(conn, get_vector_store(), body.case_id, body.question,
                                                 llm=get_llm(), extractor=get_extractor())
    except LookupError as e:
        raise HTTPException(404, str(e))
