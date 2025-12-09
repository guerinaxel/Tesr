from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import List

from django.core.management.base import BaseCommand, CommandParser

from codeqa import rag_service
from codeqa.code_extractor import collect_code_chunks, iter_text_files
from codeqa.rag_index import RagIndex
from codeqa.rag_service import _build_config_from_env, _rag_sources_base_dir
from codeqa.models import RagSource


class Command(BaseCommand):
    help = "Build or rebuild the RAG index from the project source code."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--name", type=str, default="", help="Optional source name")
        parser.add_argument(
            "--description", type=str, default="", help="Optional source description"
        )
        parser.add_argument(
            "--source-path",
            type=str,
            action="append",
            dest="paths",
            required=True,
            help="Path to include in the RAG source. Can be specified multiple times.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing index and docs files if they exist.",
        )

    def handle(self, *args, **options) -> None:
        raw_paths: list[str] = options["paths"] or []
        name: str = options.get("name") or ""
        description: str = options.get("description") or ""
        force: bool = options["force"]

        resolved_paths = [Path(path).resolve() for path in raw_paths]
        for path in resolved_paths:
            if not path.exists():
                self.stderr.write(f"Path not found: {path}")
                return

        chunks: List[str] = []
        total_files = 0
        ext_counter: Counter[str] = Counter()

        for path in resolved_paths:
            self.stdout.write(f"Collecting code from {path} ...")
            chunks.extend(collect_code_chunks(path))
            files_here = list(iter_text_files(path))
            total_files += len(files_here)
            ext_counter.update(f.suffix for f in files_here)

        if not chunks:
            self.stderr.write("No code chunks found, aborting.")
            return

        total_chunks = len(chunks)
        if not name:
            name = resolved_paths[0].name
        if not description:
            popular_ext = ", ".join(ext for ext, _ in ext_counter.most_common(3)) or "files"
            description = (
                f"Auto-generated source from {len(resolved_paths)} path(s) "
                f"containing {total_files} files ({popular_ext})."
            )

        source = RagSource.objects.create(
            name=name,
            description=description,
            path="",
            total_files=total_files,
            total_chunks=total_chunks,
        )

        base_dir = _rag_sources_base_dir() / str(source.id)
        base_dir.mkdir(parents=True, exist_ok=True)
        source.path = str(base_dir)
        source.save(update_fields=["path"])

        self.stdout.write(f"Collected {len(chunks)} chunks. Building RAG index...")

        config = _build_config_from_env()
        index_path = base_dir / "rag_index.faiss"
        docs_path = base_dir / "docs.pkl"
        config.index_path = index_path
        config.docs_path = docs_path
        config.tokenized_docs_path = base_dir / "docs_tokens.pkl"
        config.keyword_index_path = base_dir / "docs_keywords.pkl"
        config.whoosh_index_dir = base_dir / "whoosh_index"
        config.embeddings_path = base_dir / "embeddings.pkl"
        config.metadata_path = base_dir / "index_meta.json"

        if not force and index_path.exists():
            self.stderr.write("Index already exists. Use --force to rebuild.")
            return

        rag_index = RagIndex(config)
        rag_index.build_from_texts(chunks)
        if rag_service._warm_cache_enabled():
            rag_service.drop_cached_source(str(source.id))
            rag_service.warm_cached_source(source, index=rag_index)

        metadata = {
            "id": str(source.id),
            "name": source.name,
            "description": source.description,
            "path": source.path,
            "total_files": total_files,
            "total_chunks": total_chunks,
        }
        metadata_path = base_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        self.stdout.write(self.style.SUCCESS("RAG index built successfully."))
