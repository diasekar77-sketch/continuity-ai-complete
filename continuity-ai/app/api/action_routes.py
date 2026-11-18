from fastapi import APIRouter, Depends, HTTPException

from app.database.connection import get_db
from app.database.schemas import ActionStatus, ChecklistUpdate, NewAction
from app.services import action_service

router = APIRouter()


def _run(fn, *args):
    try:
        return fn(*args)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/cases/{case_id}/actions")
def actions(case_id: int, conn=Depends(get_db)):
    return action_service.list_actions(conn, case_id)


@router.post("/cases/{case_id}/actions")
def add_action(case_id: int, body: NewAction, conn=Depends(get_db)):
    return _run(action_service.add_manual_action, conn, case_id, body.description, body.by, body.assigned_agent)


@router.post("/actions/{action_id}/status")
def action_status(action_id: int, body: ActionStatus, conn=Depends(get_db)):
    return _run(action_service.set_action_status, conn, action_id, body.done, body.by)


@router.post("/cases/{case_id}/checklist")
def checklist(case_id: int, body: ChecklistUpdate, conn=Depends(get_db)):
    return _run(action_service.set_checklist, conn, case_id, body.item, body.checked, body.by)


@router.get("/cases/{case_id}/events")
def events(case_id: int, conn=Depends(get_db)):
    return action_service.get_events(conn, case_id)
