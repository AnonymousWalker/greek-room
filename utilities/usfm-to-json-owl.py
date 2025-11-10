#!/usr/bin/env python3
"""
Convert USFM files to JSON format for BibleTranslationCheck.

Usage:
    python script-name.py -f <usfm-file|dir> -c <lang-code> -n <lang-name> -o <output.json>
    python script-name.py --usfm-file <usfm-file|dir> --lang-code <code> --lang-name <name> --output <output.json>
"""

import argparse
import sys
import json
from pathlib import Path
from machine.corpora import (
    UsfmFileTextCorpus,
    extract_scripture_corpus,
)


def build_corpus_from_path(path: Path):
    """Return a Machine corpus given a path to a USFM file or a directory.

    Preference order:
    - If a USFM/SFM file is provided, use its parent dir and suffix
    - Else, if a directory contains USFM files, use the first one's suffix for pattern
    """
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    # If a single file is given
    if path.is_file():
        parent = path.parent
        return UsfmFileTextCorpus(parent.resolve(strict=True), file_pattern=path.name)

    # Otherwise, treat as a directory of USFM files
    if path.is_dir():
        return UsfmFileTextCorpus(
            path.resolve(strict=True),
            file_pattern="*.usfm"
        )

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Convert USFM files to JSON format for BibleTranslationCheck",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python usfm-to-json-owl.py -f data/usfm/ceb -c ceb -n Cebuano -o output/ceb_01.json
  python usfm-to-json-owl.py --usfm-file /path/to/book.usfm --lang-code eng --lang-name English --output output.json
  python usfm-to-json-owl.py -f /path/to/directory -c ceb -n Cebuano -o output.json
        """
    )
    parser.add_argument(
        "-f", "--usfm-file",
        required=True,
        help="Path to USFM/SFM file or directory containing USFM files"
    )
    parser.add_argument(
        "-c", "--lang-code",
        required=True,
        help="Language code (e.g., 'ceb', 'eng')"
    )
    parser.add_argument(
        "-n", "--lang-name",
        required=True,
        help="Language name (e.g., 'Cebuano', 'English')"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output JSON file path"
    )

    args = parser.parse_args()

    usfm_path = Path(args.usfm_file).resolve()
    lang_code = args.lang_code
    lang_name = args.lang_name
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus_from_path(usfm_path)

    if not corpus:
        print(
            "Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )
        sys.exit(2)

    # Extract verses from USFM
    check_corpus = []
    for verse_text, _, vref in extract_scripture_corpus(corpus):
        # Only include verses with non-empty text
        if verse_text is not None and verse_text.strip() != "":
            check_corpus.append({
                "snt-id": str(vref),
                "text": verse_text
            })

    # Build the JSON structure
    json_output = {
        "jsonrpc": "2.0",
        "id": lang_name,
        "method": "BibleTranslationCheck",
        "params": [{
            "lang-code": lang_code,
            "lang-name": lang_name,
            "project-id": lang_name,
            "project-name": lang_name,
            "selectors": [{
                "tool": "GreekRoom",
                "checks": ["RepeatedWords"]
            }],
            "check-corpus": check_corpus
        }]
    }

    # Write JSON output
    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(json_output, json_file, ensure_ascii=False, indent=1)

    print(f"Successfully converted USFM to JSON (owl): {output_path}")


if __name__ == "__main__":
    main()

