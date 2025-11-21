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
        "You are an assistant that answers questions about this codebase. "
        "Use ONLY the provided context when you are unsure. "
        "If the answer is not in the context, say you don't know."
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

    model_name = os.getenv("OLLAMA_MODEL_NAME", "llama3.1")

    response: ChatResponse = chat(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
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
