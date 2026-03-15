"""
Contract routes: process (trigger workflow), status (poll run state).
Protected by JWT.
"""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.core.doc_id import make_document_id
from app.graph.workflow import run_contract_workflow
from app.services.persistence import get_run
from app.tools.pdf_parser import extract_text_from_bytes

router = APIRouter(prefix="/contract", tags=["contract"])


@router.post("/process")
async def process_contract(
    _user: CurrentUser,
    text: Annotated[
        str | None,
        Form(description="Contract text (optional when file is uploaded). Use when no file."),
    ] = None,
    document_id: Annotated[
        str | None,
        Form(description="Optional correlation id for the run."),
    ] = None,
    file: Annotated[
        UploadFile | None,
        File(description="Contract as PDF or .txt file. If provided, text is optional."),
    ] = None,
) -> dict:
    """
    Process a contract: **upload a file** and/or **provide text**.

    - **File upload:** Send `file` (PDF or .txt). When file is sent, `text` is **optional**.
    - **Text only:** Send form field `text` (no file).
    - **Both:** File is used; `text` is ignored when `file` is present.

    Returns AgentRunResult (trace_id, status, confidence, artifacts, etc.).
    """
    contract_text: str | None = None
    filename: str | None = None
    if file and getattr(file, "filename", None):
        filename = file.filename
        try:
            data = await file.read()
            contract_text = extract_text_from_bytes(data, filename)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        if not contract_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File produced no text.")
    elif text and text.strip():
        contract_text = text.strip()
    if not contract_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload (PDF/txt) or the text form field.",
        )
    doc_id = make_document_id(user_provided=document_id, filename=filename)
    trace_id = str(uuid4())
    try:
        result = run_contract_workflow(contract_text, trace_id=trace_id, document_id=doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow error: {e}",
        ) from e
    return result.model_dump_for_gsheets()


@router.get("/status/{trace_id}")
def contract_status(
    trace_id: str,
    _user: CurrentUser,
) -> dict:
    """
    Fetches the current state of a run from SQLite.
    """
    result = get_run(trace_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No run found for trace_id={trace_id}")
    return result.model_dump_for_gsheets()
