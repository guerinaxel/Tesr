from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

from ollama import ChatResponse, chat

from .rag_index import RagConfig, RagIndex


class AnswerNotReadyError(RuntimeError):
    """Raised when the RAG index is not (yet) initialized."""


_rag_index: RagIndex | None = None


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
    whoosh_dir_env = os.getenv("RAG_WHOOSH_DIR")
    whoosh_dir = Path(whoosh_dir_env) if whoosh_dir_env else docs_path.parent / "whoosh_index"
    return RagConfig(
        index_path=index_path,
        docs_path=docs_path,
        whoosh_index_dir=whoosh_dir,
        embedding_model_name=embedding_model_name,
        fallback_embedding_model_name=fallback_embedding_model_name,
    )


def get_rag_index() -> RagIndex:
    global _rag_index
    if _rag_index is None:
        config = _build_config_from_env()
        rag_index = RagIndex(config)
        rag_index.load()
        _rag_index = rag_index
    return _rag_index


def answer_question(
    question: str,
    top_k: int = 5,
    fusion_weight: float = 0.5,
    system_prompt: str | None = None,
    custom_prompt: str | None = None,
) -> Tuple[str, Dict]:
    prepared = _prepare_chat(question, top_k, fusion_weight, system_prompt, custom_prompt)
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
) -> tuple[Dict, Iterable[str]]:
    prepared = _prepare_chat(question, top_k, fusion_weight, system_prompt, custom_prompt)
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
    contexts: list[tuple[str, float]]
    model_name: str
    fallback_model: str | None


def _build_meta(contexts: list[tuple[str, float]]) -> Dict:
    return {
        "num_contexts": len(contexts),
        "contexts": [
            {"rank": i + 1, "score": score, "snippet": snippet}
            for i, (snippet, score) in enumerate(contexts)
        ],
    }


def _prepare_chat(
    question: str,
    top_k: int,
    fusion_weight: float,
    system_prompt: str | None,
    custom_prompt: str | None,
) -> PreparedChat:
    index = get_rag_index()
    contexts = index.search(question, k=top_k, fusion_weight=fusion_weight)
    if not contexts:
        raise AnswerNotReadyError("RAG index is empty or not initialized.")

    system_prompt_mapping = {
        "code expert": " ".join(
            [
                "You are a senior Python/Django expert assistant with access to a retrieval system that can search",
                " the entire codebase.",
                "If the provided context is not sufficient to answer the question, DO NOT tell the user that you cannot",
                " verify it.",
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
        f"[Doc {i+1}, score={score:.3f}]\n{snippet}"
        for i, (snippet, score) in enumerate(contexts)
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

