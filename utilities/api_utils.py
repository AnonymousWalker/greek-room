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

from machine.corpora import UsfmFileTextCorpus, extract_scripture_corpus
import boto3
from botocore.exceptions import ClientError, BotoCoreError

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
        raise FileNotFoundError(f"USFM path not found: {path}")

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
        ValueError: If the conversion fails
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus_from_path(usfm_path)
    if not corpus:
        raise ValueError(
            "Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )

    check_corpus = []
    try:
        for verse_text, _, vref in extract_scripture_corpus(corpus):
            if verse_text is not None and verse_text.strip():
                check_corpus.append({"snt-id": str(vref), "text": verse_text})
    except Exception as exc:
        raise RuntimeError(f"Failed to read USFM content: {exc}") from exc

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
        raise RuntimeError(f"Failed to write JSON output: {exc}") from exc

    return output_json


def run_repeated_words(
    input_json: Path,
    lang_code: str,
    lang_name: str,
    output_json: Optional[Path] = None,
    output_html: Optional[Path] = None
) -> tuple[Optional[Path], Optional[Path]]:

    if not input_json.exists():
        raise FileNotFoundError(f"Input JSON file not found: {input_json}")

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
        raise RuntimeError(error_msg) from e


def run_duplicate_check(usfm_path: Path, lang_code: str, lang_name: str, output_path: Path):
    with tempfile.TemporaryDirectory() as temp_dir:
        intermediate_json = Path(temp_dir) / "owl-input.json"
        run_usfm_to_json(usfm_path, lang_code, lang_name, intermediate_json)
        run_repeated_words(intermediate_json, lang_code, lang_name, output_html=output_path)


def run_wildebeest_analysis(
    usfm_path: Path,
    vref_file_path: Optional[Path] = None
) -> tuple[dict, dict]:
    """
    Run the Wildebeest analysis on the given USFM file and return analysis results.

    Args:
        usfm_path: Path to USFM file or directory
        vref_file_path: Optional path to vref.txt file. If not provided, uses default.

    Returns:
        Tuple of (analysis dictionary, ref_id_dict)

    Raises:
        RuntimeError: If the processing fails
    """
    # Use default vref.txt path if not provided
    if vref_file_path is None:
        vref_file_path = PROJECT_ROOT / "ephesus" / "data" / "vref.txt"
    
    if not vref_file_path.exists():
        raise FileNotFoundError(f"VREF file not found: {vref_file_path}")

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
            
            # Return the analysis dictionary and ref_id_dict
            return wb.analysis, ref_id_dict
    except Exception as e:
        error_msg = f"Wildebeest analysis failed: {str(e)}"
        raise RuntimeError(error_msg) from e


def upload_to_blob_storage(
    file_path: Path,
    object_key: str,
    bucket_name: str,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    content_type: str = "text/html",
) -> str:
    """
    Upload a file to Cloudflare R2 bucket. Default content type is text/html.

    Args:
        file_path: Path to the local file to upload
        object_key: The key (path) where the file will be stored in R2
        bucket_name: Name of the R2 bucket
        endpoint_url: R2 endpoint URL (e.g., https://<account-id>.r2.cloudflarestorage.com)
        access_key: R2 access key ID
        secret_key: R2 secret access key
        content_type: MIME type for the uploaded object. Defaults to text/html.

    Returns:
        The object URL or key of the uploaded file

    Raises:
        RuntimeError: If the upload fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Create S3-compatible client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        # Upload the file
        s3_client.upload_file(
            str(file_path),
            bucket_name,
            object_key,
            ExtraArgs={'ContentType': content_type}
        )

        return object_key

    except ClientError as e:
        error_msg = f"Failed to upload to R2: {e.response.get('Error', {}).get('Message', str(e))}"
        raise RuntimeError(error_msg) from e
    except BotoCoreError as e:
        error_msg = f"R2 connection error: {str(e)}"
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error uploading to R2: {str(e)}"
        raise RuntimeError(error_msg) from e

