from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class Document:
    name: str
    content: str


CATEGORY_BY_EXTENSION = {
    ".py": "source code",
    ".ts": "source code",
    ".tsx": "source code",
    ".js": "source code",
    ".jsx": "source code",
    ".css": "stylesheet",
    ".scss": "stylesheet",
    ".md": "documentation",
    ".rst": "documentation",
    ".txt": "text",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
    ".pdf": "document",
    ".docx": "document",
}


def summarize_content(content: str, *, max_sentences: int = 3, fallback_chars: int = 200) -> str:
    text = content.strip()
    if not text:
        return ""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if sentences:
        summary = " ".join(sentences[:max_sentences]).strip()
        if summary:
            return summary

    return text[:fallback_chars].strip()


def categorize_document(name: str, content: str) -> str:
    extension = Path(name).suffix.lower()
    if extension in CATEGORY_BY_EXTENSION:
        return CATEGORY_BY_EXTENSION[extension]

    text = content.lower()
    if any(token in text for token in ["class ", "def ", "function ", "import "]):
        return "source code"
    if any(token in text for token in ["#", "documentation", "guide", "how to"]):
        return "documentation"
    if any(token in text for token in ["{", "}", "["]):
        return "data"
    return "general"


def _score_text(question_tokens: List[str], text: str) -> int:
    words = [token for token in re.split(r"\W+", text.lower()) if token]
    frequencies = Counter(words)
    return sum(frequencies.get(token, 0) for token in question_tokens if token)


def answer_question_from_documents(question: str, documents: Iterable[Document]) -> str:
    cleaned_question = (question or "").strip()
    if not cleaned_question:
        return ""

    question_tokens = [token for token in re.split(r"\W+", cleaned_question.lower()) if token]
    if not question_tokens:
        return ""

    best_match: Document | None = None
    best_score = 0
    best_snippet = ""

    for doc in documents:
        score = _score_text(question_tokens, doc.content)
        if score <= 0:
            continue

        sentence_candidates = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", doc.content)
            if s.strip()
        ]
        snippet = next(
            (s for s in sentence_candidates if any(t in s.lower() for t in question_tokens)),
            sentence_candidates[0] if sentence_candidates else doc.content[:200].strip(),
        )

        if score > best_score:
            best_match = doc
            best_score = score
            best_snippet = snippet

    if best_match is None:
        return "No relevant content found in the provided documents."

    return f"Based on {best_match.name}: {best_snippet}"
