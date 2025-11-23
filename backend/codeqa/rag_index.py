from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss  # type: ignore
import joblib
from sentence_transformers import SentenceTransformer


@dataclass
class RagConfig:
    index_path: Path
    docs_path: Path
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_model_kwargs: Dict[str, Any] | None = None


class RagIndex:
    def __init__(self, config: RagConfig) -> None:
        self._config = config
        model_kwargs: Dict[str, Any] = config.embedding_model_kwargs or {}
        if "nomic" in config.embedding_model_name and "trust_remote_code" not in model_kwargs:
            model_kwargs["trust_remote_code"] = True

        self._model = SentenceTransformer(config.embedding_model_name, **model_kwargs)

        # Not all SentenceTransformer-compatible models expose a helper to report their
        # embedding dimension (e.g., the test FakeModel). Fall back to None and rely on
        # runtime encodes if unavailable.
        get_dim = getattr(self._model, "get_sentence_embedding_dimension", None)
        self._embedding_dim: int | None = get_dim() if callable(get_dim) else None
        self._index: faiss.IndexFlatIP | None = None
        self._docs: List[str] = []

    def _ensure_data_dirs(self) -> None:
        self._config.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._config.docs_path.parent.mkdir(parents=True, exist_ok=True)

    def _save_index_and_docs(self, index: faiss.IndexFlatIP, docs: List[str]) -> None:
        self._ensure_data_dirs()
        faiss.write_index(index, str(self._config.index_path))
        joblib.dump(docs, self._config.docs_path)

    def _rebuild_index_from_docs(self, docs: List[str]) -> faiss.IndexFlatIP:
        embeddings = self._model.encode(
            docs, convert_to_numpy=True, normalize_embeddings=True
        )
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        self._save_index_and_docs(index, docs)
        return index

    def build_from_texts(self, texts: List[str]) -> None:
        if not texts:
            raise ValueError("No texts provided to build RAG index.")

        embeddings = self._model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )
        dim = embeddings.shape[1]

        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        self._save_index_and_docs(index, texts)

        self._index = index
        self._docs = texts

    def load(self) -> None:
        try:
            docs: List[str] = joblib.load(self._config.docs_path)
            index = faiss.read_index(str(self._config.index_path))
        except Exception as exc:  # pragma: no cover - defensive path
            raise FileNotFoundError("RAG index or docs file is missing.") from exc

        if self._embedding_dim is not None and index.d != self._embedding_dim:
            index = self._rebuild_index_from_docs(docs)

        self._index = index
        self._docs = docs

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        if self._index is None or not self._docs:
            raise RuntimeError("RAG index not loaded. Call load() first.")

        query_emb = self._model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        )
        scores, indices = self._index.search(query_emb, k)

        results: List[Tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if 0 <= idx < len(self._docs):
                results.append((self._docs[idx], float(score)))
        return results
