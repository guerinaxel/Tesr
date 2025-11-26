from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import coverage
from django.conf import settings
from xmlrunner.extra.djangotestrunner import XMLTestRunner

COVERAGE_FAIL_UNDER = 80.0


class CoverageXMLTestRunner(XMLTestRunner):
    """Run Django tests with coverage enforcement and XML output."""

    def run_tests(
        self,
        test_labels: Iterable[str] | None = None,
        **kwargs,
    ) -> int:
        output_dir = Path(settings.TEST_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        cov = coverage.Coverage(
            source=[str(Path(settings.BASE_DIR / "codeqa")), str(Path(settings.BASE_DIR / "project"))],
            omit=[
                "*/migrations/*",
                "*/tests/*",
                "*/settings/*",
                "*/wsgi.py",
                "*/asgi.py",
                "*/apps.py",
                "*/test_runner.py",
            ],
            data_file=str(output_dir / ".coverage"),
        )
        cov.start()

        try:
            failures = super().run_tests(test_labels, **kwargs)
        finally:
            cov.stop()
            cov.save()

        cov.xml_report(outfile=str(output_dir / "coverage.xml"))
        total_coverage = cov.report(show_missing=True, file=sys.stdout)

        if total_coverage < COVERAGE_FAIL_UNDER:
            shortfall = COVERAGE_FAIL_UNDER - total_coverage
            print(
                "ERROR: Coverage "
                f"{total_coverage:.2f}% is below the required {COVERAGE_FAIL_UNDER:.0f}% "
                f"(short by {shortfall:.2f}%)."
            )
            failures += 1

        return failures
