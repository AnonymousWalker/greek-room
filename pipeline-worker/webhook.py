#!/usr/bin/env python3
"""
FastAPI webhook endpoint for receiving Service Bus messages.

This module provides a webhook endpoint that receives POST requests
with payloads similar to the message structure processed by
ServiceBusListener._process_message().
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from git import Repo
from alignment_pipeline import AlignmentPipeline


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
    try:
        # Extract fields from JSON object
        topics = message.get("Topics", [])
        event_type = message.get("EventType")
        repo_html_url = message.get("RepoHtmlUrl")
        default_branch = message.get("DefaultBranch")
        user = message.get("User")
        repo = message.get("Repo")
        repo_id = message.get("RepoId")
        
        logger.info(f"Received webhook message for {user}/{repo}")
        logger.debug(f"Message details: Topics={topics}, EventType={event_type}")
        
        # Check if "consolidated" is in the topics list (similar to _process_message)
        if "consolidated" not in topics or event_type not in ("push", "create"):
            logger.info(f"Skipping message - 'consolidated' not in Topics or invalid EventType: Topics={topics}, EventType={event_type}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "skipped"
                }
            )
        
        # Process the message (you can add your processing logic here)
        # For now, we'll just return a success response
        logger.info(f"Processing webhook for {user}/{repo} (EventType: {event_type})")
        
        return JSONResponse(
            status_code=200,
            content={"status": "received"}
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webhook message: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

