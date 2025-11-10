#!/usr/bin/env python3
"""
Command-line interface for running the Greek Room repeated words pipeline.

Usage example:
    ./usage/run-owl.py -f ~/path/to/file.usfm -c vi -n "Vietnamese" -o ~/output/repeated-words.html
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from machine.corpora import UsfmFileTextCorpus, extract_scripture_corpus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

PACKAGE_ROOT = PROJECT_ROOT / "greekroom"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.append(str(PACKAGE_ROOT))

from greekroom.owl.repeated_words import process_repeated_words  # type: ignore[import]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Greek Room repeated words pipeline on a USFM file."
    )
    parser.add_argument(
        "-f", "--usfm-file",
        required=True,
        type=Path,
        help="Path to the USFM file to process.",
    )
    parser.add_argument(
        "-c", "--lang-code",
        required=True,
        help="Language code (e.g., 'vi', 'eng', 'ceb').",
    )
    parser.add_argument(
        "-n", "--lang-name",
        required=True,
        help="Language name (e.g., 'Vietnamese', 'English', 'Cebuano').",
    )
    parser.add_argument(
        "-o", "--output-file",
        required=True,
        type=Path,
        help=(
            "Target path for the output. Provide a .json or .html extension to generate a single "
            "file, or omit the extension to generate both .json and .html outputs."
        ),
    )
    return parser.parse_args()


def _build_corpus_from_path(path: Path) -> UsfmFileTextCorpus | None:
    """Create a Machine corpus from a USFM file or directory."""
    if not path.exists():
        raise RuntimeError(f"USFM path not found: {path}")

    if path.is_file():
        parent = path.parent
        return UsfmFileTextCorpus(parent.resolve(strict=True), file_pattern=path.name)

    if path.is_dir():
        return UsfmFileTextCorpus(path.resolve(strict=True), file_pattern="*.usfm")

    return None


def run_usfm_to_json(
    usfm_path: Path,
    lang_code: str,
    lang_name: str,
    output_json: Path,
) -> Path:
    """
    Convert USFM/SFM content to the JSON format expected by repeated words.
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)

    corpus = _build_corpus_from_path(usfm_path)
    if not corpus:
        raise RuntimeError(
            "Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )

    check_corpus = []
    try:
        for verse_text, _, vref in extract_scripture_corpus(corpus):
            if verse_text is not None and verse_text.strip():
                check_corpus.append({"snt-id": str(vref), "text": verse_text})
    except Exception as exc:  # pragma: no cover - passthrough
        raise RuntimeError(f"Failed to read USFM content: {exc}") from exc

    json_output = {
        "jsonrpc": "2.0",
        "id": lang_name,
        "method": "BibleTranslationCheck",
        "params": [
            {
                "lang-code": lang_code,
                "lang-name": lang_name,
                "project-id": lang_name,
                "project-name": lang_name,
                "selectors": [
                    {
                        "tool": "GreekRoom",
                        "checks": ["RepeatedWords"],
                    }
                ],
                "check-corpus": check_corpus,
            }
        ],
    }

    try:
        with output_json.open("w", encoding="utf-8") as json_file:
            json.dump(json_output, json_file, ensure_ascii=False, indent=1)
    except OSError as exc:  # pragma: no cover - passthrough
        raise RuntimeError(f"Failed to write JSON output: {exc}") from exc

    return output_json


def run_repeated_words(
    input_json: Path,
    lang_code: str,
    lang_name: str,
    output_json: Optional[Path] = None,
    output_html: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Run repeated_words.py to process JSON and generate output.
    """
    if not input_json.exists():
        raise RuntimeError(f"Input JSON file not found: {input_json}")

    out_filename_str = str(output_json) if output_json else None
    html_filename_str = str(output_html) if output_html else None

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
    if output_html:
        output_html.parent.mkdir(parents=True, exist_ok=True)

    try:
        process_repeated_words(
            json_input=str(input_json),
            lang_code=lang_code,
            lang_name=lang_name,
            out_filename=out_filename_str,
            html_out_filename=html_filename_str,
        )
        return output_json, output_html
    except Exception as exc:  # pragma: no cover - passthrough
        raise RuntimeError(f"Repeated words processing failed: {exc}") from exc


def run_pipeline(
    usfm_path: Path,
    lang_code: str,
    lang_name: str,
    output_file: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    output_file_path = output_file.expanduser().resolve() if output_file else None
    output_dir_path = (
        output_file_path.parent if output_file_path else usfm_path.parent.resolve()
    )
    output_dir_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir="/home/tony-tran/greekroom-data/temp") as temp_dir:
        work_dir = Path(temp_dir)
        intermediate_json = work_dir / "owl-input.json"

        try:
            run_usfm_to_json(
                usfm_path=usfm_path,
                lang_code=lang_code,
                lang_name=lang_name,
                output_json=intermediate_json,
            )
        except Exception as exc:
            raise RuntimeError(f"USFM to JSON conversion failed: {exc}") from exc

        output_json_path: Optional[Path] = None
        output_html_path: Optional[Path] = None
        if output_file_path:
            suffix = output_file_path.suffix.lower()
            if suffix == ".json":
                output_json_path = output_file_path
            elif suffix in (".html", ".htm"):
                output_html_path = output_file_path.with_suffix(".html")
            else:
                base = output_file_path if not suffix else output_file_path.with_suffix("")
                output_json_path = base.with_suffix(".json")
                output_html_path = base.with_suffix(".html")
        else:
            output_json_path = output_dir_path / f"{usfm_path.stem}.json"
            output_html_path = output_dir_path / f"{usfm_path.stem}.html"

        try:
            run_repeated_words(
                input_json=intermediate_json,
                lang_code=lang_code,
                lang_name=lang_name,
                output_json=output_json_path,
                output_html=output_html_path,
            )
        except Exception as exc:
            raise RuntimeError(f"Repeated words processing failed: {exc}") from exc

        print("input usfm path: ", usfm_path)

        return output_json_path, output_html_path


def main() -> None:
    args = parse_args()

    usfm_path: Path = args.usfm_file.expanduser().resolve()
    if not usfm_path.exists():
        print(f"USFM file not found: {usfm_path}", file=sys.stderr)
        sys.exit(1)

    output_file: Optional[Path] = args.output_file

    try:
        output_json, output_html = run_pipeline(
            usfm_path=usfm_path,
            lang_code=args.lang_code,
            lang_name=args.lang_name,
            output_file=output_file,
        )
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if output_json:
        print(f"JSON output written to: {output_json}")
    if output_html:
        print(f"HTML output written to: {output_html}")

    if not output_json and not output_html:
        print("No output generated.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

