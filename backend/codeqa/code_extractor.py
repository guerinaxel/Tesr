from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional, Sequence

from docx import Document
from PyPDF2 import PdfReader


TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".scss", ".css", ".md"}
AST_EXTENSIONS = {".py", ".ts", ".tsx"}


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


@dataclass
class CodeChunk:
    source: str
    start_line: int
    end_line: int


def _split_large_chunk(chunk: CodeChunk, max_chars: int) -> List[str]:
    if len(chunk.source) <= max_chars:
        return [chunk.source]
    return chunk_text(chunk.source, max_chars=max_chars)


def _python_ast_chunks(text: str, max_chars: int = 1200) -> List[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:  # pragma: no cover - covered by fallback
        raise ValueError("Unable to parse python code") from exc

    lines = text.splitlines()
    chunks: list[CodeChunk] = []

    class Visitor(ast.NodeVisitor):
        def visit(self, node: ast.AST) -> None:  # type: ignore[override]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if getattr(node, "lineno", None) and getattr(node, "end_lineno", None):
                    start = node.lineno
                    end = node.end_lineno
                    source = "\n".join(lines[start - 1 : end])
                    chunks.append(CodeChunk(source=source, start_line=start, end_line=end))
            super().visit(node)

    Visitor().visit(tree)

    if not chunks:
        return chunk_text(text, max_chars=max_chars)

    return [piece for chunk in sorted(chunks, key=lambda c: (c.start_line, c.end_line)) for piece in _split_large_chunk(chunk, max_chars)]


def _iter_ts_nodes(root: object, target_types: Sequence[str]) -> Iterator[object]:
    stack = [root]
    while stack:
        node = stack.pop()
        node_type = getattr(node, "type", None)
        if node_type in target_types:
            yield node
        children = getattr(node, "children", None) or []
        stack.extend(reversed(children))


def _typescript_ast_chunks(text: str, is_tsx: bool, max_chars: int = 1200) -> List[str]:
    try:
        from tree_sitter_languages import get_parser
    except Exception as exc:  # pragma: no cover - dependency missing
        raise ValueError("tree_sitter_languages is not available") from exc

    parser = get_parser("tsx" if is_tsx else "typescript")
    try:
        tree = parser.parse(bytes(text, "utf-8"))
    except Exception as exc:  # pragma: no cover - parse safety
        raise ValueError("Unable to parse typescript code") from exc

    root = tree.root_node
    target_types = {
        "function_declaration",
        "method_definition",
        "method_signature",
        "class_declaration",
    }
    chunks: list[CodeChunk] = []
    for node in _iter_ts_nodes(root, tuple(target_types)):
        start = getattr(node, "start_point", None)
        end = getattr(node, "end_point", None)
        if start is None or end is None:
            continue
        start_line = start[0] + 1
        end_line = end[0] + 1
        source = text[node.start_byte : node.end_byte]
        chunks.append(CodeChunk(source=source, start_line=start_line, end_line=end_line))

    if not chunks:
        return chunk_text(text, max_chars=max_chars)

    chunks.sort(key=lambda c: (c.start_line, c.end_line))
    return [piece for chunk in chunks for piece in _split_large_chunk(chunk, max_chars)]


def chunk_code_with_ast(path: Path, text: str, max_chars: int = 1200) -> List[str]:
    suffix = path.suffix
    if suffix == ".py":
        return _python_ast_chunks(text, max_chars=max_chars)
    if suffix in {".ts", ".tsx"}:
        return _typescript_ast_chunks(text, is_tsx=suffix == ".tsx", max_chars=max_chars)
    raise ValueError(f"Unsupported extension for AST chunking: {suffix}")


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
        try:
            if file_path.suffix in AST_EXTENSIONS:
                file_chunks = chunk_code_with_ast(file_path, text)
            else:
                file_chunks = chunk_text(text)
        except Exception:
            file_chunks = chunk_text(text)
        for ch in file_chunks:
            chunks.append(f"File: {file_path.relative_to(root)}\n\n{ch}")
    return chunks
