from __future__ import annotations
import hashlib
import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss  # type: ignore
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer

from .embedding_cache import QueryEmbeddingCache, build_cache_from_env
from .inverted_index import InvertedIndex
from .keyword_index import KeywordIndex


@dataclass
class RagConfig:
    index_path: Path
    docs_path: Path
    tokenized_docs_path: Path | None = None
    keyword_index_path: Path | None = None
    whoosh_index_dir: Path | None = None
    embeddings_path: Path | None = None
    metadata_path: Path | None = None
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    fallback_embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_kwargs: Dict[str, Any] | None = None
    persist_embeddings: bool = True
    index_version: str = "1"

    def __post_init__(self) -> None:
        if self.tokenized_docs_path is None:
            self.tokenized_docs_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_tokens{self.docs_path.suffix}"
            )
        if self.keyword_index_path is None:
            self.keyword_index_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_keywords{self.docs_path.suffix}"
            )
        if self.whoosh_index_dir is None:
            self.whoosh_index_dir = self.docs_path.parent / "whoosh_index"
        if self.embeddings_path is None:
            self.embeddings_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_embeddings.pkl"
            )
        if self.metadata_path is None:
            self.metadata_path = self.docs_path.with_name(
                f"{self.docs_path.stem}_meta.json"
            )


