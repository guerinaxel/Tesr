from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DomainError(Exception):
    """Base class for structured domain errors."""

    detail: str
    code: str = "domain_error"
    status_code: int = 400

    def __str__(self) -> str:  # pragma: no cover - dataclass helper
        return self.detail


class RagSourceNotFoundError(DomainError):
    def __init__(self, detail: str = "RAG source not found"):
        super().__init__(detail=detail, code="rag_source_not_found", status_code=404)


class RagSourcePathMissingError(DomainError):
    def __init__(self, path: str):
        super().__init__(
            detail=f"Path not found: {path}",
            code="rag_source_path_missing",
            status_code=400,
        )


class RagSourceBuildError(DomainError):
    def __init__(self, detail: str = "Failed to build RAG source"):
        super().__init__(detail=detail, code="rag_source_build_error", status_code=500)


class RagAnswerNotReadyError(DomainError):
    def __init__(self, detail: str = "RAG answer not ready"):
        super().__init__(detail=detail, code="rag_answer_not_ready", status_code=503)
