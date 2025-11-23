#!/usr/bin/env python3
"""Summarize JUnit XML test results into a Markdown table for GitHub job summaries."""
from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Tuple

Row = Tuple[str, float, str, str]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="test-results", type=Path, help="Directory containing JUnit XML files")
    parser.add_argument("--heading", default="Test Details", help="Heading for the summary section")
    return parser.parse_args()

def collect_rows(result_files: Iterable[Path]) -> List[Row]:
    rows: List[Row] = []
    for file in result_files:
        tree = ET.parse(file)
        for case in tree.findall(".//testcase"):
            name = "::".join(filter(None, [case.get("classname"), case.get("name")]))
            duration = float(case.get("time", 0.0))
            result = "passed"
            message = ""

            failure = case.find("failure") or case.find("error")
            skipped = case.find("skipped")

            if failure is not None:
                result = "error" if failure.tag == "error" else "failed"
                message = (failure.get("message") or failure.text or "").strip().replace("\n", " ")
            elif skipped is not None:
                result = "skipped"

            rows.append((name, duration, result, message))
    return rows

def write_summary(rows: List[Row], heading: str, summary_path: Path) -> None:
    lines = [
        f"### {heading}",
        "",
        "| Test | Duration (s) | Result | Message |",
        "| --- | ---: | --- | --- |",
    ]

    for name, duration, result, message in sorted(rows):
        safe_message = message.replace("|", "\\|") if result != "passed" else ""
        lines.append(f"| {name} | {duration:.3f} | {result} | {safe_message} |")

    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")

def main() -> int:
    args = parse_args()
    results_dir: Path = args.results_dir
    result_files = sorted(results_dir.rglob("*.xml"))

    if not result_files:
        print(f"No test results found in {results_dir}.")
        return 0

    rows = collect_rows(result_files)

    if not rows:
        print("No test cases found in XML reports.")
        return 0

    summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_env:
        print("GITHUB_STEP_SUMMARY not set; cannot write summary.", file=sys.stderr)
        return 1

    write_summary(rows, args.heading, Path(summary_env))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
