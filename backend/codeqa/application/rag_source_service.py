from __future__ import annotations

import fcntl
import json
import os
import shutil
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from asgiref.sync import sync_to_async
from django.db import transaction

from ..code_extractor import (
    collect_code_chunks as default_collect_code_chunks,
    iter_text_files as default_iter_text_files,
)
from ..models import RagSource
from .. import rag_service as rag_service_module
from .errors import RagSourceBuildError, RagSourceNotFoundError, RagSourcePathMissingError


@dataclass
class RagSourceBuildStatus:
    state: str
    message: str
    source_id: str | None = None
    name: str | None = None
    total_files: int | None = None
    total_chunks: int | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "message": self.message,
            "source_id": self.source_id,
            "name": self.name,
            "total_files": self.total_files,
            "total_chunks": self.total_chunks,
        }

    @classmethod
    def completed(
        cls,
        *,
        source: RagSource,
        message: str = "RAG source build completed",
    ) -> "RagSourceBuildStatus":
        return cls(
            state="completed",
            message=message,
            source_id=str(source.id),
            name=source.name,
            total_files=source.total_files,
            total_chunks=source.total_chunks,
        )

    @classmethod
    def failed(
        cls, *, source: RagSource | None = None, message: str
    ) -> "RagSourceBuildStatus":
        return cls(
            state="failed",
            message=message,
            source_id=str(source.id) if source else None,
            name=getattr(source, "name", None),
            total_files=getattr(source, "total_files", None),
            total_chunks=getattr(source, "total_chunks", None),
        )


@dataclass
class RagSourceBuildResult:
    source: RagSource
    status: RagSourceBuildStatus


