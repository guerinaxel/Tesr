from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from codeqa import code_extractor


class CodeExtractorTests(SimpleTestCase):
    def test_iter_text_files_includes_supported_extensions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "script.py"
            ignored = root / "binary.bin"
            nested = root / "nested"
            nested.mkdir()
            nested_file = nested / "component.ts"

            allowed.write_text("print('ok')")
            ignored.write_text("should be ignored")
            nested_file.write_text("console.log('ok')")

            found = {path.name for path in code_extractor.iter_text_files(root)}
            self.assertIn("script.py", found)
            self.assertIn("component.ts", found)
            self.assertNotIn("binary.bin", found)

    def test_chunk_text_splits_long_content_into_chunks(self) -> None:
        long_line = "a" * 1000
        content = "\n".join([long_line for _ in range(3)])

        chunks = code_extractor.chunk_text(content, max_chars=1100)

        self.assertEqual(3, len(chunks))
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1100)

    def test_collect_code_chunks_prefixes_file_names(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_a = root / "file.py"
            file_a.write_text("print('hello')\n# comment")

            chunks = code_extractor.collect_code_chunks(root)

            self.assertEqual(1, len(chunks))
            self.assertTrue(chunks[0].startswith("File: file.py\n\n"))
            self.assertIn("print('hello')", chunks[0])
