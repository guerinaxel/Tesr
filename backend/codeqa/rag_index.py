from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import faiss  # type: ignore
import joblib
from sentence_transformers import SentenceTransformer


@dataclass
class RagConfig:
    index_path: Path
    docs_path: Path
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"


class RagIndex:
    def __init__(self, config: RagConfig) -> None:
        self._config = config
        self._model = SentenceTransformer(config.embedding_model_name)
        self._index: faiss.IndexFlatIP | None = None
        self._docs: List[str] = []

    def build_from_texts(self, texts: List[str]) -> None:
        if not texts:
            raise ValueError("No texts provided to build RAG index.")

        embeddings = self._model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )
        dim = embeddings.shape[1]

        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        self._config.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._config.docs_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(self._config.index_path))
        joblib.dump(texts, self._config.docs_path)

        self._index = index
        self._docs = texts

    def load(self) -> None:
        try:
            self._index = faiss.read_index(str(self._config.index_path))
            self._docs = joblib.load(self._config.docs_path)
        except Exception as exc:  # pragma: no cover - defensive path
            raise FileNotFoundError("RAG index or docs file is missing.") from exc

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
