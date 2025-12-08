from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple
from uuid import UUID

from ollama import ChatResponse, chat

from .rag_index import RagConfig, RagIndex
from .models import RagSource


class AnswerNotReadyError(RuntimeError):
    """Raised when the RAG index is not (yet) initialized."""


_rag_index: RagIndex | None = None
_rag_indexes: dict[str, RagIndex] = {}
_rag_sources_cache: dict[str, RagSource] = {}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _warm_cache_enabled() -> bool:
    return _env_flag("RAG_WARM_CACHE_ON_BUILD", False)


def _get_data_dir() -> Path:
    return Path(os.getenv("RAG_DATA_DIR", Path(__file__).resolve().parent / "data"))


def _get_paths_from_env() -> tuple[Path, Path]:
    data_dir = _get_data_dir()
    index_path = Path(os.getenv("RAG_INDEX_PATH", data_dir / "rag_index.faiss"))
    docs_path = Path(os.getenv("RAG_DOCS_PATH", data_dir / "rag_docs.pkl"))
    return index_path, docs_path


def _build_config_from_env() -> RagConfig:
    index_path, docs_path = _get_paths_from_env()
    embedding_model_name = os.getenv(
        "RAG_EMBED_MODEL", RagConfig.embedding_model_name
    )
    fallback_embedding_model_name = os.getenv(
        "RAG_EMBED_MODEL_FALLBACK", RagConfig.fallback_embedding_model_name
    )
    persist_embeddings = _env_flag("RAG_PERSIST_EMBEDDINGS", True)
    index_version = os.getenv("RAG_INDEX_VERSION", RagConfig.index_version)
    whoosh_dir_env = os.getenv("RAG_WHOOSH_DIR")
    whoosh_dir = Path(whoosh_dir_env) if whoosh_dir_env else docs_path.parent / "whoosh_index"
    return RagConfig(
        index_path=index_path,
        docs_path=docs_path,
        whoosh_index_dir=whoosh_dir,
        embedding_model_name=embedding_model_name,
        fallback_embedding_model_name=fallback_embedding_model_name,
        persist_embeddings=persist_embeddings,
        index_version=index_version,
    )


def get_rag_index() -> RagIndex:
    global _rag_index
    if _rag_index is None:
        config = _build_config_from_env()
        rag_index = RagIndex(config)
        rag_index.load()
        _rag_index = rag_index
    return _rag_index


def _rag_sources_base_dir() -> Path:
    return Path(os.getenv("RAG_SOURCES_DIR", _get_data_dir() / "rag_sources"))


def _config_for_source(source: RagSource) -> RagConfig:
    base_dir = Path(source.path)
    index_path = base_dir / "rag_index.faiss"
    docs_path = base_dir / "docs.pkl"
    embeddings_path = base_dir / "embeddings.pkl"
    metadata_path = base_dir / "index_meta.json"
    whoosh_dir = base_dir / "whoosh_index"
    return RagConfig(
        index_path=index_path,
        docs_path=docs_path,
        whoosh_index_dir=whoosh_dir,
        embeddings_path=embeddings_path,
        metadata_path=metadata_path,
        embedding_model_name=os.getenv("RAG_EMBED_MODEL", RagConfig.embedding_model_name),
        fallback_embedding_model_name=os.getenv(
            "RAG_EMBED_MODEL_FALLBACK", RagConfig.fallback_embedding_model_name
        ),
        persist_embeddings=_env_flag("RAG_PERSIST_EMBEDDINGS", True),
        index_version=os.getenv("RAG_INDEX_VERSION", RagConfig.index_version),
    )


def _load_rag_source(source: RagSource) -> RagIndex:
    source_id = str(source.id)
    cached = _rag_indexes.get(source_id)
    if cached is not None:
        return cached

    config = _config_for_source(source)
    index = RagIndex(config)
    index.load()
    _rag_indexes[source_id] = index
    _rag_sources_cache[source_id] = source
    return index


