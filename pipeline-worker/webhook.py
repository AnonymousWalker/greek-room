#!/usr/bin/env python3
"""
FastAPI webhook endpoint for receiving Service Bus messages.

This module provides a webhook endpoint that receives POST requests
with payloads similar to the message structure processed by
ServiceBusListener._process_message().
"""

import json
import os
import re
import zipfile
from datetime import datetime
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from git import Repo
from jinja2 import Environment, FileSystemLoader
from alignment_pipeline import AlignmentPipeline
from utilities.api_utils import (
    run_duplicate_check,
    run_wildebeest_analysis,
    upload_to_blob_storage,
    DUPLICATE_CHECK_OUTPUT_FILENAME,
    WILDEBEEST_RESULTS_FILENAME,
    ALIGNMENT_RESULTS_FILENAME,
    TGT_SPELLINGS_FILENAME,
    INDEX_JSON,
)


R2_BUCKET_NAME = "greekroom-results"
R2_STORAGE_ENDPOINT = os.getenv("R2_STORAGE_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
BLOB_OUTPUT_PREFIX = os.getenv("BLOB_OUTPUT_PREFIX")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Greek Room Pipeline Webhook",
    description="Webhook endpoint for receiving Service Bus messages",
    version="1.0.0",
)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook")
async def receive_webhook(message: Dict[str, Any]):
    """
    Receive a webhook POST request with message payload.
    
    This endpoint accepts POST requests with payloads similar to the
    message structure processed by ServiceBusListener._process_message().
    
    Args:
        message: The webhook message payload as a JSON object
        
    Returns:
        JSON response with processing status
        
    Raises:
        HTTPException: If message validation or processing fails
    """

    topics = message.get("Topics", [])
    event_type = message.get("EventType")
    # Check if it is a consolidated repo update
    if "consolidated" not in topics or event_type not in ("push", "create"):
        logger.info(f"Skipping message - 'consolidated' not in Topics or invalid EventType: Topics={topics}, EventType={event_type}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "skipped"
            }
        )

    try:
        with tempfile.TemporaryDirectory() as tempdir:
            run_greekroom_checks(message, tempdir)
        
        return JSONResponse(
            status_code=200,
            content={"status": "success"}
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webhook message: {str(e)}"
        )

