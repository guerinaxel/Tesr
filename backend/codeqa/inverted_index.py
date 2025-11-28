from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from whoosh import index
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import FuzzyTermPlugin, MultifieldParser, OrGroup
from whoosh.scoring import BM25F
from whoosh import writing


@dataclass
class InvertedIndex:
    """Whoosh-based inverted index to power keyword and fuzzy search."""

    root_dir: Path
    field_name: str = "content"

    @classmethod
    def build(cls, docs: Sequence[str], root_dir: Path) -> InvertedIndex:
        if root_dir.exists():
            shutil.rmtree(root_dir, ignore_errors=True)
        root_dir.mkdir(parents=True, exist_ok=True)
        schema = Schema(doc_id=ID(stored=True, unique=True), content=TEXT(stored=True))
        idx = index.create_in(str(root_dir), schema)
        writer = idx.writer()
        for doc_id, text in enumerate(docs):
            writer.add_document(doc_id=str(doc_id), content=text)
        writer.commit(optimize=True)
        return cls(root_dir=root_dir)

    @classmethod
    def from_dir(cls, root_dir: Path) -> InvertedIndex:
        if not index.exists_in(str(root_dir)):
            raise FileNotFoundError(f"Whoosh index not found in {root_dir}")
        return cls(root_dir=root_dir)

    def search(self, query: str, limit: int = 5) -> List[Tuple[int, float]]:
        if not query.strip():
            return []
        if not index.exists_in(str(self.root_dir)):
            return []

        idx = index.open_dir(str(self.root_dir))
        parser = MultifieldParser([self.field_name], schema=idx.schema, group=OrGroup)
        parser.add_plugin(FuzzyTermPlugin())
        parsed_query = parser.parse(query)

        with idx.searcher(weighting=BM25F()) as searcher:
            hits = searcher.search(parsed_query, limit=limit)
            results: List[Tuple[int, float]] = []
            for hit in hits:
                doc_id = hit.get("doc_id")
                if doc_id is None:
                    continue
                results.append((int(doc_id), float(hit.score)))
            return results

