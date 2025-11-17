#!/usr/bin/env python3
"""
Azure Service Bus listener for processing messages from WACSEvent topic.

This module handles receiving and processing messages from Azure Service Bus
Topics and Subscriptions.
"""

import asyncio
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus.exceptions import ServiceBusError

from utilities.api_utils import run_duplicate_check, run_wildebeest_analysis, upload_to_blob_storage

# Configure logging
logger = logging.getLogger(__name__)

R2_BUCKET_NAME = "greekroom-results"
R2_STORAGE_ENDPOINT = os.getenv("R2_STORAGE_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
BLOB_OUTPUT_PREFIX = os.getenv("BLOB_OUTPUT_PREFIX")
RESULT_TOPIC = "GreekRoomResult"

if not R2_STORAGE_ENDPOINT or not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
    raise ValueError("Some R2 environment variables are missing")


class ServiceBusListener:
    """Azure Service Bus listener for receiving messages from a topic subscription."""

    def __init__(
        self,
        connection_string: str,
        topic_name: str,
        subscription_name: str
    ):
        """
        Initialize the Service Bus listener.

        Args:
            connection_string: Azure Service Bus connection string
            topic_name: Name of the topic to listen to
            subscription_name: Name of the subscription to receive messages from
        """
        self.connection_string = connection_string
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the Service Bus listener."""
        if self._running:
            logger.warning("Service Bus listener is already running")
            return

        self._running = True
        logger.info(
            f"Service Bus listener starting for topic '{self.topic_name}' "
            f"subscription '{self.subscription_name}'"
        )
        # Start the message receiving loop
        self._task = asyncio.create_task(self._receive_messages())

    async def stop(self):
        """Stop the Service Bus listener."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping Service Bus listener...")

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Service Bus listener stopped")

    async def _receive_messages(self):
        """Continuously receive and process messages from the subscription."""
        while self._running:
            try:
                async with ServiceBusClient.from_connection_string(
                    conn_str=self.connection_string
                ) as client:
                    async with client.get_subscription_receiver(
                        topic_name=self.topic_name,
                        subscription_name=self.subscription_name
                    ) as receiver:
                        logger.info("Service Bus listener connected and ready to receive messages")
                        
                        # Use async for to receive messages continuously
                        async for message in receiver:
                            if not self._running:
                                break
                            
                            try:
                                # Process the message
                                await self._process_message(message, client)
                                # Complete the message to remove it from the subscription
                            except Exception as e:
                                logger.error(f"Error processing message {message.message_id}: {e}")
                            finally:
                                await receiver.complete_message(message)


            except ServiceBusError as e:
                if self._running:
                    logger.error(f"Service Bus error: {e}")
                    # Wait a bit before retrying
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("Service Bus listener task cancelled")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"Error connecting to Service Bus: {e}")
                    await asyncio.sleep(10)  # Wait longer before reconnecting

    async def _process_message(self, message, client):
        """
        Process a received message.

        Args:
            message: The Service Bus message to process

        Override this method or provide a custom handler to implement
        your message processing logic.
        """
        try:
            parsed_message = json.loads(str(message))

            topics = parsed_message["Topics"]
            event_type = parsed_message["EventType"]

            # Check if "consolidated" is in the topics list
            if "consolidated" not in topics or event_type not in ("push", "create"):
                return None

            parsed_url = urlparse(parsed_message["RepoHtmlUrl"])
            default_branch = parsed_message["DefaultBranch"]
            user = parsed_message["User"]
            repo = parsed_message["Repo"]
            repo_id = parsed_message["RepoId"]

            logger.info(f"Scanning {user}/{repo}")

            repo_url = f"{parsed_url.scheme}://{parsed_url.netloc}/api/v1/repos/{user}/{repo}/archive/{default_branch}.zip"
            
            # Download and extract the repository
            with tempfile.TemporaryDirectory() as tempdir:
                with tempfile.NamedTemporaryFile(delete=False) as download_file:
                    download_path = download_file.name
                
                try:
                    # Download the repository zip file (run in thread to keep async)
                    def download_repo():
                        response = requests.get(repo_url, stream=True)
                        if response.status_code != 200:
                            raise Exception(f"Failed to download {user}/{repo}: HTTP status code {response.status_code}")
                        with open(download_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=128):
                                f.write(chunk)
                        return download_path
                    
                    await asyncio.to_thread(download_repo)
                    
                    # Extract the zip file
                    with zipfile.ZipFile(download_path) as repo_zip:
                        repo_zip.extractall(tempdir)
                    
                    logger.info(f"Successfully downloaded and extracted {user}/{repo} to {tempdir}")
                    
                    # Find the first folder inside the extracted path
                    tempdir_path = Path(tempdir)
                    dirs = [d for d in tempdir_path.iterdir() if d.is_dir()]
                    if not dirs:
                        raise Exception(f"No directories found in extracted archive for {user}/{repo}")
                    repo_dir = dirs[0]
                    
                    # Run Wildebeest analysis
                    wildebeest_results = run_wildebeest_analysis(repo_dir)                    
                    wildebeest_result_path = tempdir_path / "wildebeest-results.json"
                    with open(wildebeest_result_path, 'w', encoding='utf-8') as f:
                        json.dump(wildebeest_results, f, ensure_ascii=False, indent=2)
                    logger.info(f"Wildebeest results saved to {wildebeest_result_path}")
                    
                    # Run duplicate check
                    duplicate_result_path = tempdir_path / "duplicate-check-output.html"
                    run_duplicate_check(repo_dir, "", "", duplicate_result_path)
                    logger.info(f"Duplicate results saved to {duplicate_result_path}")

                    # Define object keys for R2 storage
                    wildebeest_object_key = f"{user}/{repo}/wildebeest-results.json"
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

                    logger.info(f"Uploaded analysis results to R2 for {user}/{repo}")
                    wildebeest_result_url = f"{BLOB_OUTPUT_PREFIX}/{wildebeest_object_key}"
                    duplicate_result_url = f"{BLOB_OUTPUT_PREFIX}/{duplicate_object_key}"
                    logger.info(f"Wildebeest result URL: {wildebeest_result_url}")
                    logger.info(f"Duplicate result URL: {duplicate_result_url}")

                    # with client.get_topic_sender(RESULT_TOPIC) as sender:
                    #     payload = {
                    #         "User": user,
                    #         "Repo": repo,
                    #         "RepoId": repo_id,
                    #         "WildebeestResultUrl": wildebeest_result_url,
                    #         "DuplicateCheckResultUrl": duplicate_result_url
                    #     }
                    #     sender.send_messages(ServiceBusMessage(json.dumps(payload)))
                finally:
                    # Clean up the download file
                    if os.path.exists(download_path):
                        os.unlink(download_path)

        except Exception as e:
            logger.error(f"Error in message processing: {e}")
            raise