def run_greekroom_checks(message: Dict[str, Any], tempdir: str):
    repo_html_url = message.get("RepoHtmlUrl")
    default_branch = message.get("DefaultBranch")
    user = message.get("User")
    repo = message.get("Repo")
    tempdir_path = Path(tempdir)
    
    os.chdir(tempdir_path)
    Repo.clone_from(repo_html_url, str(repo))
    repo_dir = tempdir_path / repo
    
    wildebeest_results, ref_id_dict = run_wildebeest_analysis(repo_dir)
    
    # Render HTML template
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template('analysis.html')
    
    html_content = template.render(
        wb_analysis_data=wildebeest_results,
        repo_name=f"{user}/{repo}",
        report_create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ref_id_dict=ref_id_dict
    )
    
    # Write HTML file instead of JSON
    wildebeest_result_path = tempdir_path / WILDEBEEST_RESULTS_FILENAME
    with open(wildebeest_result_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Wildebeest results saved to {wildebeest_result_path}")
    
    # Run duplicate check
    duplicate_result_path = tempdir_path / DUPLICATE_CHECK_OUTPUT_FILENAME
    run_duplicate_check(repo_dir, "", "", duplicate_result_path)
    logger.info(f"Duplicate results saved to {duplicate_result_path}")

    # Define object keys for R2 storage
    wildebeest_object_key = f"{user}/{repo}/{WILDEBEEST_RESULTS_FILENAME}"
    duplicate_object_key = f"{user}/{repo}/{DUPLICATE_CHECK_OUTPUT_FILENAME}"

    upload_to_blob_storage(
        wildebeest_result_path, 
        wildebeest_object_key,
        R2_BUCKET_NAME,
        R2_STORAGE_ENDPOINT,
        R2_ACCESS_KEY_ID,
        R2_SECRET_ACCESS_KEY
    )
    upload_to_blob_storage(
        duplicate_result_path, 
        duplicate_object_key,
        R2_BUCKET_NAME,
        R2_STORAGE_ENDPOINT,
        R2_ACCESS_KEY_ID,
        R2_SECRET_ACCESS_KEY
    )

    wildebeest_result_url = f"{BLOB_OUTPUT_PREFIX}/{wildebeest_object_key}"
    duplicate_result_url = f"{BLOB_OUTPUT_PREFIX}/{duplicate_object_key}"
    logger.info(f"Wildebeest result saved to: {wildebeest_result_path}")
    logger.info(f"Duplicate result saved to: {duplicate_result_path}")

    if repo != "en_ulb": # only run alignment for repos other than en_ulb
        alignment_dir = tempdir_path / "alignment"
        os.makedirs(str(alignment_dir), exist_ok=True)
        source_repo_dir = tempdir_path / "en_ulb"
        Repo.clone_from("https://content.bibletranslationtools.org/WA-Catalog/en_ulb.git", str(source_repo_dir))
        alignment_output_path = run_alignment(source_repo_dir, repo_dir, str(alignment_dir))

        alignment_object_key = f"{user}/{repo}/{ALIGNMENT_RESULTS_FILENAME}"
        upload_to_blob_storage(
            alignment_output_path, 
            alignment_object_key,
            R2_BUCKET_NAME,
            R2_STORAGE_ENDPOINT,
            R2_ACCESS_KEY_ID,
            R2_SECRET_ACCESS_KEY,
            "application/zip"
        )

        # Upload splits of the large alignment zip
        index = {}
        zip_splits = split_alignment_zip_by_prefix(alignment_output_path, alignment_dir)
        for zip_split in zip_splits:
            upload_to_blob_storage(
                zip_split, 
                f"{user}/{repo}/alignments/{zip_split.stem}.zip",
                R2_BUCKET_NAME,
                R2_STORAGE_ENDPOINT,
                R2_ACCESS_KEY_ID,
                R2_SECRET_ACCESS_KEY,
                "application/zip"
            )
            index[zip_split.stem] = f"{user}/{repo}/alignments/{zip_split.stem}.zip"

        # upload index.json
        index_json_path = alignment_dir / INDEX_JSON
        with open(index_json_path, 'w') as f:
            json.dump(index, f)
        
        upload_to_blob_storage(
            index_json_path, 
            f"{user}/{repo}/alignments/{INDEX_JSON}",
            R2_BUCKET_NAME,
            R2_STORAGE_ENDPOINT,
            R2_ACCESS_KEY_ID,
            R2_SECRET_ACCESS_KEY,
            "application/json"
        )

        # upload spell-check result
        tgt_spelling_file = alignment_dir / TGT_SPELLINGS_FILENAME
        extract_file_from_zip(
            alignment_output_path, 
            TGT_SPELLINGS_FILENAME,
            tgt_spelling_file
        )

        upload_to_blob_storage(
            tgt_spelling_file, 
            f"{user}/{repo}/{TGT_SPELLINGS_FILENAME}",
            R2_BUCKET_NAME,
            R2_STORAGE_ENDPOINT,
            R2_ACCESS_KEY_ID,
            R2_SECRET_ACCESS_KEY,
            "text/html"
        )
        logger.info(f"Alignment result saved to {alignment_object_key}")


def run_alignment(source_repo_path: str, target_repo_path: str, temp_dir: str) -> Path:
    config = AlignmentPipeline.load_config_from_repos(source_repo_path, target_repo_path, temp_dir=temp_dir)
    pipeline = AlignmentPipeline(config=config, temp_dir=temp_dir)
    output = pipeline.run()
    logger.info(f"Alignment completed.")
    return output


def split_alignment_zip_by_prefix(zip_path: Path, output_dir: Path) -> List[Path]:
    """
    Split an alignment zip file into multiple zip files grouped by three-letter prefix.
    The original zip contains files like:
    - visualization/1CH-001.html
    - visualization/EXO-002.html
    
    This function creates separate zip files for each three-letter prefix (e.g., 1CH, EXO).
    """
    os.makedirs(str(output_dir), exist_ok=True)
    
    pattern = re.compile(r'visualization/(\w{3})-\d{3}\.html')    
    prefix_groups: Dict[str, List[tuple]] = {}
    other_files: List[tuple] = []
    
    # Read the original zip and group files by prefix
    with zipfile.ZipFile(zip_path, 'r') as source_zip:
        for file_info in source_zip.infolist():
            filename = file_info.filename
            match = pattern.match(filename)
            
            if match:
                prefix = match.group(1)
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []

                file_data = source_zip.read(filename)
                prefix_groups[prefix].append((filename, file_info, file_data))
    
    # Create a zip file for each prefix group
    zip_splits: List[Path] = []
    
    for prefix, files in prefix_groups.items():
        zip_filename = output_dir / f"{prefix}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as prefix_zip:
            # Add all files for this prefix
            for filename, file_info, file_data in files:
                prefix_zip.writestr(file_info, file_data)
            
            # Also include non-visualization files (e.g., spell-check files) in each prefix zip
            for filename, file_info, file_data in other_files:
                prefix_zip.writestr(file_info, file_data)
        
        zip_splits.append(zip_filename)
    
    logger.info(f"Split alignment zip into {len(zip_splits)} files by prefix")
    return zip_splits


def extract_file_from_zip(zip_path: Path, filename: str, output_path: Path):
    """Extract a specific file from a zip archive to a target file path."""
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        file_content = zip_file.read(filename)
        with open(output_path, 'wb') as f:
            f.write(file_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

