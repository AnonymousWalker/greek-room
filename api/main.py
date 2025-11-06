#!/usr/bin/env python3
"""
FastAPI REST API server for USFM to JSON/HTML conversion pipeline.

This server processes USFM files through two steps:
1. Convert USFM to JSON using usfm-to-json-owl.py
2. Process JSON through repeated_words.py to generate JSON or HTML output
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse

# Paths to scripts (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent
USFM_TO_JSON_SCRIPT = PROJECT_ROOT / "utilities" / "usfm-to-json-owl.py"
REPEATED_WORDS_SCRIPT = PROJECT_ROOT / "greekroom" / "greekroom" / "owl" / "repeated_words.py"

app = FastAPI(
    title="Greek Room USFM Conversion API",
    description="API for converting USFM files to JSON/HTML format using repeated words analysis",
    version="1.0.0",
)




@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Greek Room USFM Conversion API",
        "version": "1.0.0",
        "endpoints": {
            "/convert": "POST - Convert USFM file to JSON/HTML",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def run_usfm_to_json(
    usfm_file: str,
    lang_code: str,
    lang_name: str,
    output_json: Path
) -> Path:
    """
    Run usfm-to-json-owl.py to convert USFM to JSON.

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
    usfm_path = Path(usfm_file).resolve()
    if not usfm_path.exists():
        raise HTTPException(status_code=400, detail=f"USFM file not found: {usfm_file}")

    output_json.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3",
        str(USFM_TO_JSON_SCRIPT),
        "-f", str(usfm_path),
        "-c", lang_code,
        "-n", lang_name,
        "-o", str(output_json)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT)
        )
        return output_json
    except subprocess.CalledProcessError as e:
        error_msg = f"USFM to JSON conversion failed: {e.stderr or e.stdout}"
        raise HTTPException(status_code=500, detail=error_msg)


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

    cmd = [
        "python3",
        str(REPEATED_WORDS_SCRIPT),
        "-j", str(input_json),
        "--lang_code", lang_code,
        "--lang_name", lang_name
    ]

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(output_json)])

    if output_html:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--html", str(output_html)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT)
        )
        return output_json, output_html
    except subprocess.CalledProcessError as e:
        error_msg = f"Repeated words processing failed: {e.stderr or e.stdout}"
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/convert")
async def convert_usfm(
    usfm_file: UploadFile = File(..., description="USFM file to convert"),
    lang_code: str = Form(..., description="Language code (e.g., 'vi', 'eng', 'ceb')"),
    lang_name: str = Form(..., description="Language name (e.g., 'Vietnamese', 'English', 'Cebuano')"),
    output_format: Literal["json", "html", "both"] = Form(
        default="json",
        description="Output format: 'json', 'html', or 'both'"
    )
):
    """
    Convert USFM file to JSON or HTML format.

    This endpoint:
    1. Accepts an uploaded USFM file
    2. Converts the USFM file to JSON using usfm-to-json-owl.py
    3. Processes the JSON through repeated_words.py
    4. Returns the requested output format(s)
    """
    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory(dir="/home/tony-tran/greekroom-data/temp") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save uploaded file to temporary location
        uploaded_file_path = temp_path / usfm_file.filename if usfm_file.filename else temp_path / "uploaded.usfm"
        try:
            with uploaded_file_path.open("wb") as f:
                content = await usfm_file.read()
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded file: {str(e)}")
        
        # Step 1: Convert USFM to JSON
        intermediate_json = temp_path / "owl-input.json"
        try:
            run_usfm_to_json(
                usfm_file=str(uploaded_file_path),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