class RagIndex:
    def __init__(self, config: RagConfig) -> None:
        self._config = config
        model_kwargs: Dict[str, Any] = config.embedding_model_kwargs or {}
        if "nomic" in config.embedding_model_name:
            self._ensure_nomic_dependencies()
            if "trust_remote_code" not in model_kwargs:
                model_kwargs["trust_remote_code"] = True
        self._model = self._load_model_with_fallback(model_kwargs)

        # Not all SentenceTransformer-compatible models expose a helper to report their
        # embedding dimension (e.g., the test FakeModel). Fall back to None and rely on
        # runtime encodes if unavailable.
        get_dim = getattr(self._model, "get_sentence_embedding_dimension", None)
        self._embedding_dim: int | None = get_dim() if callable(get_dim) else None
        self._index: faiss.IndexFlatIP | None = None
        self._docs: List[str] = []
        self._tokenized_docs: List[List[str]] = []
        self._keyword_index: KeywordIndex | None = None
        self._inverted_index: InvertedIndex | None = None
        self._doc_embeddings: np.ndarray | None = None
        self._embedding_cache: QueryEmbeddingCache = build_cache_from_env()

    def _ensure_nomic_dependencies(self) -> None:
        try:
            importlib.import_module("sentencepiece")
        except Exception as exc:
            raise ImportError(
                "The Nomic embedding model requires the 'sentencepiece' package. "
                "Install it with `pip install sentencepiece` or set RAG_EMBED_MODEL "
                "to a different embedding model."
            ) from exc

    def _load_model_with_fallback(self, model_kwargs: Dict[str, Any]):
        logger = logging.getLogger(__name__)
        primary = self._config.embedding_model_name
        fallback = self._config.fallback_embedding_model_name

        try:
            return SentenceTransformer(primary, **model_kwargs)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Failed to load embedding model '%s': %s", primary, exc)
            if fallback == primary:
                raise

            logger.info("Falling back to embedding model '%s'", fallback)
            return SentenceTransformer(fallback, **model_kwargs)

    def _ensure_data_dirs(self) -> None:
        self._config.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._config.docs_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.tokenized_docs_path is not None:
            self._config.tokenized_docs_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.keyword_index_path is not None:
            self._config.keyword_index_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.whoosh_index_dir is not None:
            self._config.whoosh_index_dir.mkdir(parents=True, exist_ok=True)
        if self._config.embeddings_path is not None:
            self._config.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config.metadata_path is not None:
            self._config.metadata_path.parent.mkdir(parents=True, exist_ok=True)

    def _save_index_and_docs(
        self,
        index: faiss.IndexFlatIP,
        docs: List[str],
        tokenized_docs: List[List[str]],
        keyword_index: KeywordIndex,
        *,
        embeddings: np.ndarray | None,
        checksum: str,
    ) -> None:
        self._ensure_data_dirs()
        faiss.write_index(index, str(self._config.index_path))
        joblib.dump(docs, self._config.docs_path)
        if self._config.tokenized_docs_path is not None:
            joblib.dump(tokenized_docs, self._config.tokenized_docs_path)
        if self._config.keyword_index_path is not None:
            joblib.dump(keyword_index.to_persisted(), self._config.keyword_index_path)
        if self._config.whoosh_index_dir is not None:
            InvertedIndex.build(docs, self._config.whoosh_index_dir)
        if self._config.persist_embeddings and embeddings is not None:
            if self._config.embeddings_path is not None:
                joblib.dump(embeddings, self._config.embeddings_path)
        if self._config.metadata_path is not None:
            metadata = {"version": self._config.index_version, "checksum": checksum}
            self._config.metadata_path.write_text(json.dumps(metadata, indent=2))

    def _load_metadata(self) -> tuple[str | None, str | None]:
        if self._config.metadata_path is None:
            return None, None
        if not self._config.metadata_path.exists():
            return None, None
        try:
            data = json.loads(self._config.metadata_path.read_text())
            return data.get("version"), data.get("checksum")
        except Exception:  # pragma: no cover - defensive against corrupted files
            return None, None

    def _compute_checksum(self, docs: List[str]) -> str:
        hasher = hashlib.sha256()
        for doc in docs:
            hasher.update(doc.encode("utf-8"))
        return hasher.hexdigest()

    def _rebuild_index_from_docs(
        self, docs: List[str]
    ) -> tuple[faiss.IndexFlatIP, List[List[str]], KeywordIndex]:
        embeddings = self._model.encode(
            docs, convert_to_numpy=True, normalize_embeddings=True
        )
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        keyword_index = KeywordIndex.build(docs)
        checksum = self._compute_checksum(docs)
        self._save_index_and_docs(
            index,
            docs,
            keyword_index.tokenized_docs,
            keyword_index,
            embeddings=embeddings,
            checksum=checksum,
        )
        self._doc_embeddings = embeddings
        return index, keyword_index.tokenized_docs, keyword_index

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

        checksum = self._compute_checksum(texts)

        self._save_index_and_docs(
            index,
            texts,
            keyword_index.tokenized_docs,
            keyword_index,
            embeddings=embeddings,
            checksum=checksum,
        )

        self._index = index
        self._docs = texts
        self._tokenized_docs = keyword_index.tokenized_docs
        self._keyword_index = keyword_index
        self._doc_embeddings = embeddings
        if self._config.whoosh_index_dir is not None:
            self._inverted_index = InvertedIndex.from_dir(self._config.whoosh_index_dir)

    def load(self) -> None:
        try:
            docs: List[str] = joblib.load(self._config.docs_path)
            tokenized_docs: List[List[str]] = joblib.load(
                self._config.tokenized_docs_path
            )
            keyword_data = joblib.load(self._config.keyword_index_path)
        except Exception as exc:  # pragma: no cover - defensive path
            raise FileNotFoundError("RAG index or docs file is missing.") from exc

        stored_version, stored_checksum = self._load_metadata()
        current_checksum = self._compute_checksum(docs)

        index: faiss.IndexFlatIP | None = None
        try:
            index = faiss.read_index(str(self._config.index_path))
        except Exception:  # pragma: no cover - defensive path
            index = None

        needs_rebuild = (
            index is None
            or (self._embedding_dim is not None and index.d != self._embedding_dim)
            or stored_version != self._config.index_version
            or stored_checksum != current_checksum
        )

        if needs_rebuild:
            index, tokenized_docs, keyword_index = self._rebuild_index_from_docs(docs)
        else:
            keyword_index = KeywordIndex.from_persisted(tokenized_docs, keyword_data)
            if self._config.persist_embeddings and self._config.embeddings_path:
                try:
                    self._doc_embeddings = joblib.load(self._config.embeddings_path)
                except Exception:  # pragma: no cover - cache miss or corruption
                    self._doc_embeddings = None

        self._index = index
        self._docs = docs
        self._tokenized_docs = tokenized_docs
        self._keyword_index = keyword_index
        if self._config.whoosh_index_dir is not None:
            try:
                self._inverted_index = InvertedIndex.from_dir(self._config.whoosh_index_dir)
            except FileNotFoundError:
                self._inverted_index = InvertedIndex.build(docs, self._config.whoosh_index_dir)

    def search(self, query: str, k: int = 5, fusion_weight: float = 0.5) -> List[Tuple[str, float]]:
        if (
            self._index is None
            or not self._docs
            or self._keyword_index is None
            or not self._tokenized_docs
            or self._inverted_index is None
        ):
            raise RuntimeError("RAG index not loaded. Call load() first.")

        vector_hits = self._search_vectors(query, k)
        keyword_hits = self._keyword_index.search(query, k)
        inverted_hits = self._inverted_index.search(query, k)
        keyword_hits = self._merge_keyword_hits(keyword_hits, inverted_hits)

        fusion_weight = min(max(fusion_weight, 0.0), 1.0)
        fused = self._fuse_results(vector_hits, keyword_hits, fusion_weight)

        results: List[Tuple[str, float]] = []
        for doc_idx, score in fused[: min(k, len(fused))]:
            if 0 <= doc_idx < len(self._docs):
                results.append((self._docs[doc_idx], score))
        return results

    def _search_vectors(self, query: str, k: int) -> List[Tuple[int, float]]:
        cached = self._embedding_cache.get(query)
        if cached is None:
            encoded = self._model.encode(
                [query], convert_to_numpy=True, normalize_embeddings=True
            )
            cached = encoded[0] if len(encoded.shape) > 1 else encoded
            self._embedding_cache.set(query, cached)

        query_emb = np.asarray([cached], dtype=np.float32)
        scores, indices = self._index.search(query_emb, k)
        hits: List[Tuple[int, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            hits.append((int(idx), float(score)))
        return hits

    def _merge_keyword_hits(
        self, primary_hits: List[Tuple[int, float]], secondary_hits: List[Tuple[int, float]]
    ) -> List[Tuple[int, float]]:
        scores: Dict[int, float] = {}
        for doc_idx, score in primary_hits:
            scores[doc_idx] = max(scores.get(doc_idx, 0.0), score)
        for doc_idx, score in secondary_hits:
            boosted = score * 1.1  # Slight boost to fuzzy matches
            scores[doc_idx] = max(scores.get(doc_idx, 0.0), boosted)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)

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
