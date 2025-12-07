from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Literal

from .code_extractor import collect_code_chunks
from .rag_index import RagIndex
from .rag_service import _build_config_from_env
from .rag_state import save_last_root


BuildStatus = Literal["idle", "running", "completed", "error"]


@dataclass
class BuildProgress:
    status: BuildStatus = "idle"
    percent: int = 0
    message: str = "No build started."
    root: str | None = None
    output: str = ""
    errors: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BuildInProgressError(RuntimeError):
    """Raised when attempting to start a build while another is running."""


class _ProgressTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = BuildProgress()

    def snapshot(self) -> BuildProgress:
        with self._lock:
            return BuildProgress(**self._progress.to_dict())

    def start(self, root: str) -> None:
        with self._lock:
            if self._progress.status == "running":
                raise BuildInProgressError("A RAG index build is already running.")

            self._progress = BuildProgress(
                status="running",
                percent=5,
                message=f"Preparing build from {root}",
                root=root,
                output="",
                errors="",
            )

    def update(self, *, message: str, percent: int | float | None = None) -> None:
        with self._lock:
            if percent is not None:
                clamped = max(0, min(int(percent), 100))
                self._progress.percent = clamped
            self._progress.message = message

    def complete(self, *, output: str, errors: str) -> None:
        with self._lock:
            self._progress.status = "completed"
            self._progress.percent = 100
            self._progress.message = "RAG index built successfully."
            self._progress.output = output
            self._progress.errors = errors

    def fail(self, *, message: str, errors: str, output: str = "") -> None:
        with self._lock:
            self._progress.status = "error"
            self._progress.message = message
            self._progress.errors = errors
            self._progress.output = output

    def reset(self) -> None:
        with self._lock:
            self._progress = BuildProgress()


_tracker = _ProgressTracker()


def _execute_build(root: Path, *, force: bool = False) -> None:
    stdout, stderr = StringIO(), StringIO()

    try:
        _tracker.update(message=f"Collecting code from {root}", percent=10)
        chunks = collect_code_chunks(root)
        stdout.write(f"Collected {len(chunks)} chunks from {root}.\n")

        if not chunks:
            stderr.write("No code chunks found, aborting.\n")
            _tracker.fail(message="No code chunks found, aborting.", errors=stderr.getvalue())
            return

        _tracker.update(message="Configuring RAG index...", percent=30)
        config = _build_config_from_env()
        index_path = config.index_path
        if index_path.exists() and not force:
            message = "Index already exists. Use --force to rebuild."
            stderr.write(message + "\n")
            _tracker.fail(message=message, errors=stderr.getvalue(), output=stdout.getvalue())
            return

        _tracker.update(message="Embedding code chunks and writing index...", percent=60)
        rag_index = RagIndex(config)
        rag_index.build_from_texts(chunks)
        stdout.write("RAG index built successfully.\n")

        save_last_root(str(root))
        _tracker.complete(output=stdout.getvalue(), errors=stderr.getvalue())
    except Exception as exc:  # pragma: no cover - defensive path
        stderr.write(f"{exc}\n")
        _tracker.fail(
            message="Failed to build RAG index. See errors for details.",
            errors=stderr.getvalue(),
            output=stdout.getvalue(),
        )


def start_build(root: Path, *, force: bool = False) -> BuildProgress:
    resolved_root = str(root)
    _tracker.start(resolved_root)

    thread = threading.Thread(
        target=_execute_build,
        args=(Path(resolved_root),),
        kwargs={"force": force},
        daemon=True,
    )
    thread.start()

    return _tracker.snapshot()


def get_progress() -> BuildProgress:
    return _tracker.snapshot()


def reset_progress() -> None:
    _tracker.reset()
