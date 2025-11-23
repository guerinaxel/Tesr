from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from docx import Document
from PyPDF2 import PdfReader


TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".scss", ".css", ".md"}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(filter(None, pages))

    if text:
        return text

    ocr_text = extract_pdf_ocr_text(path)
    return ocr_text or text


def extract_pdf_ocr_text(path: Path) -> str:
    modules = load_optional_ocr_modules()
    if modules is None:
        return ""

    convert_from_path, image_to_string = modules

    try:
        images = convert_from_path(str(path))
    except Exception:
        return ""

    ocr_pages: list[str] = []
    for image in images:
        try:
            page_text = image_to_string(image)
        except Exception:
            continue
        page_text = page_text.strip()
        if page_text:
            ocr_pages.append(page_text)

    return "\n".join(ocr_pages)


def load_optional_ocr_modules() -> Optional[tuple[Callable[[str], List[object]], Callable[[object], str]]]:
    pdf2image_spec = importlib.util.find_spec("pdf2image")
    pytesseract_spec = importlib.util.find_spec("pytesseract")

    if pdf2image_spec is None or pytesseract_spec is None:
        return None

    from pdf2image import convert_from_path
    from pytesseract import image_to_string

    return convert_from_path, image_to_string


def extract_docx_text(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)


DOCUMENT_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".pdf": extract_pdf_text,
    ".docx": extract_docx_text,
}

SUPPORTED_EXTENSIONS: set[str] = TEXT_EXTENSIONS | set(DOCUMENT_EXTRACTORS)


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in SUPPORTED_EXTENSIONS:
            yield path


def chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in text.splitlines():
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def collect_code_chunks(root: Path) -> List[str]:
    root = root.resolve()
    chunks: List[str] = []
    for file_path in iter_text_files(root):
        try:
            if file_path.suffix in TEXT_EXTENSIONS:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            else:
                extractor = DOCUMENT_EXTRACTORS.get(file_path.suffix)
                if extractor is None:
                    continue
                text = extractor(file_path)
        except OSError:
            continue
        except Exception:
            continue
        file_chunks = chunk_text(text)
        for ch in file_chunks:
            chunks.append(f"File: {file_path.relative_to(root)}\n\n{ch}")
    return chunks
