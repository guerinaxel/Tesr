from __future__ import annotations

from pathlib import Path
from typing import List

from django.core.management.base import BaseCommand, CommandParser

from codeqa.code_extractor import collect_code_chunks
from codeqa.rag_index import RagIndex
from codeqa.rag_service import _build_config_from_env


class Command(BaseCommand):
    help = "Build or rebuild the RAG index from the project source code."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--root",
            type=str,
            default="..",
            help="Path to the project root from the backend directory.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing index and docs files if they exist.",
        )

    def handle(self, *args, **options) -> None:
        root_path = Path(options["root"]).resolve()
        force: bool = options["force"]

        self.stdout.write(f"Collecting code from {root_path} ...")
        chunks: List[str] = collect_code_chunks(root_path)

        if not chunks:
            self.stderr.write("No code chunks found, aborting.")
            return

        self.stdout.write(f"Collected {len(chunks)} chunks. Building RAG index...")

        config = _build_config_from_env()
        index_path = config.index_path

        if not force and index_path.exists():
            self.stderr.write("Index already exists. Use --force to rebuild.")
            return

        rag_index = RagIndex(config)
        rag_index.build_from_texts(chunks)

        self.stdout.write(self.style.SUCCESS("RAG index built successfully."))
