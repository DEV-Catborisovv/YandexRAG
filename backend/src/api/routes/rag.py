import logging
from fastapi import APIRouter, Depends, HTTPException
from src.domain.models import SearchQuery, RAGResponse
from src.application.rag_service import RAGService
from src.api.dependencies import get_rag_service
from src.domain.exceptions import AppException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/search", tags=["search"])

from fastapi.responses import StreamingResponse
import json

@router.post("/", response_model=RAGResponse)
async def ask_question(
    query: SearchQuery,
    service: RAGService = Depends(get_rag_service)
) -> RAGResponse:
    try:
        return await service.ask(query)
    except AppException as e:
        logger.error(f"App error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unhandled error in rag route: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.post("/stream")
async def ask_question_stream(
    query: SearchQuery,
    service: RAGService = Depends(get_rag_service)
):
    try:
        return StreamingResponse(
            service.stream_ask(query),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.exception(f"Unhandled error in rag stream route: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