def drop_cached_source(source_id: str) -> None:
    _rag_indexes.pop(source_id, None)
    _rag_sources_cache.pop(source_id, None)


def warm_cached_source(source: RagSource, *, index: RagIndex | None = None) -> RagIndex:
    source_id = str(source.id)
    rag_index = index or _load_rag_source(source)
    _rag_indexes[source_id] = rag_index
    _rag_sources_cache[source_id] = source
    return rag_index


def answer_question(
    question: str,
    top_k: int = 5,
    fusion_weight: float = 0.5,
    system_prompt: str | None = None,
    custom_prompt: str | None = None,
    sources: list[UUID] | None = None,
) -> Tuple[str, Dict]:
    prepared = _prepare_chat(
        question, top_k, fusion_weight, system_prompt, custom_prompt, sources=sources
    )
    try:
        response: ChatResponse = _run_chat_sync(prepared)
    except Exception:
        if prepared.fallback_model is None:
            raise
        fallback_prepared = PreparedChat(
            user_content=prepared.user_content,
            system_prompt=prepared.system_prompt,
            contexts=prepared.contexts,
            model_name=prepared.fallback_model,
            fallback_model=None,
        )
        response = _run_chat_sync(fallback_prepared)

    answer = response.message.content
    meta = _build_meta(prepared.contexts)
    return answer, meta


def stream_answer(
    question: str,
    top_k: int = 5,
    fusion_weight: float = 0.5,
    system_prompt: str | None = None,
    custom_prompt: str | None = None,
    sources: list[UUID] | None = None,
) -> tuple[Dict, Iterable[str]]:
    prepared = _prepare_chat(
        question, top_k, fusion_weight, system_prompt, custom_prompt, sources=sources
    )
    meta = _build_meta(prepared.contexts)

    def _tokens_for_model(model_name: str) -> Iterable[str]:
        stream = chat(
            model=model_name,
            messages=[
                {"role": "system", "content": prepared.system_prompt},
                {"role": "user", "content": prepared.user_content},
            ],
            stream=True,
            options={"num_ctx": 2048, "use_gpu": True},
        )
        for chunk in stream:
            message = getattr(chunk, "message", None)
            if message is None:
                continue
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", "")
            )
            if content:
                yield str(content)

    def _generator() -> Iterable[str]:
        try:
            yield from _tokens_for_model(prepared.model_name)
        except Exception:
            if prepared.fallback_model is None:
                raise
            yield from _tokens_for_model(prepared.fallback_model)

    return meta, _generator()


@dataclass(frozen=True)
class PreparedChat:
    user_content: str
    system_prompt: str
    contexts: list[tuple[str, float, str, str]]
    model_name: str
    fallback_model: str | None


def _build_meta(contexts: list[tuple[str, float, str, str]]) -> Dict:
    unique_sources: dict[str, str] = {}
    for _snippet, _score, source_id, source_name in contexts:
        unique_sources[source_id] = source_name

    return {
        "num_contexts": len(contexts),
        "sources": list(unique_sources.keys()),
        "source_names": list(unique_sources.values()),
        "contexts": [
            {
                "rank": i + 1,
                "score": score,
                "snippet": snippet,
                "source_id": source_id,
                "source_name": source_name,
            }
            for i, (snippet, score, source_id, source_name) in enumerate(contexts)
        ],
    }


def _gather_contexts(
    question: str,
    top_k: int,
    fusion_weight: float,
    sources: list[UUID] | None,
) -> list[tuple[str, float, str, str]]:
    if not sources:
        raise AnswerNotReadyError("No RAG sources selected.")

    rag_sources = list(RagSource.objects.filter(id__in=sources))
    if not rag_sources:
        raise AnswerNotReadyError("No matching RAG sources found.")

    combined: list[tuple[str, float, str, str]] = []
    for rag_source in rag_sources:
        index = _load_rag_source(rag_source)
        hits = index.search(question, k=top_k, fusion_weight=fusion_weight)
        if not hits:
            continue
        max_score = max(score for _, score in hits) or 1.0
        for snippet, score in hits:
            normalized = score / max_score if max_score else score
            combined.append((snippet, normalized, str(rag_source.id), rag_source.name))

    if not combined:
        raise AnswerNotReadyError("RAG index is empty or not initialized.")

    combined.sort(key=lambda item: item[1], reverse=True)
    return combined[:top_k]