class RagSourceService:
    """Encapsulates RAG source build operations and metadata persistence."""

    def list_sources(self) -> Iterable[RagSource]:
        return RagSource.objects.all().order_by("-created_at")

    def build_source(
        self,
        *,
        paths: list[str],
        name: str | None = None,
        description: str | None = None,
        collect_code_chunks_fn: Callable[[Path], list[str]] = default_collect_code_chunks,
        iter_text_files_fn: Callable[[Path], Iterable[Path]] = default_iter_text_files,
    ) -> RagSourceBuildResult:
        return self._build(
            paths=paths,
            name=name,
            description=description,
            existing=None,
            collect_code_chunks_fn=collect_code_chunks_fn,
            iter_text_files_fn=iter_text_files_fn,
        )

    def rebuild_source(
        self,
        *,
        source_id: str,
        paths: list[str],
        name: str | None = None,
        description: str | None = None,
        collect_code_chunks_fn: Callable[[Path], list[str]] = default_collect_code_chunks,
        iter_text_files_fn: Callable[[Path], Iterable[Path]] = default_iter_text_files,
    ) -> RagSourceBuildResult:
        source = RagSource.objects.filter(id=source_id).first()
        if source is None:
            raise RagSourceNotFoundError()
        return self._build(
            paths=paths,
            name=name,
            description=description,
            existing=source,
            collect_code_chunks_fn=collect_code_chunks_fn,
            iter_text_files_fn=iter_text_files_fn,
        )

    def update_metadata(
        self,
        *,
        source_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> RagSource:
        source = RagSource.objects.filter(id=source_id).first()
        if source is None:
            raise RagSourceNotFoundError()

        updated_fields: list[str] = []
        if name is not None:
            source.name = name or source.name
            updated_fields.append("name")
        if description is not None:
            source.description = description or ""
            updated_fields.append("description")

        if updated_fields:
            source.save(update_fields=updated_fields)
            self._write_metadata_file(source)
            rag_service_module.drop_cached_source(str(source.id))

        return source

    async def build_source_async(
        self,
        *,
        paths: list[str],
        name: str | None = None,
        description: str | None = None,
    ) -> RagSourceBuildResult:
        return await sync_to_async(self.build_source)(
            paths=paths, name=name, description=description
        )

    async def rebuild_source_async(
        self,
        *,
        source_id: str,
        paths: list[str],
        name: str | None = None,
        description: str | None = None,
    ) -> RagSourceBuildResult:
        return await sync_to_async(self.rebuild_source)(
            source_id=source_id, paths=paths, name=name, description=description
        )

    async def update_metadata_async(
        self,
        *,
        source_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> RagSource:
        return await sync_to_async(self.update_metadata)(
            source_id=source_id, name=name, description=description
        )

    def _build(
        self,
        *,
        paths: list[str],
        name: str | None,
        description: str | None,
        existing: RagSource | None,
        collect_code_chunks_fn: Callable[[Path], list[str]],
        iter_text_files_fn: Callable[[Path], Iterable[Path]],
    ) -> RagSourceBuildResult:
        resolved_paths = [Path(p).expanduser().resolve() for p in paths]
        counter: Counter[str] = Counter()
        total_files = 0
        chunks: list[str] = []

        for path in resolved_paths:
            if not path.exists():
                raise RagSourcePathMissingError(str(path))
            chunks.extend(collect_code_chunks_fn(path))
            files_here = list(iter_text_files_fn(path))
            total_files += len(files_here)
            counter.update(f.suffix for f in files_here)

        total_chunks = len(chunks)
        final_name = (name or resolved_paths[0].name).strip()
        popular_ext = ", ".join(ext for ext, _ in counter.most_common(3)) or "files"
        final_description = (description or (
            f"Auto-generated source from {len(resolved_paths)} path(s) containing {total_files} files ({popular_ext})."
        )).strip()

        temp_dir: Path | None = None
        backup_dir: Path | None = None
        target_dir: Path | None = None
        source: RagSource | None = None
        try:
            with transaction.atomic():
                source = existing or RagSource.objects.create(
                    name=final_name,
                    description=final_description,
                    path="",
                    total_files=total_files,
                    total_chunks=total_chunks,
                )

                if existing is not None:
                    source.name = final_name
                    source.description = final_description
                    source.total_files = total_files
                    source.total_chunks = total_chunks
                    source.save(
                        update_fields=[
                            "name",
                            "description",
                            "total_files",
                            "total_chunks",
                        ]
                    )

                with self._acquire_source_lock(str(source.id)):
                    base_dir = rag_service_module._rag_sources_base_dir() / str(source.id)
                    temp_dir = base_dir.with_name(f"{source.id}.tmp")
                    target_dir = base_dir
                    self._prepare_temp_dir(temp_dir)

                    config = self._build_config_for_dir(temp_dir)

                    rag_index_cls = rag_service_module.RagIndex
                    rag_index = rag_index_cls(config)
                    rag_index.build_from_texts(chunks)

                    backup_dir = self._atomic_swap_dir(temp_dir, base_dir)

                    source.path = str(base_dir)
                    source.save(
                        update_fields=[
                            "name",
                            "description",
                            "total_files",
                            "total_chunks",
                            "path",
                        ]
                    )

                    self._write_metadata_file(source)

                    status = RagSourceBuildStatus.completed(source=source)

                    rag_index.config = self._build_config_for_dir(base_dir)
                    rag_service_module.drop_cached_source(str(source.id))

                    def _on_commit() -> None:
                        if rag_service_module._warm_cache_enabled():
                            rag_service_module.warm_cached_source(source, index=rag_index)
                        if backup_dir and backup_dir.exists():
                            shutil.rmtree(backup_dir, ignore_errors=True)

                    transaction.on_commit(_on_commit)

            return RagSourceBuildResult(source=source, status=status)
        except (RagSourcePathMissingError, RagSourceNotFoundError):
            raise
        except Exception as exc:  # pragma: no cover - defensive path
            if backup_dir and backup_dir.exists() and target_dir:
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)
                os.replace(backup_dir, target_dir)
            raise RagSourceBuildError(str(exc)) from exc
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _write_metadata_file(self, source: RagSource) -> None:
        base_dir = Path(source.path)
        base_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "id": str(source.id),
            "name": source.name,
            "description": source.description,
            "path": source.path,
            "total_files": source.total_files,
            "total_chunks": source.total_chunks,
        }
        (base_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    def _build_config_for_dir(self, base_dir: Path):
        config = rag_service_module._build_config_from_env()
        config.index_path = base_dir / "rag_index.faiss"
        config.docs_path = base_dir / "docs.pkl"
        config.tokenized_docs_path = base_dir / "docs_tokens.pkl"
        config.keyword_index_path = base_dir / "docs_keywords.pkl"
        config.whoosh_index_dir = base_dir / "whoosh_index"
        config.embeddings_path = base_dir / "embeddings.pkl"
        config.metadata_path = base_dir / "index_meta.json"
        return config

    def _prepare_temp_dir(self, temp_dir: Path) -> None:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_swap_dir(self, temp_dir: Path, target_dir: Path) -> Path | None:
        backup_dir: Path | None = None

        if target_dir.exists():
            backup_dir = target_dir.with_suffix(".bak")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            target_dir.replace(backup_dir)

        os.replace(temp_dir, target_dir)

        return backup_dir

    @contextmanager
    def _acquire_source_lock(self, source_id: str):
        lock_dir = rag_service_module._rag_sources_base_dir()
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / f"{source_id}.lock"
        with lock_path.open("a") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
