#!/usr/bin/env python3
"""
CLI entry point for the Service Bus listener worker.

This script runs the Service Bus listener as a standalone process,
receiving messages from the WACSEvent topic and processing them.

Usage: `op run --env-file=".env.op" -- python main.py`
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add project root and pipeline-worker to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
PIPELINE_WORKER_DIR = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PIPELINE_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_WORKER_DIR))

from service_bus import ServiceBusListener

# Add simple HTTP server for health checks
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service Bus configuration
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
TOPIC_NAME = "WACSEvent"
SUBSCRIPTION_NAME = "GreekRoom"


async def health_check(request):
    """Simple health check endpoint to keep container alive."""
    return web.Response(text="OK", status=200)


async def main():
    """Main entry point for the Service Bus listener."""
    if not SERVICE_BUS_CONNECTION_STRING:
        logger.error("SERVICE_BUS_CONNECTION_STRING environment variable is not set")
        sys.exit(1)
    
    listener = ServiceBusListener(
        connection_string=SERVICE_BUS_CONNECTION_STRING,
        topic_name=TOPIC_NAME,
        subscription_name=SUBSCRIPTION_NAME
    )
    
    # Set up simple HTTP server for health checks (keeps container alive)
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Start health check server on port 8080 (Cloudflare Containers standard)
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Health check server started on port {port}")
    
    # Set up signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Starting Service Bus listener...")
        await listener.start()
        logger.info("Service Bus listener started. Waiting for messages...")
        
        # Wait for shutdown signal
        await shutdown_event.wait()
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await listener.stop()
        await runner.cleanup()
        logger.info("Service Bus listener stopped.")


if __name__ == "__main__":
    asyncio.run(main())

