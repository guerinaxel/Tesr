from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

from asgiref.sync import sync_to_async

from ..code_extractor import (
    collect_code_chunks as default_collect_code_chunks,
    iter_text_files as default_iter_text_files,
)
from ..models import RagSource
from .. import rag_service as rag_service_module
from .errors import RagSourceBuildError, RagSourceNotFoundError, RagSourcePathMissingError


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
    ) -> RagSource:
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
    ) -> RagSource:
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
    ) -> RagSource:
        return await sync_to_async(self.build_source)(paths=paths, name=name, description=description)

    async def rebuild_source_async(
        self,
        *,
        source_id: str,
        paths: list[str],
        name: str | None = None,
        description: str | None = None,
    ) -> RagSource:
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
    ) -> RagSource:
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

        base_dir = rag_service_module._rag_sources_base_dir() / str(source.id)
        try:
            self._reset_base_dir(base_dir)
            source.path = str(base_dir)
            source.save(update_fields=["name", "description", "total_files", "total_chunks", "path"])

            config = rag_service_module._build_config_from_env()
            config.index_path = base_dir / "rag_index.faiss"
            config.docs_path = base_dir / "docs.pkl"
            config.whoosh_index_dir = base_dir / "whoosh_index"
            config.embeddings_path = base_dir / "embeddings.pkl"
            config.metadata_path = base_dir / "index_meta.json"

            rag_index_cls = rag_service_module.RagIndex
            rag_index = rag_index_cls(config)
            rag_index.build_from_texts(chunks)

            self._write_metadata_file(source)
            rag_service_module.drop_cached_source(str(source.id))
            if rag_service_module._warm_cache_enabled():
                rag_service_module.warm_cached_source(source, index=rag_index)
            return source
        except (RagSourcePathMissingError, RagSourceNotFoundError):
            raise
        except Exception as exc:  # pragma: no cover - defensive path
            raise RagSourceBuildError(str(exc)) from exc

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

    def _reset_base_dir(self, base_dir: Path) -> None:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
