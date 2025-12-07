from __future__ import annotations

from asgiref.sync import sync_to_async
from typing import Any, Iterable
from uuid import UUID
import inspect

from .. import rag_service
from .errors import RagAnswerNotReadyError


def _supports_fusion_weight(callable_obj) -> bool:
    signature = inspect.signature(callable_obj)
    return "fusion_weight" in signature.parameters or any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
    )


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
        kwargs = {
            "question": question,
            "top_k": top_k,
            "system_prompt": system_prompt,
            "custom_prompt": custom_prompt,
            "sources": sources,
        }

        if _supports_fusion_weight(rag_service.answer_question):
            kwargs["fusion_weight"] = fusion_weight

        try:
            answer, meta = rag_service.answer_question(**kwargs)
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
        kwargs = {
            "question": question,
            "top_k": top_k,
            "system_prompt": system_prompt,
            "custom_prompt": custom_prompt,
            "sources": sources,
        }

        if _supports_fusion_weight(rag_service.stream_answer):
            kwargs["fusion_weight"] = fusion_weight

        try:
            return rag_service.stream_answer(**kwargs)
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