def _prepare_chat(
    question: str,
    top_k: int,
    fusion_weight: float,
    system_prompt: str | None,
    custom_prompt: str | None,
    *,
    sources: list[UUID] | None,
) -> PreparedChat:
    contexts = _gather_contexts(question, top_k, fusion_weight, sources)

    system_prompt_mapping = {
        "code expert": " ".join(
            [
                "You are a senior Python/Django expert assistant with access to a retrieval system that can search",
                " the entire codebase.",
                "If the provided context is not sufficient to answer the question, do not claim you cannot verify it.",
                "Instead, explicitly request more context by stating:",
                "request: more_context needed: <describe what you need>",
                "Only use this format when the available context is insufficient.",
                "When enough context is provided, answer with a complete, expert-level Django/Python explanation:",
                "- Reference functions, classes, files, and logic accurately.",
                "- Do not hallucinate code, but you may infer relationships that are normal within Django projects.",
                "- Prefer architecture-level reasoning (views → serializers → models → services).",
                "- Use Django 5 and DRF best practices for all explanations.",
                "- Always give precise, actionable, senior-level insight.",
                "Your behavior model:",
                "- If context is insufficient → ask the retriever for specific missing parts.",
                "- If context is sufficient → answer fully.",
                "- Never force the user to ask a second time.",
                "- Never stop at “I cannot verify this”.",
                "- You may request context repeatedly until you have enough to answer confidently.",
                "Use this protocol for every question.",
            ]
        ),
        "document expert": " ".join(
            [
                "You are a technical documentation expert.",
                "Provide clear, concise, and well-structured explanations based solely on the supplied context.",
                "When code is referenced, summarize behavior in documentation style.",
                "Call out missing details that may require more context.",
                "Always keep responses actionable, accurate, and easy to follow for engineering teams.",
            ]
        ),
    }

    prompt_choice = system_prompt or "code expert"
    if prompt_choice == "custom":
        if not custom_prompt or not custom_prompt.strip():
            raise ValueError("custom_prompt is required when system_prompt is 'custom'")
        selected_prompt = custom_prompt.strip()
    else:
        selected_prompt = system_prompt_mapping.get(prompt_choice, system_prompt_mapping["code expert"])

    context_text = "\n\n".join(
        f"[Doc {i+1}, score={score:.3f}, source={source_name}]\n{snippet}"
        for i, (snippet, score, _, source_name) in enumerate(contexts)
    )

    user_content = (
        f"Question:\n{question}\n\n"
        f"Relevant code context:\n{context_text}\n\n"
        "Answer in clear, concise terms."
    )

    model_name, fallback_model = _select_model(prompt_choice)
    return PreparedChat(
        user_content=user_content,
        system_prompt=selected_prompt,
        contexts=contexts,
        model_name=model_name,
        fallback_model=fallback_model,
    )


def _select_model(choice: str) -> tuple[str, str | None]:
    if choice == "document expert":
        primary = os.getenv("OLLAMA_DOC_MODEL_NAME", "qwen2.5vl:7b")
        fallback = os.getenv("OLLAMA_DOC_MODEL_FALLBACK", "qwen2.5-vl:3b")
        return primary, fallback
    return os.getenv("OLLAMA_MODEL_NAME", "llama3.1:8b"), None


def _run_chat_sync(prepared: PreparedChat) -> ChatResponse:
    return chat(
        model=prepared.model_name,
        messages=[
            {"role": "system", "content": prepared.system_prompt},
            {"role": "user", "content": prepared.user_content},
        ],
        options={
            "num_ctx": 2048,
            "use_gpu": True,
        },
    )

