#!/usr/bin/env python3
"""
Utility functions for USFM processing pipeline.

This module contains helper functions for:
- Building corpora from USFM files
- Converting USFM to JSON format
- Processing repeated words
- Running Wildebeest analysis
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from machine.corpora import UsfmFileTextCorpus, extract_scripture_corpus

PROJECT_ROOT = Path(__file__).parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "greekroom"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.append(str(PACKAGE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from greekroom.owl.repeated_words import process_repeated_words  # type: ignore[import]
from utilities.prep_usfm import convert_usfm_to_vref  # type: ignore[import]
from wildebeest import wb_analysis  # type: ignore[import]


def build_corpus_from_path(path: Path) -> UsfmFileTextCorpus | None:
    """Create a Machine corpus from a USFM file or directory."""
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"USFM path not found: {path}")

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
    output_json: Path
) -> Path:
    """
    Convert USFM/SFM content to the JSON format expected by repeated words.

    Args:
        usfm_path: Path to USFM file or directory
        lang_code: Language code
        lang_name: Language name
        output_json: Path to output JSON file

    Returns:
        Path to the created JSON file

    Raises:
        HTTPException: If the conversion fails
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus_from_path(usfm_path)
    if not corpus:
        raise HTTPException(
            status_code=400,
            detail="Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )

    check_corpus = []
    try:
        for verse_text, _, vref in extract_scripture_corpus(corpus):
            if verse_text is not None and verse_text.strip():
                check_corpus.append({"snt-id": str(vref), "text": verse_text})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read USFM content: {exc}")

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
            "check-corpus": check_corpus,
        }],
    }

    try:
        with output_json.open("w", encoding="utf-8") as json_file:
            json.dump(json_output, json_file, ensure_ascii=False, indent=1)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write JSON output: {exc}")

    return output_json


def run_repeated_words(
    input_json: Path,
    lang_code: str,
    lang_name: str,
    output_json: Optional[Path] = None,
    output_html: Optional[Path] = None
) -> tuple[Optional[Path], Optional[Path]]:
    """
    Run repeated_words.py to process JSON and generate output.

    Args:
        input_json: Path to input JSON file
        lang_code: Language code
        lang_name: Language name
        output_json: Optional path to output JSON file
        output_html: Optional path to output HTML file

    Returns:
        Tuple of (output_json_path, output_html_path)

    Raises:
        HTTPException: If the processing fails
    """
    if not input_json.exists():
        raise HTTPException(status_code=400, detail=f"Input JSON file not found: {input_json}")

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
            html_out_filename=html_filename_str
        )
        return output_json, output_html
    except Exception as e:
        error_msg = f"Repeated words processing failed: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)


def run_wildebeest_analysis(
    usfm_path: Path,
    vref_file_path: Optional[Path] = None
) -> dict:
    """
    Run the Wildebeest analysis on the given USFM file and return analysis results.

    Args:
        usfm_path: Path to USFM file or directory
        vref_file_path: Optional path to vref.txt file. If not provided, uses default.

    Returns:
        Dictionary containing the Wildebeest analysis results

    Raises:
        HTTPException: If the processing fails
    """
    # Use default vref.txt path if not provided
    if vref_file_path is None:
        vref_file_path = PROJECT_ROOT / "ephesus" / "data" / "vref.txt"
    
    if not vref_file_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"VREF file not found: {vref_file_path}"
        )

    try:
        # Convert USFM to vref format
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vref_text_path = convert_usfm_to_vref(usfm_path, temp_path)
            
            # Load reference IDs
            ref_id_dict = wb_analysis.load_ref_ids(str(vref_file_path))
            
            # Run Wildebeest analysis and get the result object
            wb = wb_analysis.process(
                in_file=str(vref_text_path),
                ref_id_dict=ref_id_dict,
            )
            
            # Return the analysis dictionary
            return wb.analysis
    except Exception as e:
        error_msg = f"Wildebeest analysis failed: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)

