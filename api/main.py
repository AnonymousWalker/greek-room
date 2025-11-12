#!/usr/bin/env python3
"""
FastAPI REST API server for USFM to JSON/HTML conversion pipeline.

This server processes USFM files through two steps:
1. Convert USFM to JSON using usfm-to-json-owl.py
2. Process JSON through repeated_words.py to generate JSON or HTML output
"""

import json
import tempfile
from pathlib import Path
import sys
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse
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


app = FastAPI(
    title="Greek Room USFM Conversion API",
    description="API for converting USFM files to JSON/HTML format using repeated words analysis",
    version="1.0.0",
)

def _build_corpus_from_path(path: Path) -> UsfmFileTextCorpus | None:
    """Create a Machine corpus from a USFM file or directory."""
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"USFM path not found: {path}")

    if path.is_file():
        parent = path.parent
        return UsfmFileTextCorpus(parent.resolve(strict=True), file_pattern=path.name)

    if path.is_dir():
        return UsfmFileTextCorpus(path.resolve(strict=True), file_pattern="*.usfm")

    return None



@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Greek Room USFM Conversion API",
        "version": "1.0.0",
        "endpoints": {
            "/check-duplicates": "POST - Check for duplicate/repeated words in USFM file(s)",
            "/wildebeest": "POST - Run Wildebeest analysis on USFM file(s)",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def run_usfm_to_json(
    usfm_path: Path,
    lang_code: str,
    lang_name: str,
    output_json: Path
) -> Path:
    """
    Convert USFM/SFM content to the JSON format expected by repeated words.

    Args:
        usfm_file: Path to USFM file or directory
        lang_code: Language code
        lang_name: Language name
        output_json: Path to output JSON file

    Returns:
        Path to the created JSON file

    Raises:
        HTTPException: If the conversion fails
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)

    corpus = _build_corpus_from_path(usfm_path)
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


@app.post("/check-duplicates")
async def check_duplicates(
    usfm_files: list[UploadFile] = File(..., description="USFM files (one or more)"),
    lang_code: str = Form(..., description="Language code (e.g., 'vi', 'eng', 'ceb')"),
    lang_name: str = Form(..., description="Language name (e.g., 'Vietnamese', 'English', 'Cebuano')"),
    output_format: Literal["json", "html", "both"] = Form(
        default="json",
        description="Output format: 'json', 'html', or 'both'"
    )
):
    """
    Convert USFM file(s) to JSON or HTML format.

    This endpoint:
    1. Accepts one or more uploaded USFM files
    2. Converts the USFM file(s) to JSON using usfm-to-json-owl.py
    3. Processes the JSON through repeated_words.py
    4. Returns the requested output format(s)
    """
    # Create temporary directory for intermediate files
    # with tempfile.TemporaryDirectory(dir="/home/tony-tran/greekroom-data/temp") as temp_dir:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Save uploaded files to temporary location
        usfm_dir = temp_path / "usfm_files"
        usfm_dir.mkdir(exist_ok=True)
        
        if not usfm_files:
            raise HTTPException(status_code=400, detail="At least one USFM file must be provided")
        
        try:
            for usfm_file in usfm_files:
                filename = usfm_file.filename if usfm_file.filename else "uploaded.usfm"
                uploaded_file_path = usfm_dir / filename
                with uploaded_file_path.open("wb") as f:
                    content = await usfm_file.read()
                    f.write(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded file(s): {str(e)}")

        # Step 1: Convert USFM to JSON
        intermediate_json = temp_path / "owl-input.json"
        try:
            run_usfm_to_json(
                usfm_path=usfm_dir,
                lang_code=lang_code,
                lang_name=lang_name,
                output_json=intermediate_json
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error in USFM conversion: {str(e)}")

        # Step 2: Process through repeated_words.py
        output_json_path = None
        output_html_path = None

        if output_format in ("json", "both"):
            output_json_path = temp_path / "output.json"
        if output_format in ("html", "both"):
            output_html_path = temp_path / "output.html"

        try:
            run_repeated_words(
                input_json=intermediate_json,
                lang_code=lang_code,
                lang_name=lang_name,
                output_json=output_json_path,
                output_html=output_html_path
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error in repeated words processing: {str(e)}")

        # Step 3: Return the appropriate response(s)
        if output_format == "json":
            if output_json_path and output_json_path.exists():
                content = output_json_path.read_text(encoding="utf-8")
                # Parse JSON to return as proper JSON object
                json_data = json.loads(content)
                return JSONResponse(content=json_data)
            else:
                raise HTTPException(status_code=500, detail="JSON output file was not created")

        elif output_format == "html":
            if output_html_path and output_html_path.exists():
                content = output_html_path.read_text(encoding="utf-8")
                return HTMLResponse(content=content)
            else:
                raise HTTPException(status_code=500, detail="HTML output file was not created")

        elif output_format == "both":
            # Return both as JSON with JSON object and HTML string
            result = {}
            if output_json_path and output_json_path.exists():
                json_content = output_json_path.read_text(encoding="utf-8")
                result["json"] = json.loads(json_content)
            if output_html_path and output_html_path.exists():
                result["html"] = output_html_path.read_text(encoding="utf-8")

            if not result:
                raise HTTPException(status_code=500, detail="No output files were created")

            return JSONResponse(content=result)


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


@app.post("/wildebeest")
async def wildebeest_analysis(
    usfm_files: list[UploadFile] = File(..., description="USFM files to analyze (one or more)")
):
    """
    Run Wildebeest analysis on USFM file(s).

    This endpoint:
    1. Accepts one or more uploaded USFM files
    2. Converts the USFM file(s) to vref format
    3. Runs Wildebeest analysis
    4. Returns the analysis results as JSON

    Args:
        usfm_files: Uploaded USFM file(s)

    Returns:
        JSON response with Wildebeest analysis results (wb.analysis object)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Save uploaded files to temporary location
        usfm_dir = temp_path / "usfm_files"
        usfm_dir.mkdir(exist_ok=True)
        
        if not usfm_files:
            raise HTTPException(status_code=400, detail="At least one USFM file must be provided")
        
        try:
            for usfm_file in usfm_files:
                filename = usfm_file.filename if usfm_file.filename else "uploaded.usfm"
                uploaded_file_path = usfm_dir / filename
                with uploaded_file_path.open("wb") as f:
                    content = await usfm_file.read()
                    f.write(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded file(s): {str(e)}")

        analysis_result = run_wildebeest_analysis(
            usfm_path=usfm_dir
        )
        return JSONResponse(content=analysis_result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

