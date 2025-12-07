from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from django.test import TestCase

from codeqa import build_runner


class BuildRunnerTests(TestCase):
    def setUp(self) -> None:
        build_runner.reset_progress()
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_start_build_runs_with_fake_thread(self) -> None:
        # Arrange
        fake_chunks = ["alpha", "beta"]

        class FakeRagIndex:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                pass

            def build_from_texts(self, _texts: list[str]) -> None:
                return None

        def immediate_thread(target, args=(), kwargs=None, daemon=False):
            kwargs = kwargs or {}
            target(*args, **kwargs)

            class _Thread:
                def start(self_inner):
                    return None

            return _Thread()

        with patch("codeqa.build_runner.collect_code_chunks", return_value=fake_chunks), patch(
            "codeqa.build_runner.RagIndex", FakeRagIndex
        ), patch("codeqa.build_runner.threading.Thread", side_effect=immediate_thread):
            # Act
            progress = build_runner.start_build(Path(self.tmpdir.name))

        # Assert
        self.assertEqual("completed", build_runner.get_progress().status)
        self.assertEqual("completed", progress.status)

    def test_start_build_rejects_parallel_run(self) -> None:
        # Arrange
        build_runner.reset_progress()
        build_runner._tracker.start(self.tmpdir.name)  # type: ignore[attr-defined]

        # Act / Assert
        with self.assertRaises(build_runner.BuildInProgressError):
            build_runner.start_build(Path(self.tmpdir.name))

    def test_execute_build_records_failure_on_missing_chunks(self) -> None:
        # Arrange
        with patch("codeqa.build_runner.collect_code_chunks", return_value=[]):
            # Act
            build_runner._execute_build(Path(self.tmpdir.name))  # type: ignore[attr-defined]

        # Assert
        progress = build_runner.get_progress()
        self.assertEqual("error", progress.status)
        self.assertIn("No code chunks", progress.message)
