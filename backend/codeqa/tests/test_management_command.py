from __future__ import annotations

import os
import uuid
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from codeqa.models import RagSource
from codeqa.management.commands import build_rag_index


class BuildRagIndexCommandTests(TestCase):
    def setUp(self) -> None:
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        os.environ["RAG_DATA_DIR"] = self.tmpdir.name
        os.environ["RAG_INDEX_PATH"] = str(Path(self.tmpdir.name) / "rag_index.faiss")
        os.environ["RAG_DOCS_PATH"] = str(Path(self.tmpdir.name) / "rag_docs.pkl")
        os.environ["RAG_SOURCES_DIR"] = self.tmpdir.name
        self.addCleanup(os.environ.pop, "RAG_DATA_DIR", None)
        self.addCleanup(os.environ.pop, "RAG_INDEX_PATH", None)
        self.addCleanup(os.environ.pop, "RAG_DOCS_PATH", None)
        self.addCleanup(os.environ.pop, "RAG_SOURCES_DIR", None)

    def test_aborts_when_no_chunks_found(self) -> None:
        # Arrange
        def fake_collect_code_chunks(root: Path) -> List[str]:
            return []

        build_rag_index.collect_code_chunks = fake_collect_code_chunks  # type: ignore[assignment]

        # Act
        call_command(
            "build_rag_index",
            stdout=self.stdout,
            stderr=self.stderr,
            paths=[self.tmpdir.name],
        )

        # Assert
        self.assertIn("No code chunks found", self.stderr.getvalue())

    def test_skips_when_index_exists_without_force(self) -> None:
        # Arrange
        fixed_id = uuid.uuid4()
        base_dir = Path(self.tmpdir.name) / str(fixed_id)
        existing_index = base_dir / "rag_index.faiss"
        existing_index.parent.mkdir(parents=True, exist_ok=True)
        existing_index.write_text("existing")

        def fake_collect_code_chunks(root: Path) -> List[str]:
            return ["code"]

        class FakeRagIndex:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def build_from_texts(self, texts: List[str]) -> None:
                raise AssertionError("Should not be called without --force")

        def fake_create(**kwargs):
            obj = RagSource(id=fixed_id, **kwargs)
            obj.save(force_insert=True)
            return obj

        build_rag_index.collect_code_chunks = fake_collect_code_chunks  # type: ignore[assignment]
        build_rag_index.RagIndex = FakeRagIndex  # type: ignore[assignment]

        # Act
        with patch(
            "codeqa.management.commands.build_rag_index.RagSource.objects.create",
            side_effect=fake_create,
        ):
            call_command(
                "build_rag_index",
                stdout=self.stdout,
                stderr=self.stderr,
                paths=[self.tmpdir.name],
            )

        # Assert
        self.assertIn("Index already exists", self.stderr.getvalue())

    def test_builds_index_when_force_flag_used(self) -> None:
        # Arrange
        created_docs: List[str] = []

        def fake_collect_code_chunks(root: Path) -> List[str]:
            return ["doc1", "doc2"]

        class FakeRagIndex:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def build_from_texts(self, texts: List[str]) -> None:
                created_docs.extend(texts)

        build_rag_index.collect_code_chunks = fake_collect_code_chunks  # type: ignore[assignment]
        build_rag_index.RagIndex = FakeRagIndex  # type: ignore[assignment]

        # Act
        call_command(
            "build_rag_index",
            "--force",
            stdout=self.stdout,
            stderr=self.stderr,
            paths=[self.tmpdir.name],
        )

        # Assert
        self.assertEqual(["doc1", "doc2"], created_docs)
        self.assertIn("RAG index built successfully", self.stdout.getvalue())
