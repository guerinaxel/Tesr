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


def answer_question(question: str, top_k: int = 5) -> Tuple[str, Dict]:
    index = get_rag_index()
    contexts = index.search(question, k=top_k)

    if not contexts:
        raise AnswerNotReadyError("RAG index is empty or not initialized.")

    system_prompt = (
        # # "You are an assistant that answers questions about this codebase. "
        # # "Use ONLY the provided context when you are unsure. "
        # # "If the answer is not in the context, say you don't know."
        # "You are a senior software engineer acting as a codebase assistant."
        # "Your only source of truth is the code snippets and project context provided to you in the conversation."
        # "Follow these rules:"
        # "1. Base every answer strictly on the retrieved code context."
        # "2. If information is missing or unclear, say that you cannot verify it."
        # "3. When the user asks about behavior, APIs, or architecture, cite the specific lines or files from the context in natural language (do NOT fabricate)."
        # "4. Avoid assumptions, speculations, or inferred code that does not appear in the provided context."
        # "5. When code is unclear or ambiguous, explain the ambiguity explicitly."
        # "6. Summarize cross-file relationships only if they appear in the retrieved context."
        # "7. Provide explanations step-by-step and highlight important logic paths."
        # "8. Suggest improvements only when supported by the context."
        # "9. Never invent classes, functions, variables, or configurations that do not exist in the supplied context."
        # "10. If the user asks for something outside the provided context, warn them and answer only what can be verified."
        # "Your goal is to give accurate, safe, and non-hallucinated explanations about the codebase using only the information retrieved for this query."
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
    )

    context_text = "\n\n".join(
        f"[Doc {i+1}, score={score:.3f}]\n{snippet}"
        for i, (snippet, score) in enumerate(contexts)
    )

    user_content = (
        f"Question:\n{question}\n\n"
        f"Relevant code context:\n{context_text}\n\n"
        "Answer in clear, concise terms."
    )

    model_name = os.getenv("OLLAMA_MODEL_NAME", "llama3.1:8b")

    response: ChatResponse = chat(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        options={
            "num_ctx": 2048,
            "use_gpu": True
        }
    )

    answer = response.message.content
    meta = {
        "num_contexts": len(contexts),
        "contexts": [
            {"rank": i + 1, "score": score, "snippet": snippet}
            for i, (snippet, score) in enumerate(contexts)
        ],
    }
    return answer, meta
