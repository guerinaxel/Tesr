from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


def _tokenize(text: str) -> List[str]:
    return [token for token in text.lower().split() if token]


@dataclass
class KeywordIndex:
    tokenized_docs: List[List[str]]
    idf: Dict[str, float]
    doc_lengths: List[int]
    avgdl: float
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def build(cls, texts: Sequence[str]) -> KeywordIndex:
        tokenized_docs: List[List[str]] = [_tokenize(text) for text in texts]
        doc_freq: Dict[str, int] = {}
        doc_lengths: List[int] = []

        for tokens in tokenized_docs:
            doc_lengths.append(len(tokens))
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1

        num_docs = len(tokenized_docs) or 1
        avgdl = sum(doc_lengths) / num_docs if doc_lengths else 0.0

        idf: Dict[str, float] = {}
        for token, df in doc_freq.items():
            idf[token] = math.log((num_docs - df + 0.5) / (df + 0.5) + 1)

        return cls(tokenized_docs=tokenized_docs, idf=idf, doc_lengths=doc_lengths, avgdl=avgdl)

    @classmethod
    def from_persisted(
        cls, tokenized_docs: List[List[str]], data: Dict[str, float | List[int] | float]
    ) -> KeywordIndex:
        return cls(
            tokenized_docs=tokenized_docs,
            idf=data.get("idf", {}),
            doc_lengths=data.get("doc_lengths", []),
            avgdl=float(data.get("avgdl", 0.0)),
            k1=float(data.get("k1", 1.5)),
            b=float(data.get("b", 0.75)),
        )

    def to_persisted(self) -> Dict[str, float | Dict[str, float] | List[int]]:
        return {
            "idf": self.idf,
            "doc_lengths": self.doc_lengths,
            "avgdl": self.avgdl,
            "k1": self.k1,
            "b": self.b,
        }

    def search(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self.tokenized_docs:
            return []

        scores: List[Tuple[int, float]] = []
        for doc_id, tokens in enumerate(self.tokenized_docs):
            score = self._score_doc(tokens, query_tokens, doc_id)
            scores.append((doc_id, score))

        sorted_scores = sorted(scores, key=lambda item: item[1], reverse=True)
        return sorted_scores[: min(k, len(sorted_scores))]

    def _score_doc(self, doc_tokens: Iterable[str], query_tokens: List[str], doc_id: int) -> float:
        doc_len = self.doc_lengths[doc_id] if doc_id < len(self.doc_lengths) else len(list(doc_tokens))
        score = 0.0
        if doc_len == 0:
            return score

        freq: Dict[str, int] = {}
        for token in doc_tokens:
            freq[token] = freq.get(token, 0) + 1

        for token in query_tokens:
            if token not in freq:
                continue
            idf = self.idf.get(token, 0.0)
            numerator = freq[token] * (self.k1 + 1)
            denominator = freq[token] + self.k1 * (1 - self.b + self.b * (doc_len / (self.avgdl or 1)))
            score += idf * numerator / denominator

        return score

