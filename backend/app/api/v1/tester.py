"""Tweet tester API (PROJECT.md §19): paste text → scored breakdown + why."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.pipeline.tester import analyze
from app.providers.factory import get_embedding_provider
from app.schemas.api import TesterRequest, TesterResponse

router = APIRouter(prefix="/tester", tags=["tester"])


@router.post("", response_model=TesterResponse)
async def test_text(
    payload: TesterRequest, session: AsyncSession = Depends(get_session)
) -> TesterResponse:
    result = await analyze(session, payload.text, get_embedding_provider())
    return TesterResponse(**result.__dict__)
