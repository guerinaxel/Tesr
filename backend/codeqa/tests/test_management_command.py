from __future__ import annotations

import os
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

from django.core.management import call_command
from django.test import SimpleTestCase

from codeqa.management.commands import build_rag_index


class BuildRagIndexCommandTests(SimpleTestCase):
    def setUp(self) -> None:
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        os.environ["RAG_DATA_DIR"] = self.tmpdir.name
        os.environ["RAG_INDEX_PATH"] = str(Path(self.tmpdir.name) / "rag_index.faiss")
        os.environ["RAG_DOCS_PATH"] = str(Path(self.tmpdir.name) / "rag_docs.pkl")
        self.addCleanup(os.environ.pop, "RAG_DATA_DIR", None)
        self.addCleanup(os.environ.pop, "RAG_INDEX_PATH", None)
        self.addCleanup(os.environ.pop, "RAG_DOCS_PATH", None)

    def test_aborts_when_no_chunks_found(self) -> None:
        def fake_collect_code_chunks(root: Path) -> List[str]:
            return []

        build_rag_index.collect_code_chunks = fake_collect_code_chunks  # type: ignore[assignment]

        call_command("build_rag_index", stdout=self.stdout, stderr=self.stderr)

        self.assertIn("No code chunks found", self.stderr.getvalue())

    def test_skips_when_index_exists_without_force(self) -> None:
        existing_index = Path(os.environ["RAG_INDEX_PATH"])
        existing_index.parent.mkdir(parents=True, exist_ok=True)
        existing_index.write_text("existing")

        def fake_collect_code_chunks(root: Path) -> List[str]:
            return ["code"]

        class FakeRagIndex:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def build_from_texts(self, texts: List[str]) -> None:
                raise AssertionError("Should not be called without --force")

        build_rag_index.collect_code_chunks = fake_collect_code_chunks  # type: ignore[assignment]
        build_rag_index.RagIndex = FakeRagIndex  # type: ignore[assignment]

        call_command("build_rag_index", stdout=self.stdout, stderr=self.stderr)

        self.assertIn("Index already exists", self.stderr.getvalue())

    def test_builds_index_when_force_flag_used(self) -> None:
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

        call_command("build_rag_index", "--force", stdout=self.stdout, stderr=self.stderr)

        self.assertEqual(["doc1", "doc2"], created_docs)
        self.assertIn("RAG index built successfully", self.stdout.getvalue())
