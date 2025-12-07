from __future__ import annotations

from asgiref.sync import sync_to_async
from typing import Any, Iterable
from uuid import UUID

from .. import rag_service
from .errors import RagAnswerNotReadyError


class RagQueryService:
    """Coordinates FAISS-backed retrieval and LLM interactions."""

    def answer(
        self,
        *,
        question: str,
        top_k: int,
        fusion_weight: float,
        system_prompt: str,
        custom_prompt: str | None,
        sources: list[UUID],
    ) -> tuple[str, dict[str, Any]]:
        try:
            answer, meta = rag_service.answer_question(
                question=question,
                top_k=top_k,
                fusion_weight=fusion_weight,
                system_prompt=system_prompt,
                custom_prompt=custom_prompt,
                sources=sources,
            )
        except rag_service.AnswerNotReadyError as exc:
            raise RagAnswerNotReadyError(str(exc)) from exc
        return answer, meta

    def stream(
        self,
        *,
        question: str,
        top_k: int,
        fusion_weight: float,
        system_prompt: str,
        custom_prompt: str | None,
        sources: list[UUID],
    ) -> tuple[dict[str, Any], Iterable[str]]:
        try:
            return rag_service.stream_answer(
                question=question,
                top_k=top_k,
                fusion_weight=fusion_weight,
                system_prompt=system_prompt,
                custom_prompt=custom_prompt,
                sources=sources,
            )
        except rag_service.AnswerNotReadyError as exc:
            raise RagAnswerNotReadyError(str(exc)) from exc

    async def answer_async(
        self,
        *,
        question: str,
        top_k: int,
        fusion_weight: float,
        system_prompt: str,
        custom_prompt: str | None,
        sources: list[UUID],
    ) -> tuple[str, dict[str, Any]]:
        return await sync_to_async(self.answer)(
            question=question,
            top_k=top_k,
            fusion_weight=fusion_weight,
            system_prompt=system_prompt,
            custom_prompt=custom_prompt,
            sources=sources,
        )

    async def stream_async(
        self,
        *,
        question: str,
        top_k: int,
        fusion_weight: float,
        system_prompt: str,
        custom_prompt: str | None,
        sources: list[UUID],
    ) -> tuple[dict[str, Any], Iterable[str]]:
        return await sync_to_async(self.stream)(
            question=question,
            top_k=top_k,
            fusion_weight=fusion_weight,
            system_prompt=system_prompt,
            custom_prompt=custom_prompt,
            sources=sources,
        )
