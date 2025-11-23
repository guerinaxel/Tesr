from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss  # type: ignore
import joblib
from sentence_transformers import SentenceTransformer

from .keyword_index import KeywordIndex


@dataclass
class RagConfig:
    index_path: Path
    docs_path: Path
    tokenized_docs_path: Path | None = None
    keyword_index_path: Path | None = None
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_model_kwargs: Dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.tokenized_docs_path is None:
            self.tokenized_docs_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_tokens{self.docs_path.suffix}"
            )
        if self.keyword_index_path is None:
            self.keyword_index_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_keywords{self.docs_path.suffix}"
            )


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
        self._tokenized_docs: List[List[str]] = []
        self._keyword_index: KeywordIndex | None = None

    def _ensure_data_dirs(self) -> None:
        self._config.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._config.docs_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.tokenized_docs_path is not None:
            self._config.tokenized_docs_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.keyword_index_path is not None:
            self._config.keyword_index_path.parent.mkdir(parents=True, exist_ok=True)

    def _save_index_and_docs(
        self,
        index: faiss.IndexFlatIP,
        docs: List[str],
        tokenized_docs: List[List[str]],
        keyword_index: KeywordIndex,
    ) -> None:
        self._ensure_data_dirs()
        faiss.write_index(index, str(self._config.index_path))
        joblib.dump(docs, self._config.docs_path)
        if self._config.tokenized_docs_path is not None:
            joblib.dump(tokenized_docs, self._config.tokenized_docs_path)
        if self._config.keyword_index_path is not None:
            joblib.dump(keyword_index.to_persisted(), self._config.keyword_index_path)

    def _rebuild_index_from_docs(self, docs: List[str]) -> faiss.IndexFlatIP:
        embeddings = self._model.encode(
            docs, convert_to_numpy=True, normalize_embeddings=True
        )
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        keyword_index = KeywordIndex.build(docs)
        self._save_index_and_docs(index, docs, keyword_index.tokenized_docs, keyword_index)
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

        keyword_index = KeywordIndex.build(texts)

        self._save_index_and_docs(index, texts, keyword_index.tokenized_docs, keyword_index)

        self._index = index
        self._docs = texts
        self._tokenized_docs = keyword_index.tokenized_docs
        self._keyword_index = keyword_index

    def load(self) -> None:
        try:
            docs: List[str] = joblib.load(self._config.docs_path)
            tokenized_docs: List[List[str]] = joblib.load(
                self._config.tokenized_docs_path
            )
            keyword_data = joblib.load(self._config.keyword_index_path)
            index = faiss.read_index(str(self._config.index_path))
        except Exception as exc:  # pragma: no cover - defensive path
            raise FileNotFoundError("RAG index or docs file is missing.") from exc

        if self._embedding_dim is not None and index.d != self._embedding_dim:
            index = self._rebuild_index_from_docs(docs)

        keyword_index = KeywordIndex.from_persisted(tokenized_docs, keyword_data)

        self._index = index
        self._docs = docs
        self._tokenized_docs = tokenized_docs
        self._keyword_index = keyword_index

    def search(self, query: str, k: int = 5, fusion_weight: float = 0.5) -> List[Tuple[str, float]]:
        if (
            self._index is None
            or not self._docs
            or self._keyword_index is None
            or not self._tokenized_docs
        ):
            raise RuntimeError("RAG index not loaded. Call load() first.")

        vector_hits = self._search_vectors(query, k)
        keyword_hits = self._keyword_index.search(query, k)

        fusion_weight = min(max(fusion_weight, 0.0), 1.0)
        fused = self._fuse_results(vector_hits, keyword_hits, fusion_weight)

        results: List[Tuple[str, float]] = []
        for doc_idx, score in fused[: min(k, len(fused))]:
            if 0 <= doc_idx < len(self._docs):
                results.append((self._docs[doc_idx], score))
        return results

    def _search_vectors(self, query: str, k: int) -> List[Tuple[int, float]]:
        query_emb = self._model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        )
        scores, indices = self._index.search(query_emb, k)
        hits: List[Tuple[int, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            hits.append((int(idx), float(score)))
        return hits

    def _fuse_results(
        self,
        vector_hits: List[Tuple[int, float]],
        keyword_hits: List[Tuple[int, float]],
        fusion_weight: float,
    ) -> List[Tuple[int, float]]:
        scores: Dict[int, float] = {}
        rrf_k = 60

        for rank, (doc_idx, _score) in enumerate(vector_hits):
            contribution = fusion_weight / (rrf_k + rank + 1)
            scores[doc_idx] = scores.get(doc_idx, 0.0) + contribution

        for rank, (doc_idx, _score) in enumerate(keyword_hits):
            contribution = (1 - fusion_weight) / (rrf_k + rank + 1)
            scores[doc_idx] = scores.get(doc_idx, 0.0) + contribution

        return sorted(scores.items(), key=lambda item: item[1], reverse=True)
