from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

from ollama import ChatResponse, chat

from .rag_index import RagConfig, RagIndex


class AnswerNotReadyError(RuntimeError):
    """Raised when the RAG index is not (yet) initialized."""


_rag_index: RagIndex | None = None


def _get_paths_from_env() -> tuple[Path, Path]:
    data_dir = Path(
        os.getenv("RAG_DATA_DIR", Path(__file__).resolve().parent / "data")
    )
    index_path = Path(os.getenv("RAG_INDEX_PATH", data_dir / "rag_index.faiss"))
    docs_path = Path(os.getenv("RAG_DOCS_PATH", data_dir / "rag_docs.pkl"))
    return index_path, docs_path


def get_rag_index() -> RagIndex:
    global _rag_index
    if _rag_index is None:
        index_path, docs_path = _get_paths_from_env()
        config = RagConfig(index_path=index_path, docs_path=docs_path)
        rag_index = RagIndex(config)
        rag_index.load()
        _rag_index = rag_index
    return _rag_index


def answer_question(
    question: str,
    top_k: int = 5,
    system_prompt: str | None = None,
    custom_prompt: str | None = None,
) -> Tuple[str, Dict]:
    index = get_rag_index()
    contexts = index.search(question, k=top_k)

    if not contexts:
        raise AnswerNotReadyError("RAG index is empty or not initialized.")

    system_prompt_mapping = {
        "code expert": (
            "You are a senior Python/Django expert assistant with access to a retrieval system that can search the entire codebase."
            "If the provided context is not sufficient to answer the question, DO NOT tell the user that you cannot verify it."
            "Instead, explicitly request more context by stating:"
            "request: more_context needed: <describe what you need>"
            "Only use this format when the available context is insufficient."
            "When enough context is provided, answer with a complete, expert-level Django/Python explanation:"
            "- Reference functions, classes, files, and logic accurately."
            "- Do not hallucinate code, but you may infer relationships that are normal within Django projects."
            "- Prefer architecture-level reasoning (views → serializers → models → services)."
            "- Use Django 5 and DRF best practices for all explanations."
            "- Always give precise, actionable, senior-level insight."
            "Your behavior model:"
            "- If context is insufficient → ask the retriever for specific missing parts."
            "- If context is sufficient → answer fully."
            "- Never force the user to ask a second time."
            "- Never stop at “I cannot verify this”."
            "- You may request context repeatedly until you have enough to answer confidently."
            "Use this protocol for every question."
        ),
        "document expert": (
            "You are a technical documentation expert."
            "Provide clear, concise, and well-structured explanations based solely on the supplied context."
            "When code is referenced, summarize behavior in documentation style and call out missing details that may require more context."
            "Always keep responses actionable, accurate, and easy to follow for engineering teams."
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

    def _select_model(choice: str) -> tuple[str, str | None]:
        if choice == "document expert":
            primary = os.getenv("OLLAMA_DOC_MODEL_NAME", "qwen2.5vl:7b")
            fallback = os.getenv("OLLAMA_DOC_MODEL_FALLBACK", "qwen2.5-vl:3b")
            return primary, fallback
        return os.getenv("OLLAMA_MODEL_NAME", "llama3.1:8b"), None

    def _run_chat(model: str) -> ChatResponse:
        return chat(
            model=model,
            messages=[
                {"role": "system", "content": selected_prompt},
                {"role": "user", "content": user_content},
            ],
            options={
                "num_ctx": 2048,
                "use_gpu": True,
            },
        )

    model_name, fallback_model = _select_model(prompt_choice)

    try:
        response: ChatResponse = _run_chat(model_name)
    except Exception:
        if fallback_model is None:
            raise
        response = _run_chat(fallback_model)

    answer = response.message.content
    meta = {
        "num_contexts": len(contexts),
        "contexts": [
            {"rank": i + 1, "score": score, "snippet": snippet}
            for i, (snippet, score) in enumerate(contexts)
        ],
    }
    return answer, meta
