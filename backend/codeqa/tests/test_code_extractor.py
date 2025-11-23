from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
from docx import Document

from codeqa.code_extractor import collect_code_chunks


PDF_CONTENT = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 24 Tf
100 100 Td
(Test PDF) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000079 00000 n 
0000000178 00000 n 
0000000409 00000 n 
0000000502 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
582
%%EOF
"""


class CollectCodeChunksTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.root_path = Path(self.tmpdir.name)
        self.addCleanup(self.tmpdir.cleanup)

    def test_collects_pdf_content(self) -> None:
        pdf_path = self.root_path / "sample.pdf"
        pdf_path.write_bytes(PDF_CONTENT)

        chunks = collect_code_chunks(self.root_path)

        self.assertTrue(
            any("File: sample.pdf" in chunk and "Test PDF" in chunk for chunk in chunks),
        )

    def test_collects_docx_content(self) -> None:
        docx_path = self.root_path / "sample.docx"
        document = Document()
        document.add_paragraph("Hello Word Doc")
        document.save(docx_path)

        chunks = collect_code_chunks(self.root_path)

        self.assertTrue(
            any("File: sample.docx" in chunk and "Hello Word Doc" in chunk for chunk in chunks),
        )
