#!/usr/bin/env python3
"""
FastAPI REST API server for USFM to JSON/HTML conversion pipeline.

This server processes USFM files through two steps:
1. Convert USFM to JSON using usfm-to-json-owl.py
2. Process JSON through repeated_words.py to generate JSON or HTML output
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse

from utilities.api_utils import run_usfm_to_json, run_repeated_words, run_wildebeest_analysis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

