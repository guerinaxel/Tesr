from __future__ import annotations

from pathlib import Path

from .rag_service import _get_data_dir


_STATE_FILENAME = "rag_last_root.txt"


def get_default_root() -> str:
    """Return the default root used when no custom path is provided."""

    return str(Path("..").resolve())


def _state_path() -> Path:
    return _get_data_dir() / _STATE_FILENAME


def save_last_root(root: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(root)


def load_last_root() -> str:
    path = _state_path()
    if not path.exists():
        return get_default_root()

    stored = path.read_text().strip()
    return stored or get_default_root()
