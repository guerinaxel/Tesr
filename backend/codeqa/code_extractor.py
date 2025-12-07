from __future__ import annotations

import ast
import importlib
import re
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

    return [
        piece
        for chunk in sorted(chunks, key=lambda c: (c.start_line, c.end_line))
        for piece in _split_large_chunk(chunk, max_chars)
    ]


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value_name = _node_name(node.value)
        return f"{value_name}.{node.attr}" if value_name else node.attr
    if isinstance(node, ast.Call):
        return _node_name(node.func)
    if isinstance(node, ast.Subscript):
        return _node_name(node.value)
    return ""


def _summarize_model_fields(class_node: ast.ClassDef) -> list[str]:
    fields: list[str] = []
    for stmt in class_node.body:
        target: str | None = None
        if isinstance(stmt, ast.Assign) and stmt.targets:
            first_target = stmt.targets[0]
            if isinstance(first_target, ast.Name):
                target = first_target.id
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target = stmt.target.id
        if target is None:
            continue
        value = getattr(stmt, "value", None)
        value_name = _node_name(value) if value else ""
        if "Field" in value_name:
            fields.append(f"{target} ({value_name})")
        elif value_name:
            fields.append(f"{target} = {value_name}")
    return fields


def _summarize_class(class_node: ast.ClassDef) -> str:
    base_names = [_node_name(base) for base in class_node.bases if _node_name(base)]
    methods = [n.name for n in class_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    attributes = _summarize_model_fields(class_node)

    model_bases = {"models.Model", "Model"}
    view_bases = {"View", "APIView", "ViewSet", "TemplateView", "GenericAPIView"}
    command_bases = {"BaseCommand"}

    if set(base_names) & model_bases:
        field_desc = ", ".join(attributes) if attributes else "no explicit fields"
        return f"Django model {class_node.name} (fields: {field_desc})"

    if set(base_names) & view_bases:
        method_desc = ", ".join(methods) if methods else "no methods"
        base_desc = ", ".join(base_names) if base_names else "View"
        return f"View {class_node.name} (bases: {base_desc}) methods: {method_desc}"

    if set(base_names) & command_bases:
        method_desc = ", ".join(methods) if methods else "no handlers"
        extra_attrs = [a for a in attributes if not a.endswith("Field)")]
        attr_desc = f"; attributes: {', '.join(extra_attrs)}" if extra_attrs else ""
        return f"Management command {class_node.name} methods: {method_desc}{attr_desc}"

    attr_desc = f" attributes: {', '.join(attributes)}" if attributes else ""
    method_desc = f" methods: {', '.join(methods)}" if methods else ""
    base_desc = f" bases: {', '.join(base_names)}" if base_names else ""
    return f"Class {class_node.name}{base_desc}{method_desc}{attr_desc}".strip()


def describe_python_semantics(path: Path, text: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""

    summaries: list[str] = []
    functions: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arg_names = [arg.arg for arg in node.args.args]
            arg_text = ", ".join(arg_names)
            functions.append(f"Function {node.name}({arg_text})")
        elif isinstance(node, ast.ClassDef):
            summary = _summarize_class(node)
            if summary:
                summaries.append(summary)

    if not summaries and not functions:
        return ""

    lines = [f"Python overview for {path.name}:"]
    if summaries:
        lines.extend(f"- {line}" for line in summaries)
    if functions:
        lines.append("Functions:")
        lines.extend(f"  - {fn}" for fn in functions)

    return "\n".join(lines)


_SYMBOL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*def\s+(?P<name>[\w_]+)\s*\("), "Function {name}()"),
    (re.compile(r"^\s*class\s+(?P<name>[\w_]+)\b"), "Class {name}"),
    (re.compile(r"^\s*(?:export\s+)?function\s+(?P<name>[\w_]+)\s*\("), "Function {name}()"),
    (re.compile(r"^\s*(?:export\s+)?class\s+(?P<name>[\w_]+)\b"), "Class {name}"),
    (re.compile(r"^\s*export\s+(?:const|let|var)\s+(?P<name>[\w_]+)\s*="), "Export {name}"),
    (re.compile(r"^\s*(?:interface|type)\s+(?P<name>[\w_]+)\b"), "Type {name}"),
    (re.compile(r"^\s*(?:const|let|var)\s+(?P<name>[\w_]+)\s*="), "Variable {name}"),
)


def describe_file_overview(path: Path, text: str) -> str:
    if not text.strip():
        return ""

    if path.suffix == ".py":
        py_summary = describe_python_semantics(path, text)
        if py_summary:
            return py_summary

    lines = text.splitlines()
    symbols: list[str] = []
    for line in lines:
        for pattern, template in _SYMBOL_PATTERNS:
            match = pattern.match(line)
            if match:
                name = match.group("name")
                rendered = template.format(name=name)
                if rendered not in symbols:
                    symbols.append(rendered)
    preview = [ln.strip() for ln in lines if ln.strip()][:3]

    components: list[str] = [f"File overview for {path.name} ({len(lines)} lines):"]
    if symbols:
        components.append("Symbols:")
        components.extend(f"- {entry}" for entry in symbols)
    if preview:
        components.append("Preview:")
        components.extend(f"  {line}" for line in preview)

    return "\n".join(components)


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
            semantic_summary = ""
            semantic_summary = describe_file_overview(file_path, text)
            if file_path.suffix in AST_EXTENSIONS:
                file_chunks = chunk_code_with_ast(file_path, text)
            else:
                file_chunks = chunk_text(text)
            if semantic_summary:
                file_chunks = [semantic_summary, *file_chunks]
        except Exception:
            file_chunks = chunk_text(text)
        for ch in file_chunks:
            chunks.append(f"File: {file_path.relative_to(root)}\n\n{ch}")
    return chunks
