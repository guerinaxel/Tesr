from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Iterable

from django.http import HttpRequest, StreamingHttpResponse
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import rag_service
from .document_service import (
    Document,
    answer_question_from_documents,
    categorize_document,
    summarize_content,
)
from .build_runner import BuildInProgressError, get_progress, start_build
from .rag_state import get_default_root, load_last_root, save_last_root
from .models import Message, Topic
from .serializers import (
    BuildRagRequestSerializer,
    CodeQuestionSerializer,
    DocumentAnalysisSerializer,
    TopicCreateSerializer,
)


def _parse_pagination(request: HttpRequest, *, default_limit: int = 20, max_limit: int = 50) -> tuple[int, int]:
    try:
        limit = int(request.query_params.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit

    try:
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    limit = max(0, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset


def _paginate_queryset(qs, *, limit: int, offset: int) -> tuple[list, int | None]:
    if limit == 0:
        has_more = qs.count() > offset
        return [], offset if has_more else None

    window = list(qs[offset : offset + limit + 1])
    has_more = len(window) > limit
    return window[:limit], offset + limit if has_more else None


class CodeQAView(APIView):
    """POST endpoint for code Q&A."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = CodeQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question: str = serializer.validated_data["question"]
        top_k: int = serializer.validated_data["top_k"]
        fusion_weight: float = serializer.validated_data.get("fusion_weight", 0.5)
        system_prompt: str = serializer.validated_data["system_prompt"]
        custom_prompt: str | None = serializer.validated_data.get("custom_prompt")
        typo_prompt: str | None = serializer.validated_data.get("custom_pront")
        topic_id: int | None = serializer.validated_data.get("topic_id")

        topic: Topic | None = None
        if topic_id is not None:
            topic = Topic.objects.filter(id=topic_id).first()
            if topic is None:
                return Response(
                    {"detail": "Topic not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        answer_kwargs: dict[str, Any] = {
            "question": question,
            "top_k": top_k,
            "system_prompt": system_prompt,
            "custom_prompt": custom_prompt or typo_prompt,
        }

        signature = inspect.signature(rag_service.answer_question)
        if "fusion_weight" in signature.parameters or any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        ):
            answer_kwargs["fusion_weight"] = fusion_weight

        try:
            answer, meta = rag_service.answer_question(**answer_kwargs)
        except rag_service.AnswerNotReadyError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {"detail": "Internal server error.", "errors": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if topic is not None:
            Message.objects.bulk_create(
                [
                    Message(topic=topic, role=Message.ROLE_USER, content=question),
                    Message(topic=topic, role=Message.ROLE_ASSISTANT, content=answer),
                ]
            )

        return Response({"answer": answer, "meta": meta}, status=status.HTTP_200_OK)


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


class CodeQAStreamView(APIView):
    """Stream LLM responses over SSE for chat-like UX."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> StreamingHttpResponse | Response:
        serializer = CodeQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question: str = serializer.validated_data["question"]
        top_k: int = serializer.validated_data["top_k"]
        fusion_weight: float = serializer.validated_data.get("fusion_weight", 0.5)
        system_prompt: str = serializer.validated_data["system_prompt"]
        custom_prompt: str | None = serializer.validated_data.get("custom_prompt")
        typo_prompt: str | None = serializer.validated_data.get("custom_pront")
        topic_id: int | None = serializer.validated_data.get("topic_id")

        topic: Topic | None = None
        if topic_id is not None:
            topic = Topic.objects.filter(id=topic_id).first()
            if topic is None:
                return Response(
                    {"detail": "Topic not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            meta, token_stream = rag_service.stream_answer(
                question=question,
                top_k=top_k,
                fusion_weight=fusion_weight,
                system_prompt=system_prompt,
                custom_prompt=custom_prompt or typo_prompt,
            )
        except rag_service.AnswerNotReadyError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            return Response(
                {"detail": "Internal server error.", "errors": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        def event_stream() -> Iterable[str]:
            yield _format_sse({"event": "meta", "data": meta})
            answer_parts: list[str] = []

            try:
                for token in token_stream:
                    answer_parts.append(token)
                    yield _format_sse({"event": "token", "data": token})
            except Exception as exc:  # pragma: no cover - streaming failure
                yield _format_sse({"event": "error", "data": str(exc)})
                return

            final_answer = "".join(answer_parts).strip()
            if topic is not None and final_answer:
                Message.objects.bulk_create(
                    [
                        Message(topic=topic, role=Message.ROLE_USER, content=question),
                        Message(topic=topic, role=Message.ROLE_ASSISTANT, content=final_answer),
                    ]
                )

            yield _format_sse({"event": "done", "data": {"answer": final_answer, "meta": meta}})

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class TopicListView(APIView):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        limit, offset = _parse_pagination(request)
        topics = (
            Topic.objects.annotate(message_count=Count("messages"))
            .order_by("-created_at", "-id")
            .all()
        )

        paginated = list(topics[offset : offset + limit + 1]) if limit else []
        has_more = len(paginated) > limit if limit else topics.count() > offset
        topic_payload = paginated[:limit] if limit else []
        next_offset = offset + limit if has_more and limit else None

        return Response(
            {
                "topics": [
                    {"id": topic.id, "name": topic.name, "message_count": topic.message_count}
                    for topic in topic_payload
                ],
                "next_offset": next_offset,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = TopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic = Topic.objects.create(name=serializer.validated_data["name"])
        return Response(
            {
                "id": topic.id,
                "name": topic.name,
                "message_count": 0,
                "messages": [],
                "next_offset": None,
            },
            status=status.HTTP_201_CREATED,
        )


class TopicDetailView(APIView):
    def get(self, request: HttpRequest, topic_id: int, *args: Any, **kwargs: Any) -> Response:
        topic = get_object_or_404(Topic.objects.all(), id=topic_id)
        limit, offset = _parse_pagination(request)

        messages_qs = topic.messages.order_by("created_at", "id")
        message_count = messages_qs.count()

        if limit == 0:
            messages_payload: list[Message] = []
            has_more = message_count > offset
        else:
            messages_slice = list(messages_qs[offset : offset + limit + 1])
            has_more = len(messages_slice) > limit
            messages_payload = messages_slice[:limit]

        next_offset = offset + limit if has_more and limit else None

        return Response(
            {
                "id": topic.id,
                "name": topic.name,
                "message_count": message_count,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages_payload
                ],
                "next_offset": next_offset,
            },
            status=status.HTTP_200_OK,
        )


class SearchView(APIView):
    """Search topics, questions and answers."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        query = (request.query_params.get("q") or "").strip()
        limit, _ = _parse_pagination(request, default_limit=5, max_limit=20)
        topics_offset = int(request.query_params.get("topics_offset", 0) or 0)
        questions_offset = int(request.query_params.get("questions_offset", 0) or 0)
        answers_offset = int(request.query_params.get("answers_offset", 0) or 0)

        if not query:
            empty_payload = {"items": [], "next_offset": None}
            return Response(
                {"topics": empty_payload, "questions": empty_payload, "answers": empty_payload},
                status=status.HTTP_200_OK,
            )

        topics = (
            Topic.objects.annotate(message_count=Count("messages"))
            .filter(name__icontains=query)
            .order_by("-created_at", "-id")
        )
        topic_items, topics_next = _paginate_queryset(
            topics, limit=limit, offset=max(0, topics_offset)
        )

        questions = (
            Message.objects.select_related("topic")
            .filter(role=Message.ROLE_USER)
            .filter(Q(content__icontains=query) | Q(topic__name__icontains=query))
        )
        question_items, questions_next = _paginate_queryset(
            questions, limit=limit, offset=max(0, questions_offset)
        )

        answers = (
            Message.objects.select_related("topic")
            .filter(role=Message.ROLE_ASSISTANT)
            .filter(Q(content__icontains=query) | Q(topic__name__icontains=query))
        )
        answer_items, answers_next = _paginate_queryset(
            answers, limit=limit, offset=max(0, answers_offset)
        )

        return Response(
            {
                "topics": {
                    "items": [
                        {
                            "id": topic.id,
                            "name": topic.name,
                            "message_count": topic.message_count,
                        }
                        for topic in topic_items
                    ],
                    "next_offset": topics_next,
                },
                "questions": {
                    "items": [
                        {
                            "id": message.id,
                            "topic_id": message.topic_id,
                            "topic_name": message.topic.name,
                            "content": message.content,
                        }
                        for message in question_items
                    ],
                    "next_offset": questions_next,
                },
                "answers": {
                    "items": [
                        {
                            "id": message.id,
                            "topic_id": message.topic_id,
                            "topic_name": message.topic.name,
                            "content": message.content,
                        }
                        for message in answer_items
                    ],
                    "next_offset": answers_next,
                },
            },
            status=status.HTTP_200_OK,
        )


class DocumentAnalysisView(APIView):
    """Summarize, categorize, and answer questions about provided documents."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = DocumentAnalysisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        documents = [
            Document(name=doc_data["name"], content=doc_data["content"])
            for doc_data in serializer.validated_data["documents"]
        ]
        question: str = serializer.validated_data.get("question") or ""

        summaries = [
            {"name": doc.name, "summary": summarize_content(doc.content)}
            for doc in documents
        ]
        categories = [
            {"name": doc.name, "category": categorize_document(doc.name, doc.content)}
            for doc in documents
        ]

        response_payload: dict[str, Any] = {
            "summaries": summaries,
            "categories": categories,
        }

        if question:
            response_payload["answer"] = answer_question_from_documents(question, documents)

        return Response(response_payload, status=status.HTTP_200_OK)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class BuildRagIndexView(APIView):
    """Trigger rebuilding the RAG index via the management command."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response(
            {"root": load_last_root(), "progress": get_progress().to_dict()},
            status=status.HTTP_200_OK,
        )

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = BuildRagRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_root = serializer.validated_data.get("root") or None
        root = raw_root.strip() if isinstance(raw_root, str) else None
        resolved_root = Path(root or get_default_root()).resolve()
        save_last_root(str(resolved_root))

        try:
            progress = start_build(resolved_root)
        except BuildInProgressError as exc:
            return Response(
                {"detail": str(exc), "progress": get_progress().to_dict()},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:  # pragma: no cover - defensive path
            return Response(
                {"detail": "Failed to build RAG index."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "detail": "RAG index build triggered.",
                "root": str(resolved_root),
                "progress": progress.to_dict(),
            },
            status=status.HTTP_200_OK,
        )
