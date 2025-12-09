#!/usr/bin/env python3
"""
FastAPI REST API server for USFM to JSON/HTML conversion pipeline.

This server processes USFM files through two steps:
1. Convert USFM to JSON using usfm-to-json-owl.py
2. Process JSON through repeated_words.py to generate JSON or HTML output
"""

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
import zipfile
import requests
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from utilities.api_utils import run_usfm_to_json, run_repeated_words, run_wildebeest_analysis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Jinja2 templates
BASE_PATH = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_PATH / "templates"))
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")

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
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
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
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
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

        try:
            analysis_result, ref_id_dict = run_wildebeest_analysis(
                usfm_path=usfm_dir
            )
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error in Wildebeest analysis: {str(e)}")
        
        return JSONResponse(content=analysis_result)


@app.get("/view/{user}/{repo}")
async def view_results(user: str, repo: str, request: Request):
    """
    Front end for viewing the results of Greek Room analysis.
    
    Args:
        user: User identifier
        repo: Repository identifier
    """
    if not STORAGE_ENDPOINT:
        raise HTTPException(status_code=500, detail="STORAGE_ENDPOINT not configured")
    
    # Check availability of files via HEAD requests
    duplicate_check_url = f"{STORAGE_ENDPOINT}/{user}/{repo}/duplicate-check-output.html"
    wildebeest_results_url = f"{STORAGE_ENDPOINT}/{user}/{repo}/wildebeest-results.html"
    alignment_results_url = f"{STORAGE_ENDPOINT}/{user}/{repo}/alignment.zip"
    tgt_spell_check_url = f"{STORAGE_ENDPOINT}/{user}/{repo}/tgt-spellings.html"
    
    duplicate_check_available = False
    wildebeest_results_available = False
    alignment_results_available = False
    tgt_spell_check_available = False

    try:
        response = requests.head(duplicate_check_url, timeout=5)
        duplicate_check_available = response.status_code == 200

        response = requests.head(wildebeest_results_url, timeout=5)
        wildebeest_results_available = response.status_code == 200

        response = requests.head(alignment_results_url, timeout=5)
        alignment_results_available = response.status_code == 200

        response = requests.head(tgt_spell_check_url, timeout=5)
        tgt_spell_check_available = response.status_code == 200

    except Exception as e:
        logger.warning(f"HEAD request failed for one or more resources: {e}")
    
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "user": user,
            "repo": repo,
            "duplicate_check_available": duplicate_check_available,
            "wildebeest_results_available": wildebeest_results_available,
            "duplicate_check_url": duplicate_check_url,
            "wildebeest_results_url": wildebeest_results_url,
            "alignment_results_available": alignment_results_available,
            "alignment_results_url": f"/view/{user}/{repo}/alignment/default",
            "tgt_spell_check_available": tgt_spell_check_available,
            "tgt_spell_check_url": tgt_spell_check_url,
        }
    )


@app.get("/view/{user}/{repo}/alignment/{chapter_file}")
def view_alignment_results(user: str, repo: str, chapter_file: str, request: Request):
    """
    View alignment results. Default chapter should be requested as /alignment/default.
    Example chapter_file: "GEN-001.html"
    """
    return _serve_alignment_html(user, repo, chapter_file)


def _extract_html_from_zip(zip_file_path: Path, chapter_file: str) -> str | None:
    """
    Extract an HTML file from a zip archive on disk.
    
    Args:
        zip_file_path: Path to the zip file
        chapter_file: The name of the chapter file to extract (e.g., "GEN-001.html").
    """
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
            if not chapter_file or chapter_file == "default":
                # pick any HTML file under visualization/
                file_path = next(
                    (
                        name for name in zip_file.namelist()
                        if name.startswith("visualization/") and (
                            name.lower().endswith("001.html") or name.lower().endswith(".html")
                        )
                    ),
                    None
                )
                if not file_path:
                    return None
            else:
                file_path = f"visualization/{chapter_file}"
                if file_path not in zip_file.namelist():
                    return None
            
            return zip_file.read(file_path).decode('utf-8')

    except Exception as e:
        logger.error(f"Error extracting HTML from zip: {e}", exc_info=True)
        return None


def _serve_alignment_html(user: str, repo: str, chapter_file: str) -> HTMLResponse:    
    # Download index.json
    index_json_url = f"{STORAGE_ENDPOINT}/{user}/{repo}/alignments/index.json"
    response = requests.get(index_json_url, timeout=30)
    response.raise_for_status()
    index_json = response.json()

    if chapter_file == "default":
        # default to the first entry in index.json
        alignment_file_object_key = next(iter(index_json.values()))
    else:
        # get the book zip file from index
        book_id = chapter_file.split("-")[0]
        alignment_file_object_key = index_json[book_id]
    
    alignment_results_url = f"{STORAGE_ENDPOINT}/{alignment_file_object_key}"
    
    response = requests.get(alignment_results_url, timeout=10)
    response.raise_for_status()

    # Download zip to temporary file
    with tempfile.NamedTemporaryFile(delete=True, suffix='.zip') as temp_zip:
        temp_zip.write(response.content)
        temp_zip_path = Path(temp_zip.name)

        html_content = _extract_html_from_zip(temp_zip_path, chapter_file)
        
        if html_content is None:
            raise HTTPException(status_code=404, detail="Chapter HTML not found in alignment zip")

        return HTMLResponse(content=html_content)

    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

