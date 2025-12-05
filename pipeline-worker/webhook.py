#!/usr/bin/env python3
"""
FastAPI webhook endpoint for receiving Service Bus messages.

This module provides a webhook endpoint that receives POST requests
with payloads similar to the message structure processed by
ServiceBusListener._process_message().
"""

import os
from datetime import datetime
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from git import Repo
from jinja2 import Environment, FileSystemLoader
from alignment_pipeline import AlignmentPipeline
from utilities.api_utils import run_duplicate_check, run_wildebeest_analysis, upload_to_blob_storage


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
    
    repo_dir = tempdir_path / repo
    repo_dir.mkdir(parents=True, exist_ok=True)
    Repo.clone_from(repo_html_url, str(repo_dir))
    
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
    wildebeest_result_path = tempdir_path / "wildebeest-results.html"
    with open(wildebeest_result_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Wildebeest results saved to {wildebeest_result_path}")
    
    # Run duplicate check
    duplicate_result_path = tempdir_path / "duplicate-check-output.html"
    run_duplicate_check(repo_dir, "", "", duplicate_result_path)
    logger.info(f"Duplicate results saved to {duplicate_result_path}")

    # Define object keys for R2 storage
    wildebeest_object_key = f"{user}/{repo}/wildebeest-results.html"
    duplicate_object_key = f"{user}/{repo}/duplicate-check-output.html"

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
    logger.info(f"Wildebeest result URL: {wildebeest_result_url}")
    logger.info(f"Duplicate result URL: {duplicate_result_url}")

    # run_alignment(source_repo_dir, repo_dir)


@app.post("/debug-alignment")
def debug():
    source_repo_url = "https://content.bibletranslationtools.org/WA-Catalog/en_ulb.git"
    target_repo_url = "https://content.bibletranslationtools.org/WA-Catalog/vi_ulb.git"
    
    with tempfile.TemporaryDirectory() as base_temp_dir:
        base_path = Path(base_temp_dir)
        source_repo_path = base_path / "en_ulb"
        target_repo_path = base_path / "vi_ulb"
        
        Repo.clone_from(source_repo_url, str(source_repo_path))
        Repo.clone_from(target_repo_url, str(target_repo_path))
        
        run_alignment(str(source_repo_path), str(target_repo_path))
        
        return JSONResponse(status_code=200, content={"status": "completed"})


def run_alignment(source_repo_path: str, target_repo_path: str):
    with tempfile.TemporaryDirectory() as temp_dir:
        config = AlignmentPipeline.load_config_from_repos(source_repo_path, target_repo_path, temp_dir=temp_dir)
        pipeline = AlignmentPipeline(config=config, temp_dir=temp_dir)
        pipeline.run()
        logger.info(f"Pipeline completed. Check outputs: {temp_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

